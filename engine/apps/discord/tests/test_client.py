import json

import pytest
import responses

from apps.discord.client import DISCORD_API_URL, NONCE_LIMIT, DiscordClient
from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid


@pytest.mark.django_db
@responses.activate
def test_create_message():
    responses.add(
        responses.POST,
        f"{DISCORD_API_URL}/channels/123/messages",
        json={"id": "456", "channel_id": "123"},
        status=200,
    )

    message = DiscordClient().create_message(channel_id="123", data={"embeds": []})

    assert message.message_id == "456"
    assert message.channel_id == "123"
    assert responses.calls[0].request.headers["Authorization"].startswith("Bot ")


@pytest.mark.django_db
@responses.activate
def test_update_message():
    responses.add(
        responses.PATCH,
        f"{DISCORD_API_URL}/channels/123/messages/456",
        json={"id": "456", "channel_id": "123"},
        status=200,
    )

    message = DiscordClient().update_message(channel_id="123", message_id="456", data={"embeds": []})

    assert message.message_id == "456"


@pytest.mark.django_db
@responses.activate
def test_get_channel():
    responses.add(
        responses.GET,
        f"{DISCORD_API_URL}/channels/123",
        json={"id": "123", "guild_id": "789", "name": "incidents"},
        status=200,
    )

    channel = DiscordClient().get_channel(channel_id="123")

    assert (channel.channel_id, channel.guild_id, channel.channel_name) == ("123", "789", "incidents")


@pytest.mark.django_db
@responses.activate
def test_api_error_carries_the_discord_message():
    responses.add(
        responses.POST,
        f"{DISCORD_API_URL}/channels/123/messages",
        json={"message": "Missing Access", "code": 50001},
        status=403,
    )

    with pytest.raises(DiscordAPIException) as exc:
        DiscordClient().create_message(channel_id="123", data={"embeds": []})

    assert exc.value.status == 403
    assert exc.value.msg == "Missing Access"


@pytest.mark.django_db
def test_missing_bot_token(settings):
    settings.DISCORD_BOT_TOKEN = None

    with pytest.raises(DiscordAPITokenInvalid):
        DiscordClient()


@pytest.mark.django_db
@responses.activate
def test_register_commands():
    from apps.discord.commands import LINK_COMMAND_NAME, register_commands

    responses.add(responses.GET, f"{DISCORD_API_URL}/applications/@me", json={"id": "999"}, status=200)
    responses.add(
        responses.PUT,
        f"{DISCORD_API_URL}/applications/999/commands",
        json=[{"id": "1", "name": LINK_COMMAND_NAME}],
        status=200,
    )

    assert [command["name"] for command in register_commands()] == [LINK_COMMAND_NAME]


@pytest.mark.django_db
@responses.activate
def test_create_message_with_a_nonce_asks_discord_to_deduplicate():
    responses.add(
        responses.POST,
        f"{DISCORD_API_URL}/channels/123/messages",
        json={"id": "456", "channel_id": "123"},
        status=200,
    )

    DiscordClient().create_message(channel_id="123", data={"embeds": []}, nonce="ag-IJL19VG5TWBEV")

    sent = json.loads(responses.calls[0].request.body)
    assert sent["nonce"] == "ag-IJL19VG5TWBEV"
    assert sent["enforce_nonce"] is True


@pytest.mark.django_db
@responses.activate
def test_a_long_nonce_is_cut_to_what_discord_accepts():
    responses.add(
        responses.POST,
        f"{DISCORD_API_URL}/channels/123/messages",
        json={"id": "456", "channel_id": "123"},
        status=200,
    )

    DiscordClient().create_message(channel_id="123", data={}, nonce="n" * 40)

    assert json.loads(responses.calls[0].request.body)["nonce"] == "n" * NONCE_LIMIT
