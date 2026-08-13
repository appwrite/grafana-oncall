import logging

from rest_framework import status

from apps.alerts.models import AlertGroup
from apps.alerts.representative import AlertGroupAbstractRepresentative
from apps.discord.alert_rendering import DiscordMessageRenderer
from apps.discord.client import DiscordClient
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid
from apps.discord.tasks import on_alert_group_action_triggered_async, on_create_alert_async

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
        }

    def on_alert_group_action(self, alert_group: AlertGroup):
        logger.info(f"Update discord message for alert_group {alert_group.pk}")
        payload = DiscordMessageRenderer(alert_group).render_alert_group_message()
        discord_message = alert_group.discord_messages.order_by("created_at").first()
        try:
            DiscordClient().update_message(
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
