"""A resolution note lands beside the Discord card, the same place escalation pings go."""

from unittest.mock import patch

import pytest

from apps.alerts.models import AlertReceiveChannel, ResolutionNote
from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative
from apps.discord.client import DiscordMessage as DiscordAPIMessage
from apps.discord.exceptions import DiscordAPIException
from apps.discord.models import DiscordMessage, DiscordResolutionNoteMessage
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
            alert_group=alert_group,
            message_type=DiscordMessage.ALERT_GROUP_MESSAGE,
            channel_id=channel.channel_id,
            guild_id=channel.guild_id,
            thread_id=thread_id,
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

    assert alert_group.discord_permalink == f"https://discord.com/channels/{channel.guild_id}/{message.thread_id}"
    assert alert_group.permalinks["discord"] == alert_group.discord_permalink


@pytest.mark.django_db
def test_a_channel_permalink_points_at_the_card(posted_note):
    alert_group, _, message, channel = posted_note()

    assert alert_group.discord_permalink == (
        f"https://discord.com/channels/{channel.guild_id}/{message.channel_id}/{message.message_id}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("thread_id", [None, "1300000000000000009"])
def test_a_permalink_survives_channel_disconnection(posted_note, thread_id):
    alert_group, _, _, channel = posted_note(thread_id=thread_id)
    permalink = alert_group.discord_permalink

    channel.delete()

    assert alert_group.discord_permalink == permalink


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
    alert_group, note, message, _ = posted_note(thread_id="1300000000000000009")
    posted = DiscordAPIMessage(message_id="1300000000000000010", channel_id=message.thread_id)

    with patch(
        "apps.discord.alert_group_representative.DiscordClient.create_message", return_value=posted
    ) as create_message, patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread:
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
    assert DiscordResolutionNoteMessage.objects.get(resolution_note=note).message_id == posted.message_id


@pytest.mark.django_db
def test_a_note_in_a_text_channel_quotes_the_card(posted_note):
    alert_group, note, message, _ = posted_note()
    posted = DiscordAPIMessage(message_id="1300000000000000010", channel_id=message.channel_id)

    with patch(
        "apps.discord.alert_group_representative.DiscordClient.create_message", return_value=posted
    ) as create_message, patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread:
        AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)

    update_thread.assert_not_called()
    _, kwargs = create_message.call_args
    assert kwargs["channel_id"] == message.channel_id
    assert kwargs["data"]["message_reference"]["message_id"] == message.message_id


@pytest.mark.django_db
@pytest.mark.parametrize("thread_id", [None, "1300000000000000009"])
def test_an_edited_note_updates_the_existing_message_without_the_card_record(posted_note, thread_id):
    _, note, message, _ = posted_note(thread_id=thread_id)
    note_message = DiscordResolutionNoteMessage.objects.create(
        resolution_note=note,
        channel_id=message.thread_id or message.channel_id,
        message_id="1300000000000000010",
        thread_id=message.thread_id,
    )
    message.delete()
    note.message_text = "The queue recovered."
    note.save(update_fields=["message_text"])

    with patch("apps.discord.alert_group_representative.DiscordClient.update_message") as update_message, patch(
        "apps.discord.alert_group_representative.DiscordClient.create_message"
    ) as create_message, patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread:
        on_resolution_note_async(note.pk)

    create_message.assert_not_called()
    update_message.assert_called_once()
    assert update_message.call_args.kwargs["channel_id"] == note_message.channel_id
    assert "The queue recovered" in update_message.call_args.kwargs["data"]["embeds"][0]["description"]
    if thread_id:
        update_thread.assert_called_once_with(thread_id=thread_id, archived=False)
    else:
        update_thread.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("thread_id", [None, "1300000000000000009"])
@pytest.mark.parametrize("missing_remotely", [False, True])
def test_a_deleted_note_removes_the_existing_message(posted_note, thread_id, missing_remotely):
    alert_group, note, message, _ = posted_note(thread_id=thread_id)
    note_message = DiscordResolutionNoteMessage.objects.create(
        resolution_note=note,
        channel_id=message.thread_id or message.channel_id,
        message_id="1300000000000000010",
        thread_id=message.thread_id,
    )
    note.delete()
    note = ResolutionNote.objects_with_deleted.get(pk=note.pk)
    error = DiscordAPIException(status=404, url="unused", method="DELETE") if missing_remotely else None

    with patch(
        "apps.discord.alert_group_representative.DiscordClient.delete_message", side_effect=error
    ) as delete_message, patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread:
        AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)

    delete_message.assert_called_once_with(channel_id=note_message.channel_id, message_id=note_message.message_id)
    if thread_id:
        update_thread.assert_called_once_with(thread_id=thread_id, archived=False)
    else:
        update_thread.assert_not_called()
    assert not DiscordResolutionNoteMessage.objects.filter(pk=note_message.pk).exists()


@pytest.mark.django_db
def test_a_failed_note_deletion_is_retried(posted_note):
    alert_group, note, message, _ = posted_note()
    note_message = DiscordResolutionNoteMessage.objects.create(
        resolution_note=note,
        channel_id=message.channel_id,
        message_id="1300000000000000010",
    )
    note.delete()
    note = ResolutionNote.objects_with_deleted.get(pk=note.pk)
    error = DiscordAPIException(status=403, url="unused", method="DELETE")

    with patch("apps.discord.alert_group_representative.DiscordClient.delete_message", side_effect=error):
        with pytest.raises(DiscordAPIException):
            AlertGroupDiscordRepresentative.post_resolution_note(alert_group, note)

    assert DiscordResolutionNoteMessage.objects.filter(pk=note_message.pk).exists()


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
def test_the_task_retries_when_another_note_sync_holds_the_lock(posted_note):
    _, note, _, _ = posted_note()

    with patch("apps.discord.tasks.task_lock") as lock, patch(
        "apps.discord.alert_group_representative.AlertGroupDiscordRepresentative.post_resolution_note"
    ) as post_resolution_note:
        lock.return_value.__enter__.return_value = False
        with pytest.raises(RuntimeError):
            on_resolution_note_async(note.pk)

    post_resolution_note.assert_not_called()


@pytest.mark.django_db
def test_the_signal_queues_the_note_task(posted_note):
    _, note, _, _ = posted_note()

    with patch("apps.discord.alert_group_representative.on_resolution_note_async.apply_async") as apply_async:
        AlertGroupDiscordRepresentative.on_alert_group_update_resolution_note(
            alert_group=note.alert_group, resolution_note=note
        )

    apply_async.assert_called_once_with((note.pk,))
