import logging

from celery.utils.log import get_task_logger
from django.conf import settings
from rest_framework import status

from apps.alerts.models import Alert, AlertGroup
from apps.discord.alert_rendering import AlertGroupDiscordRenderer, DiscordMessageRenderer
from apps.discord.client import DiscordClient
from apps.discord.client import DiscordMessage as DiscordAPIMessage
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid
from apps.discord.models import DiscordChannel, DiscordMessage
from apps.user_management.models import User
from common.custom_celery_tasks import shared_dedicated_queue_retry_task
from common.utils import OkToRetry, task_lock

logger = get_task_logger(__name__)
logger.setLevel(logging.DEBUG)


@shared_dedicated_queue_retry_task(
    bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=1 if settings.DEBUG else None
)
def on_create_alert_async(self, alert_pk):
    """
    It's async in order to prevent Discord downtime or formatting issues causing delay with SMS and other destinations.
    """
    try:
        alert = Alert.objects.get(pk=alert_pk)
    except Alert.DoesNotExist as e:
        if on_create_alert_async.request.retries >= 10:
            logger.error(f"Alert {alert_pk} was not found. Probably it was deleted. Stop retrying")
            return
        raise e

    alert_group = alert.group
    discord_channel = DiscordChannel.get_channel_for_alert_group(alert_group=alert_group)
    if not discord_channel:
        logger.error(f"Discord channel not found for alert {alert_pk}. Probably it was deleted. Stop retrying")
        return

    # Every alert in a group queues one of these, so the "has it been posted yet" check and the post itself have to
    # happen together: two tasks that both read "no" would each post a card, and only one of them could be recorded.
    with task_lock(f"discord-alert-group-message-{alert_group.pk}", self.request.id) as acquired:
        if not acquired:
            logger.info(f"Another task is already posting alert group {alert_group.pk} to discord, skipping")
            return

        message = alert_group.discord_messages.filter(message_type=DiscordMessage.ALERT_GROUP_MESSAGE).first()
        if message:
            logger.info(f"Discord message exists with message id {message.message_id} hence skipping")
            return

        renderer = DiscordMessageRenderer(alert_group)
        payload = renderer.render_alert_group_message()

        with OkToRetry(task=self, exc=(DiscordAPIException,), num_retries=3):
            try:
                client = DiscordClient()
                if discord_channel.is_forum:
                    # A forum post is the alert group's own thread, so discussion lands beside the card rather than
                    # in a shared channel.
                    name = renderer.render_thread_name()

                    # Thread creation takes no nonce, so Discord cannot make the retry idempotent the way it does
                    # for a message. A retry is therefore the one time it is worth asking whether the post this task
                    # is about to open already exists — which it does if a previous attempt posted and then died
                    # before it could record where.
                    thread_id = (
                        client.find_thread_for(
                            guild_id=discord_channel.guild_id,
                            channel_id=discord_channel.channel_id,
                            name=name,
                            marker=alert_group.public_primary_key,
                        )
                        if self.request.retries
                        else None
                    )
                    if thread_id:
                        logger.info(
                            f"Adopting discord post {thread_id} already opened for alert group {alert_group.pk}"
                        )
                    else:
                        thread_id = client.create_thread(
                            channel_id=discord_channel.channel_id,
                            name=name,
                            data=payload,
                            applied_tags=discord_channel.tag_ids_for(renderer.state_tag_name()),
                        ).message_id
                    discord_message = DiscordAPIMessage(message_id=thread_id, channel_id=discord_channel.channel_id)
                else:
                    thread_id = None
                    discord_message = client.create_message(
                        channel_id=discord_channel.channel_id,
                        data=payload,
                        nonce=f"ag-{alert_group.public_primary_key}",
                    )
            except DiscordAPITokenInvalid:
                logger.error(f"Discord bot token is invalid, could not create message for alert {alert_pk}")
            except DiscordAPIException as ex:
                logger.error(f"Discord API error {ex}")
                if ex.status not in [
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN,
                    status.HTTP_404_NOT_FOUND,
                ]:
                    raise ex
            else:
                DiscordMessage.create_message(
                    alert_group=alert_group,
                    message=discord_message,
                    message_type=DiscordMessage.ALERT_GROUP_MESSAGE,
                    thread_id=thread_id,
                )


@shared_dedicated_queue_retry_task(
    autoretry_for=(Exception,), retry_backoff=True, max_retries=1 if settings.DEBUG else None
)
def on_alert_group_action_triggered_async(log_record_id):
    from apps.alerts.models import AlertGroupLogRecord
    from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative

    try:
        log_record = AlertGroupLogRecord.objects.get(pk=log_record_id)
    except AlertGroupLogRecord.DoesNotExist as e:
        logger.warning(f"Discord representative: log record {log_record_id} never created or has been deleted")
        raise e

    alert_group_id = log_record.alert_group_id

    try:
        log_record.alert_group.discord_messages.get(message_type=DiscordMessage.ALERT_GROUP_MESSAGE)
    except DiscordMessage.DoesNotExist as e:
        if on_alert_group_action_triggered_async.request.retries >= 10:
            logger.error(f"Discord message not created for {alert_group_id}. Stop retrying")
            return
        raise e

    logger.info(
        f"Start discord on_alert_group_action_triggered for alert_group {alert_group_id}, log record {log_record_id}"
    )
    representative = AlertGroupDiscordRepresentative(log_record)
    if representative.is_applicable():
        representative.get_handler()(log_record.alert_group)


@shared_dedicated_queue_retry_task(
    autoretry_for=(Exception,), retry_backoff=True, max_retries=1 if settings.DEBUG else None
)
def notify_user_about_alert_async(user_pk, alert_group_pk, notification_policy_pk):
    from apps.base.models import UserNotificationPolicy, UserNotificationPolicyLogRecord

    def _create_error_log_record(notification_error_code=None):
        UserNotificationPolicyLogRecord.objects.create(
            author=user,
            type=UserNotificationPolicyLogRecord.TYPE_PERSONAL_NOTIFICATION_FAILED,
            notification_policy=notification_policy,
            alert_group=alert_group,
            reason="Error during discord notification",
            notification_step=notification_policy.step,
            notification_channel=notification_policy.notify_by,
            notification_error_code=notification_error_code,
        )

    try:
        user = User.objects.get(pk=user_pk)
        alert_group = AlertGroup.objects.get(pk=alert_group_pk)
        notification_policy = UserNotificationPolicy.objects.get(pk=notification_policy_pk)
        discord_message = alert_group.discord_messages.get(message_type=DiscordMessage.ALERT_GROUP_MESSAGE)
    except User.DoesNotExist:
        logger.warning(f"User {user_pk} is not found")
        return
    except AlertGroup.DoesNotExist:
        logger.warning(f"Alert group {alert_group_pk} is not found")
        return
    except UserNotificationPolicy.DoesNotExist:
        logger.warning(f"UserNotificationPolicy {notification_policy_pk} is not found")
        return
    except DiscordMessage.DoesNotExist as e:
        if notify_user_about_alert_async.request.retries >= 10:
            logger.error(
                f"Alert group discord message is not created {alert_group_pk}. Hence stopped retrying for user notification"
            )
            _create_error_log_record(
                UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_ALERT_GROUP_MESSAGE_NOT_FOUND
            )
            return
        raise e

    templated_alert = AlertGroupDiscordRenderer(alert_group).alert_renderer.templated_alert
    discord_user = getattr(user, "discord_user_identity", None)
    if discord_user is None:
        content = f"{templated_alert.title}\nTried to invite {user.username} to look at the alert group. "
        content += f"Unfortunately {user.username} has not linked a Discord account."
        _create_error_log_record(UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_USER_NOT_IN_DISCORD)
    else:
        content = f"{templated_alert.title}\nInviting {discord_user.mention_username} to look at the alert group."

    payload = {
        "content": content,
        "message_reference": {"message_id": discord_message.message_id, "fail_if_not_exists": False},
        # An alert annotation is attacker-adjacent text, so a stray @everyone in one must never resolve: only the
        # user being invited is allowed to be pinged.
        "allowed_mentions": {"parse": [], "users": [discord_user.discord_user_id] if discord_user else []},
    }

    try:
        DiscordClient().create_message(
            channel_id=discord_message.channel_id,
            data=payload,
            # Same reason as the alert group card: the log record is written after the post, and a retry in between
            # must not page the user twice.
            nonce=f"un-{notification_policy.pk}-{alert_group.pk}",
        )
    except DiscordAPITokenInvalid:
        logger.error(f"Discord bot token is invalid, could not notify user about alert group {alert_group_pk}")
        _create_error_log_record(UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_API_TOKEN_INVALID)
    except DiscordAPIException as ex:
        logger.error(f"Discord API error {ex}")
        if ex.status not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
            raise ex
        _create_error_log_record(UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_API_UNAUTHORIZED)
    else:
        UserNotificationPolicyLogRecord.objects.create(
            author=user,
            type=UserNotificationPolicyLogRecord.TYPE_PERSONAL_NOTIFICATION_SUCCESS,
            notification_policy=notification_policy,
            alert_group=alert_group,
            notification_step=notification_policy.step,
            notification_channel=notification_policy.notify_by,
        )
