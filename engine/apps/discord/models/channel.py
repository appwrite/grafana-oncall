import typing

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models, transaction

from apps.alerts.models import AlertGroup
from common.insight_log.chatops_insight_logs import ChatOpsEvent, ChatOpsTypePlug, write_chatops_insight_log
from common.public_primary_keys import generate_public_primary_key, increase_public_primary_key_length


def generate_public_primary_key_for_discord_channel():
    prefix = "DC"
    new_public_primary_key = generate_public_primary_key(prefix)

    failure_counter = 0
    while DiscordChannel.objects.filter(public_primary_key=new_public_primary_key).exists():
        new_public_primary_key = increase_public_primary_key_length(
            failure_counter=failure_counter, prefix=prefix, model_name="DiscordChannel"
        )
        failure_counter += 1

    return new_public_primary_key


class DiscordChannel(models.Model):
    organization = models.ForeignKey(
        "user_management.Organization",
        on_delete=models.CASCADE,
        related_name="discord_channels",
    )

    public_primary_key = models.CharField(
        max_length=20,
        validators=[MinLengthValidator(settings.PUBLIC_PRIMARY_KEY_MIN_LENGTH + 1)],
        unique=True,
        default=generate_public_primary_key_for_discord_channel,
    )

    guild_id = models.CharField(max_length=100)
    # A forum channel holds posts rather than messages, so an alert group becomes a thread there instead. Both of
    # these are nullable so that adding them takes no NOT NULL constraint to an existing table.
    channel_type = models.IntegerField(null=True, default=0)
    # The forum's tags as {name: id}, captured when the channel is connected. Re-connect the channel to pick up
    # tags added since.
    available_tags = models.JSONField(null=True, blank=True, default=dict)
    channel_id = models.CharField(max_length=100)
    channel_name = models.CharField(max_length=100, default=None)
    is_default_channel = models.BooleanField(null=True, default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "channel_id")

    @property
    def is_forum(self) -> bool:
        from apps.discord.client import FORUM_CHANNEL

        return self.channel_type == FORUM_CHANNEL

    def tag_ids_for(self, name: str) -> typing.Optional[list]:
        """The forum tag matching a card state, if the forum happens to have one by that name."""
        by_name = {key.casefold(): value for key, value in (self.available_tags or {}).items()}
        tag_id = by_name.get(name.casefold())
        return [tag_id] if tag_id else None

    @classmethod
    def get_channel_for_alert_group(cls, alert_group: AlertGroup) -> typing.Optional["DiscordChannel"]:
        from apps.discord.backend import DiscordBackend  # To avoid circular import

        default_channel = cls.objects.filter(
            organization=alert_group.channel.organization, is_default_channel=True
        ).first()

        if (
            alert_group.channel_filter is None
            or not alert_group.channel_filter.notification_backends
            or not alert_group.channel_filter.notification_backends.get(DiscordBackend.backend_id)
        ):
            return default_channel

        backend_data = alert_group.channel_filter.notification_backends[DiscordBackend.backend_id]

        if not backend_data.get("enabled"):
            return None

        channel_id = backend_data.get("channel")
        if not channel_id:
            return default_channel

        channel = cls.objects.filter(
            organization=alert_group.channel.organization, public_primary_key=channel_id
        ).first()

        return channel or default_channel

    def make_channel_default(self, author):
        old_default_channel = DiscordChannel.objects.filter(
            organization=self.organization, is_default_channel=True
        ).first()

        self.is_default_channel = True
        with transaction.atomic():
            if old_default_channel:
                old_default_channel.is_default_channel = False
                old_default_channel.save(update_fields=["is_default_channel"])
            self.save(update_fields=["is_default_channel"])

        write_chatops_insight_log(
            author=author,
            event_name=ChatOpsEvent.DEFAULT_CHANNEL_CHANGED,
            chatops_type=ChatOpsTypePlug.DISCORD.value,
            prev_channel=old_default_channel.channel_name if old_default_channel else None,
            new_channel=self.channel_name,
        )
