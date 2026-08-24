"""A resolution note lands beside the Discord card, the same place escalation pings go."""

from unittest.mock import patch

import pytest

from apps.alerts.models import AlertReceiveChannel, ResolutionNote
from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative
from apps.discord.models import DiscordMessage
from apps.discord.tasks import on_resolution_note_async


@pytest.fixture()
def posted_note(
    make_organization,
    make_user_for_organization,
    make_discord_channel,
    make_alert_receive_channel,
    make_alert_group,
    make_alert,
    make_discord_message,
    make_resolution_note,
):
    def _posted_note(thread_id=None, deleted=False, **channel_kwargs):
        organization = make_organization()
        user = make_user_for_organization(organization, username="investigator")
        channel = make_discord_channel(
            organization=organization, is_default_channel=True, guild_id="1300000000000000100", **channel_kwargs
        )
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        message = make_discord_message(
            alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE, thread_id=thread_id
        )
        note = make_resolution_note(
            alert_group=alert_group,
            source=ResolutionNote.Source.WEB,
            author=user,
            message_text="Subject: the queue waits.\n\nWhat started it: depth stayed high for 15 minutes.",
        )
        if deleted:
            note.delete()
            note = ResolutionNote.objects_with_deleted.get(pk=note.pk)
        return alert_group, note, message, channel

    return _posted_note


@pytest.mark.django_db
def test_a_forum_permalink_is_the_post(posted_note):
    alert_group, _, message, channel = posted_note(thread_id="1300000000000000009")

    assert (
        alert_group.discord_permalink
        == f"https://discord.com/channels/{channel.guild_id}/{message.thread_id}"
    )
    assert alert_group.permalinks["discord"] == alert_group.discord_permalink


@pytest.mark.django_db
def test_a_channel_permalink_points_at_the_card(posted_note):
    alert_group, _, message, channel = posted_note()

    assert alert_group.discord_permalink == (
        f"https://discord.com/channels/{channel.guild_id}/{message.channel_id}/{message.message_id}"
    )


@pytest.mark.django_db
def test_permalinks_are_empty_without_a_card(
    make_organization, make_discord_channel, make_alert_receive_channel, make_alert_group
):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    alert_receive_channel = make_alert_receive_channel(organization)
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)

    assert alert_group.discord_permalink is None
    assert alert_group.permalinks["discord"] is None


@pytest.mark.django_db
def test_a_note_in_a_forum_post_needs_no_reply(posted_note):
    alert_group, note, _, _ = posted_note(thread_id="1300000000000000009")

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message, patch(
        "apps.discord.alert_group_representative.DiscordClient.update_thread"
    ) as update_thread:
        AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)

    update_thread.assert_called_once_with(thread_id="1300000000000000009", archived=False)
    _, kwargs = create_message.call_args
    assert kwargs["channel_id"] == "1300000000000000009"
    assert "message_reference" not in kwargs["data"]
    assert kwargs["data"]["embeds"][0]["title"] == "Investigation"
    assert "the queue waits" in kwargs["data"]["embeds"][0]["description"]
    assert kwargs["data"]["embeds"][0]["footer"]["text"] == "Note from investigator"
    assert kwargs["data"]["allowed_mentions"] == {"parse": []}
    assert kwargs["nonce"] == f"rn-{note.pk}"


@pytest.mark.django_db
def test_a_note_in_a_text_channel_quotes_the_card(posted_note):
    alert_group, note, message, _ = posted_note()

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message, patch(
        "apps.discord.alert_group_representative.DiscordClient.update_thread"
    ) as update_thread:
        AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)

    update_thread.assert_not_called()
    _, kwargs = create_message.call_args
    assert kwargs["channel_id"] == message.channel_id
    assert kwargs["data"]["message_reference"]["message_id"] == message.message_id


@pytest.mark.django_db
def test_a_deleted_note_is_not_posted(posted_note):
    alert_group, note, _, _ = posted_note(deleted=True)

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)
        on_resolution_note_async(note.pk)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_the_task_retries_until_the_card_exists(
    make_organization,
    make_user_for_organization,
    make_discord_channel,
    make_alert_receive_channel,
    make_alert_group,
    make_resolution_note,
):
    organization = make_organization()
    user = make_user_for_organization(organization)
    make_discord_channel(organization=organization, is_default_channel=True)
    alert_receive_channel = make_alert_receive_channel(organization)
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    note = make_resolution_note(alert_group=alert_group, source=ResolutionNote.Source.WEB, author=user)

    with pytest.raises(DiscordMessage.DoesNotExist):
        on_resolution_note_async(note.pk)


@pytest.mark.django_db
def test_the_signal_queues_the_note_task(posted_note):
    _, note, _, _ = posted_note()

    with patch("apps.discord.alert_group_representative.on_resolution_note_async.apply_async") as apply_async:
        AlertGroupDiscordRepresentative.on_alert_group_update_resolution_note(
            alert_group=note.alert_group, resolution_note=note
        )

    apply_async.assert_called_once_with((note.pk,))
