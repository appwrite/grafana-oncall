from rest_framework import serializers

from apps.base.messaging import BaseMessagingBackend
from apps.discord.models import DiscordChannel
from apps.discord.tasks import notify_user_about_alert_async


class DiscordBackend(BaseMessagingBackend):
    """Discord as a notification channel and a routing destination."""

    backend_id = "DISCORD"
    label = "Discord"
    short_label = "Discord"
    available_for_use = True
    templater = "apps.discord.alert_rendering.AlertDiscordTemplater"

    def generate_user_verification_code(self, user):
        from apps.discord.utils import create_verification_code

        return create_verification_code(user)

    def unlink_user(self, user):
        from apps.discord.models import DiscordUser

        DiscordUser.objects.get(user=user).delete()

    def serialize_user(self, user):
        discord_user = getattr(user, "discord_user_identity", None)
        if not discord_user:
            return None
        return {
            "discord_user_id": discord_user.discord_user_id,
            "username": discord_user.username,
        }

    def notify_user(self, user, alert_group, notification_policy):
        notify_user_about_alert_async.delay(
            user_pk=user.pk,
            alert_group_pk=alert_group.pk,
            notification_policy_pk=notification_policy.pk,
        )

    def validate_channel_filter_data(self, organization, data):
        notification_data = {}

        if not data:
            return notification_data

        if "enabled" in data:
            notification_data["enabled"] = bool(data["enabled"])

        if "channel" not in data:
            return notification_data

        # "channel" and "enabled" are treated separately to handle the channel being cleared while the flag stays on.
        if not data["channel"]:
            notification_data["channel"] = data["channel"]
            return notification_data

        channel = DiscordChannel.objects.filter(organization=organization, public_primary_key=data["channel"]).first()

        if not channel:
            raise serializers.ValidationError(["Invalid discord channel id"])

        notification_data["channel"] = channel.public_primary_key

        return notification_data
