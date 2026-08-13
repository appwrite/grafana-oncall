from django.db import models

from apps.alerts.models import AlertGroup
from apps.discord.client import DiscordMessage as DiscordAPIMessage


class DiscordMessage(models.Model):
    (
        ALERT_GROUP_MESSAGE,
        LOG_MESSAGE,
    ) = range(2)

    DISCORD_MESSAGE_CHOICES = (
        (ALERT_GROUP_MESSAGE, "Alert group message"),
        (LOG_MESSAGE, "Log message"),
    )

    message_id = models.CharField(max_length=100)

    channel_id = models.CharField(max_length=100)

    message_type = models.IntegerField(choices=DISCORD_MESSAGE_CHOICES)

    alert_group = models.ForeignKey(
        "alerts.AlertGroup",
        on_delete=models.CASCADE,
        related_name="discord_messages",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["alert_group", "message_type", "channel_id"],
                name="unique_discord_alert_group_message_type_channel_id",
            )
        ]

        indexes = [
            models.Index(fields=["channel_id", "message_id"]),
        ]

    @staticmethod
    def create_message(alert_group: AlertGroup, message: DiscordAPIMessage, message_type: int) -> "DiscordMessage":
        return DiscordMessage.objects.create(
            alert_group=alert_group,
            message_id=message.message_id,
            channel_id=message.channel_id,
            message_type=message_type,
        )
