"""A forum channel makes each alert group its own post, so discussion lands beside the card."""

from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.alerts.models import AlertGroupLogRecord, AlertReceiveChannel
from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative
from apps.discord.client import FORUM_CHANNEL
from apps.discord.client import DiscordMessage as DiscordAPIMessage
from apps.discord.models import DiscordMessage
from apps.discord.tasks import on_create_alert_async

TAGS = {"Alert": "111", "Acknowledged": "222", "Resolved": "333"}


@pytest.fixture()
def make_forum(make_organization, make_user_for_organization, make_discord_channel):
    def _make_forum(available_tags=None):
        organization = make_organization()
        make_user_for_organization(organization, username="loks0n")
        channel = make_discord_channel(
            organization=organization,
            is_default_channel=True,
            channel_type=FORUM_CHANNEL,
            available_tags=TAGS if available_tags is None else available_tags,
        )
        return organization, channel

    return _make_forum


@pytest.fixture()
def make_alert_for(make_alert_receive_channel, make_alert_group, make_alert):
    def _make_alert_for(organization, **alert_group_kwargs):
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, **alert_group_kwargs)
        alert = make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        return alert_group, alert

    return _make_alert_for


@pytest.mark.django_db
def test_an_alert_group_becomes_a_forum_post(make_forum, make_alert_for):
    organization, channel = make_forum()
    alert_group, alert = make_alert_for(organization)

    with patch(
        "apps.discord.tasks.DiscordClient.create_thread",
        return_value=DiscordAPIMessage(message_id="1300000000000000009", channel_id="1300000000000000009"),
    ) as create_thread, patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        on_create_alert_async(alert.pk)

    create_message.assert_not_called()
    _, kwargs = create_thread.call_args
    assert kwargs["channel_id"] == channel.channel_id
    assert kwargs["name"].endswith(f"#{alert_group.inside_organization_number}")
    assert kwargs["applied_tags"] == ["111"]
    assert kwargs["data"]["embeds"]

    # The post is the message: a thread and its first message share an id, and the placement remembers the forum it
    # belongs to so its tags can be found again.
    placement = alert_group.discord_messages.get()
    assert placement.thread_id == "1300000000000000009"
    assert placement.message_id == "1300000000000000009"
    assert placement.channel_id == channel.channel_id


@pytest.mark.django_db
def test_a_forum_without_matching_tags_still_posts(make_forum, make_alert_for):
    organization, _ = make_forum(available_tags={"Something else": "999"})
    _, alert = make_alert_for(organization)

    with patch(
        "apps.discord.tasks.DiscordClient.create_thread",
        return_value=DiscordAPIMessage(message_id="1300000000000000009", channel_id="1300000000000000009"),
    ) as create_thread:
        on_create_alert_async(alert.pk)

    assert create_thread.call_args[1]["applied_tags"] is None


@pytest.mark.django_db
def test_a_text_channel_still_gets_a_plain_message(
    make_organization, make_user_for_organization, make_discord_channel, make_alert_for
):
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    channel = make_discord_channel(organization=organization, is_default_channel=True)
    alert_group, alert = make_alert_for(organization)

    with patch(
        "apps.discord.tasks.DiscordClient.create_message",
        return_value=DiscordAPIMessage(message_id="1300000000000000001", channel_id=channel.channel_id),
    ), patch("apps.discord.tasks.DiscordClient.create_thread") as create_thread:
        on_create_alert_async(alert.pk)

    create_thread.assert_not_called()
    assert alert_group.discord_messages.get().thread_id is None


def run_as_retry(task, *args, retries):
    """Run the task the way celery runs it on a retry, so `self.request.retries` is what the code reads."""
    return task.apply(args=args, retries=retries, throw=True)


@pytest.mark.django_db
def test_a_retry_adopts_the_post_a_dead_attempt_already_opened(make_forum, make_alert_for):
    """Discord opened the post, the worker died before recording it, and celery retried the task."""
    organization, _ = make_forum()
    alert_group, alert = make_alert_for(organization)

    with patch("apps.discord.tasks.DiscordClient.find_thread_for", return_value="1300000000000000009") as find, patch(
        "apps.discord.tasks.DiscordClient.create_thread"
    ) as create_thread:
        run_as_retry(on_create_alert_async, alert.pk, retries=1)

    create_thread.assert_not_called()
    find.assert_called_once()
    assert alert_group.discord_messages.get().thread_id == "1300000000000000009"


@pytest.mark.django_db
def test_a_retry_with_nothing_to_adopt_opens_the_post(make_forum, make_alert_for):
    organization, _ = make_forum()
    alert_group, alert = make_alert_for(organization)

    with patch("apps.discord.tasks.DiscordClient.find_thread_for", return_value=None), patch(
        "apps.discord.tasks.DiscordClient.create_thread",
        return_value=DiscordAPIMessage(message_id="1300000000000000010", channel_id="1300000000000000010"),
    ) as create_thread:
        run_as_retry(on_create_alert_async, alert.pk, retries=2)

    create_thread.assert_called_once()
    assert alert_group.discord_messages.get().thread_id == "1300000000000000010"


@pytest.mark.django_db
def test_the_first_attempt_does_not_go_looking(make_forum, make_alert_for):
    """The duplicate only exists after a retry, so the common path pays nothing for it."""
    organization, _ = make_forum()
    _, alert = make_alert_for(organization)

    with patch("apps.discord.tasks.DiscordClient.find_thread_for") as find, patch(
        "apps.discord.tasks.DiscordClient.create_thread",
        return_value=DiscordAPIMessage(message_id="1300000000000000011", channel_id="1300000000000000011"),
    ):
        on_create_alert_async(alert.pk)

    find.assert_not_called()


@pytest.fixture()
def acknowledge(make_alert_group_log_record):
    def _acknowledge(alert_group):
        alert_group.acknowledged = True
        alert_group.acknowledged_at = timezone.now()
        alert_group.save()
        log_record = make_alert_group_log_record(alert_group, type=AlertGroupLogRecord.TYPE_ACK, author=None)
        return AlertGroupDiscordRepresentative(log_record=log_record)

    return _acknowledge


@pytest.mark.django_db
def test_updating_a_post_unarchives_and_retags_it_first(make_forum, make_alert_for, make_discord_message, acknowledge):
    organization, channel = make_forum()
    alert_group, _ = make_alert_for(organization)
    make_discord_message(
        alert_group=alert_group,
        message_type=DiscordMessage.ALERT_GROUP_MESSAGE,
        channel_id=channel.channel_id,
        message_id="1300000000000000009",
        thread_id="1300000000000000009",
    )
    representative = acknowledge(alert_group)

    with patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread, patch(
        "apps.discord.alert_group_representative.DiscordClient.update_message"
    ) as update_message:
        representative.get_handler()(alert_group)

    # Discord refuses an edit to an archived post, so unarchiving happens in the same call that retags it.
    assert update_thread.call_args[1] == {
        "thread_id": "1300000000000000009",
        "applied_tags": ["222"],
        "archived": False,
    }
    assert update_message.call_args[1]["channel_id"] == "1300000000000000009"
    assert update_message.call_args[1]["message_id"] == "1300000000000000009"


@pytest.mark.django_db
def test_updating_a_channel_message_touches_no_thread(
    make_organization,
    make_user_for_organization,
    make_discord_channel,
    make_alert_for,
    make_discord_message,
    acknowledge,
):
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    make_discord_channel(organization=organization, is_default_channel=True)
    alert_group, _ = make_alert_for(organization)
    message = make_discord_message(alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE)
    representative = acknowledge(alert_group)

    with patch("apps.discord.alert_group_representative.DiscordClient.update_thread") as update_thread, patch(
        "apps.discord.alert_group_representative.DiscordClient.update_message"
    ) as update_message:
        representative.get_handler()(alert_group)

    update_thread.assert_not_called()
    assert update_message.call_args[1]["message_id"] == message.message_id
