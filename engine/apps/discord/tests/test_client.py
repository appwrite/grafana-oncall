import json

import pytest
import responses

from apps.discord.client import DISCORD_API_URL, FORUM_CHANNEL, NONCE_LIMIT, THREAD_NAME_LIMIT, DiscordClient
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
def test_delete_message():
    responses.add(responses.DELETE, f"{DISCORD_API_URL}/channels/123/messages/456", status=204)

    DiscordClient().delete_message(channel_id="123", message_id="456")

    assert len(responses.calls) == 1


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
def test_get_channel_reads_a_forum_and_its_tags():
    responses.add(
        responses.GET,
        f"{DISCORD_API_URL}/channels/123",
        json={
            "id": "123",
            "guild_id": "789",
            "name": "incidents",
            "type": FORUM_CHANNEL,
            "available_tags": [{"id": "111", "name": "Firing"}, {"id": "222", "name": "Resolved"}],
        },
        status=200,
    )

    channel = DiscordClient().get_channel(channel_id="123")

    assert channel.is_forum
    assert channel.available_tags == {"Firing": "111", "Resolved": "222"}


@pytest.mark.django_db
@responses.activate
def test_create_thread_opens_a_post_carrying_the_card():
    responses.add(
        responses.POST,
        f"{DISCORD_API_URL}/channels/123/threads",
        json={"id": "456"},
        status=200,
    )

    posted = DiscordClient().create_thread(
        channel_id="123", name="DiskSpaceLow · #12", data={"embeds": []}, applied_tags=["111"]
    )

    sent = json.loads(responses.calls[0].request.body)
    assert sent["name"] == "DiskSpaceLow · #12"
    assert sent["applied_tags"] == ["111"]
    assert sent["message"] == {"embeds": []}
    # A thread and its first message share an id.
    assert posted.message_id == posted.channel_id == "456"


@pytest.mark.django_db
@responses.activate
def test_a_long_post_name_is_cut_to_what_discord_accepts():
    responses.add(responses.POST, f"{DISCORD_API_URL}/channels/123/threads", json={"id": "456"}, status=200)

    DiscordClient().create_thread(channel_id="123", name="n" * 200, data={})

    assert json.loads(responses.calls[0].request.body)["name"] == "n" * THREAD_NAME_LIMIT


def register_threads(*threads):
    responses.add(
        responses.GET, f"{DISCORD_API_URL}/guilds/789/threads/active", json={"threads": list(threads)}, status=200
    )
    responses.add(
        responses.GET,
        f"{DISCORD_API_URL}/channels/123/threads/archived/public",
        json={"threads": []},
        status=200,
    )


def register_card(thread_id, alert_group):
    responses.add(
        responses.GET,
        f"{DISCORD_API_URL}/channels/{thread_id}/messages/{thread_id}",
        json={
            "id": thread_id,
            "components": [{"type": 1, "components": [{"type": 2, "custom_id": f"oncall:acknowledge:{alert_group}"}]}],
        },
        status=200,
    )


@pytest.mark.django_db
@responses.activate
def test_find_thread_for_matches_the_post_whose_card_acts_on_the_alert_group():
    """Two posts share a name — a long title truncates the same way — so the buttons decide which is which."""
    register_threads(
        {"id": "900", "parent_id": "123", "name": "DiskSpaceLow · #1"},
        {"id": "901", "parent_id": "123", "name": "DiskSpaceLow · #1"},
    )
    register_card("900", "IOTHERGROUP")
    register_card("901", "IWANTEDGROUP")

    found = DiscordClient().find_thread_for(
        guild_id="789", channel_id="123", name="DiskSpaceLow · #1", marker="IWANTEDGROUP"
    )

    assert found == "901"


@pytest.mark.django_db
@responses.activate
def test_find_thread_for_refuses_another_alert_groups_post():
    register_threads({"id": "900", "parent_id": "123", "name": "DiskSpaceLow · #1"})
    register_card("900", "IOTHERGROUP")

    found = DiscordClient().find_thread_for(
        guild_id="789", channel_id="123", name="DiskSpaceLow · #1", marker="IWANTEDGROUP"
    )

    assert found is None


@pytest.mark.django_db
@responses.activate
def test_find_thread_for_ignores_posts_in_another_channel():
    register_threads({"id": "900", "parent_id": "456", "name": "DiskSpaceLow · #1"})

    found = DiscordClient().find_thread_for(
        guild_id="789", channel_id="123", name="DiskSpaceLow · #1", marker="IWANTEDGROUP"
    )

    assert found is None


@pytest.mark.django_db
@responses.activate
def test_update_thread_sets_tags_and_unarchives():
    responses.add(responses.PATCH, f"{DISCORD_API_URL}/channels/456", json={"id": "456"}, status=200)

    DiscordClient().update_thread(thread_id="456", applied_tags=["222"], archived=False)

    assert json.loads(responses.calls[0].request.body) == {"archived": False, "applied_tags": ["222"]}


@pytest.mark.django_db
@responses.activate
def test_update_thread_leaves_tags_alone_when_there_is_no_match():
    responses.add(responses.PATCH, f"{DISCORD_API_URL}/channels/456", json={"id": "456"}, status=200)

    DiscordClient().update_thread(thread_id="456", applied_tags=None)

    assert json.loads(responses.calls[0].request.body) == {"archived": False}


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
