from rest_framework import serializers

from apps.discord.client import DiscordClient
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid
from apps.discord.models import DiscordChannel
from common.api_helpers.exceptions import BadRequest
from common.api_helpers.utils import CurrentOrganizationDefault


class DiscordChannelSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True, source="public_primary_key")
    organization = serializers.HiddenField(default=CurrentOrganizationDefault())

    class Meta:
        model = DiscordChannel
        fields = [
            "id",
            "organization",
            "guild_id",
            "channel_id",
            "channel_name",
            "channel_type",
            "available_tags",
            "is_default_channel",
        ]
        extra_kwargs = {
            "guild_id": {"required": True, "write_only": True},
            "available_tags": {"write_only": True},
            "channel_id": {"required": True},
        }

    def create(self, validated_data):
        return DiscordChannel.objects.create(**validated_data)

    def to_internal_value(self, data):
        channel_id = data.get("channel_id")

        if not channel_id:
            raise serializers.ValidationError({"channel_id": "This field is required."})

        try:
            channel = DiscordClient().get_channel(channel_id=channel_id)
        except DiscordAPIException as ex:
            raise BadRequest(detail=ex.msg)
        except DiscordAPITokenInvalid:
            raise BadRequest(detail="Discord bot token is invalid.")

        return super().to_internal_value(
            {
                "channel_id": channel.channel_id,
                "guild_id": channel.guild_id,
                "channel_name": channel.channel_name,
                "channel_type": channel.channel_type,
                "available_tags": channel.available_tags or {},
            }
        )
