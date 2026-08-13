from rest_framework import serializers

from apps.base.messaging import BaseMessagingBackend
from apps.discord.models import DiscordChannel


class DiscordBackend(BaseMessagingBackend):
    """Discord as a routing destination.

    `available_for_use` stays False until a Discord account can be linked to an OnCall user, which is what a personal
    notification step would need; registering the backend already gives routes a Discord channel and alert templates a
    `discord` render target.
    """

    backend_id = "DISCORD"
    label = "Discord"
    short_label = "Discord"
    available_for_use = False
    templater = "apps.discord.alert_rendering.AlertDiscordTemplater"

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
