import logging

from rest_framework import status

from apps.alerts.models import AlertGroup
from apps.alerts.representative import AlertGroupAbstractRepresentative
from apps.discord.alert_rendering import DiscordMessageRenderer
from apps.discord.client import DiscordClient
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid
from apps.discord.tasks import on_alert_group_action_triggered_async, on_create_alert_async
from apps.discord.utils import beside_card

logger = logging.getLogger(__name__)


class AlertGroupDiscordRepresentative(AlertGroupAbstractRepresentative):
    def __init__(self, log_record) -> None:
        self.log_record = log_record

    def is_applicable(self):
        from apps.discord.models import DiscordChannel

        organization = self.log_record.alert_group.channel.organization
        handler_exists = self.log_record.type in self.get_handler_map().keys()

        return handler_exists and DiscordChannel.objects.filter(organization=organization).exists()

    @staticmethod
    def get_handler_map():
        from apps.alerts.models import AlertGroupLogRecord

        return {
            AlertGroupLogRecord.TYPE_ACK: "alert_group_action",
            AlertGroupLogRecord.TYPE_UN_ACK: "alert_group_action",
            AlertGroupLogRecord.TYPE_AUTO_UN_ACK: "alert_group_action",
            AlertGroupLogRecord.TYPE_RESOLVED: "alert_group_action",
            AlertGroupLogRecord.TYPE_UN_RESOLVED: "alert_group_action",
            AlertGroupLogRecord.TYPE_ACK_REMINDER_TRIGGERED: "alert_group_action",
            AlertGroupLogRecord.TYPE_SILENCE: "alert_group_action",
            AlertGroupLogRecord.TYPE_UN_SILENCE: "alert_group_action",
            AlertGroupLogRecord.TYPE_ATTACHED: "alert_group_action",
            AlertGroupLogRecord.TYPE_UNATTACHED: "alert_group_action",
            AlertGroupLogRecord.TYPE_ESCALATION_TRIGGERED: "escalation_triggered",
        }

    def on_escalation_triggered(self, alert_group: AlertGroup):
        """Say out loud that OnCall has escalated, for the steps that mean "everyone".

        OnCall's own escalation reaches people through their notification policies, which is the part that respects
        who is actually on call. This adds the thing a channel gives that a DM does not: everybody watching can see
        that an alert has gone unanswered.
        """
        from apps.alerts.models import EscalationPolicy
        from apps.discord.alert_rendering import route_escalation_role

        broadcast_steps = (
            EscalationPolicy.STEP_FINAL_NOTIFYALL,
            EscalationPolicy.STEP_NOTIFY_GROUP,
            EscalationPolicy.STEP_NOTIFY_GROUP_IMPORTANT,
        )
        if self.log_record.escalation_policy_step not in broadcast_steps:
            return

        if alert_group.acknowledged or alert_group.resolved or alert_group.silenced:
            logger.info(f"Alert group {alert_group.pk} was already handled, not escalating it in discord")
            return

        discord_message = alert_group.discord_messages.order_by("created_at").first()
        if discord_message is None:
            return

        # A route names a role to escalate to, or it does not. Either way the channel is told, because a step
        # that says "notify everyone" and then says nothing is worse than a channel message with no ping in it.
        role = route_escalation_role(alert_group)
        payload = {
            "content": (
                f"<@&{role}> — this alert group is still unacknowledged."
                if role
                else "This alert group is still unacknowledged."
            ),
            # The role being escalated to, and nothing else the alert text happens to name.
            "allowed_mentions": {"parse": [], "roles": [role] if role else []},
        }
        channel_id, reference = beside_card(discord_message)
        payload.update(reference)

        try:
            DiscordClient().create_message(
                channel_id=channel_id,
                data=payload,
                nonce=f"es-{alert_group.public_primary_key}-{self.log_record.pk}",
            )
        except DiscordAPITokenInvalid:
            logger.error(f"Discord bot token is invalid, could not escalate alert group {alert_group.pk}")
        except DiscordAPIException as ex:
            logger.error(f"Discord API error {ex}")
            if ex.status not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]:
                raise ex

    def on_alert_group_action(self, alert_group: AlertGroup):
        from apps.discord.models import DiscordChannel

        logger.info(f"Update discord message for alert_group {alert_group.pk}")
        renderer = DiscordMessageRenderer(alert_group)
        payload = renderer.render_alert_group_message()
        discord_message = alert_group.discord_messages.order_by("created_at").first()
        try:
            client = DiscordClient()
            if discord_message.thread_id:
                # Discord archives a quiet post on its own and an archived post refuses edits, so the post is
                # unarchived and retagged in the same call that would have only retagged it.
                channel = DiscordChannel.objects.filter(
                    organization=alert_group.channel.organization, channel_id=discord_message.channel_id
                ).first()
                client.update_thread(
                    thread_id=discord_message.thread_id,
                    applied_tags=channel.tag_ids_for(renderer.tag_names()) if channel else None,
                    archived=False,
                )
                client.update_message(
                    channel_id=discord_message.thread_id, message_id=discord_message.thread_id, data=payload
                )
            else:
                client.update_message(
                    channel_id=discord_message.channel_id, message_id=discord_message.message_id, data=payload
                )
        except DiscordAPITokenInvalid:
            logger.error(f"Discord bot token is invalid, could not update message for alert group {alert_group.pk}")
        except DiscordAPIException as ex:
            logger.error(f"Discord API error {ex}")
            if ex.status not in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]:
                raise ex

    @staticmethod
    def on_create_alert(**kwargs):
        on_create_alert_async.apply_async((kwargs["alert"],))

    @staticmethod
    def on_alert_group_action_triggered(**kwargs):
        from apps.alerts.models import AlertGroupLogRecord

        log_record = kwargs["log_record"]
        log_record_id = log_record.pk if isinstance(log_record, AlertGroupLogRecord) else log_record
        on_alert_group_action_triggered_async.apply_async((log_record_id,))

    def get_handler(self):
        handler_name = self.get_handler_name()
        logger.info(f"Using '{handler_name}' handler to process alert action in discord")
        return getattr(self, handler_name, None)

    def get_handler_name(self):
        return self.HANDLER_PREFIX + self.get_handler_map()[self.log_record.type]
