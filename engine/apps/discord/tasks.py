import logging

from celery.utils.log import get_task_logger
from django.conf import settings
from rest_framework import status

from apps.alerts.models import Alert
from apps.discord.alert_rendering import DiscordMessageRenderer
from apps.discord.client import DiscordClient
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid
from apps.discord.models import DiscordChannel, DiscordMessage
from common.custom_celery_tasks import shared_dedicated_queue_retry_task
from common.utils import OkToRetry

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

    message = alert_group.discord_messages.filter(message_type=DiscordMessage.ALERT_GROUP_MESSAGE).first()
    if message:
        logger.error(f"Discord message exists with message id {message.message_id} hence skipping")
        return

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    with OkToRetry(task=self, exc=(DiscordAPIException,), num_retries=3):
        try:
            discord_message = DiscordClient().create_message(channel_id=discord_channel.channel_id, data=payload)
        except DiscordAPITokenInvalid:
            logger.error(f"Discord bot token is invalid, could not create message for alert {alert_pk}")
        except DiscordAPIException as ex:
            logger.error(f"Discord API error {ex}")
            if ex.status not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]:
                raise ex
        else:
            DiscordMessage.create_message(
                alert_group=alert_group, message=discord_message, message_type=DiscordMessage.ALERT_GROUP_MESSAGE
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
