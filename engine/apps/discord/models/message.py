import typing

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

    # Set when the alert group lives in a forum post rather than a channel message. A thread and its first message
    # share an id, so this is both the post and the message to edit inside it.
    thread_id = models.CharField(max_length=100, null=True, default=None)

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
    def create_message(
        alert_group: AlertGroup,
        message: DiscordAPIMessage,
        message_type: int,
        thread_id: typing.Optional[str] = None,
    ) -> "DiscordMessage":
        """Record where a message landed, idempotently.

        A task that posted and then failed on the way to writing this row is retried, and Discord answers the second
        post with the same message. Matching the uniqueness constraint here means that retry settles on the row it
        meant to write instead of raising against it.
        """
        discord_message, _ = DiscordMessage.objects.get_or_create(
            alert_group=alert_group,
            message_type=message_type,
            channel_id=message.channel_id,
            defaults={"message_id": message.message_id, "thread_id": thread_id},
        )
        return discord_message
