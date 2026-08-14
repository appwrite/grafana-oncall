from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.alerts.models import AlertReceiveChannel
from apps.discord.client import DiscordMessage as DiscordAPIMessage
from apps.discord.exceptions import DiscordAPIException
from apps.discord.models import DiscordMessage
from apps.discord.tasks import on_create_alert_async


@pytest.fixture()
def make_alert_for_channel(make_organization, make_alert_receive_channel, make_alert_group, make_alert):
    def _make_alert_for_channel(organization=None):
        organization = organization or make_organization()
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
        alert = make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        return organization, alert_group, alert

    return _make_alert_for_channel


@pytest.mark.django_db
def test_on_create_alert_posts_and_records_the_message(make_organization, make_discord_channel, make_alert_for_channel):
    organization = make_organization()
    channel = make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, alert = make_alert_for_channel(organization)

    with patch(
        "apps.discord.tasks.DiscordClient.create_message",
        return_value=DiscordAPIMessage(message_id="1300000000000000001", channel_id=channel.channel_id),
    ) as create_message:
        on_create_alert_async(alert.pk)

    create_message.assert_called_once()
    message = alert_group.discord_messages.get(message_type=DiscordMessage.ALERT_GROUP_MESSAGE)
    assert message.message_id == "1300000000000000001"
    assert message.channel_id == channel.channel_id


@pytest.mark.django_db
def test_on_create_alert_without_a_channel_posts_nothing(make_alert_for_channel):
    _, alert_group, alert = make_alert_for_channel()

    with patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        on_create_alert_async(alert.pk)

    create_message.assert_not_called()
    assert not alert_group.discord_messages.exists()


@pytest.mark.django_db
def test_on_create_alert_skips_an_alert_group_already_posted(
    make_organization, make_discord_channel, make_alert_for_channel, make_discord_message
):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, alert = make_alert_for_channel(organization)
    make_discord_message(alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE)

    with patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        on_create_alert_async(alert.pk)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_on_create_alert_swallows_a_forbidden_channel(make_organization, make_discord_channel, make_alert_for_channel):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, alert = make_alert_for_channel(organization)

    with patch(
        "apps.discord.tasks.DiscordClient.create_message",
        side_effect=DiscordAPIException(status=403, url="", msg="Missing Access", method="POST"),
    ):
        on_create_alert_async(alert.pk)

    assert not alert_group.discord_messages.exists()


@pytest.mark.django_db
def test_on_create_alert_posts_once_while_another_task_holds_the_lock(
    make_organization, make_discord_channel, make_alert_for_channel
):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, alert = make_alert_for_channel(organization)

    with patch("apps.discord.tasks.task_lock") as lock, patch(
        "apps.discord.tasks.DiscordClient.create_message"
    ) as create_message:
        lock.return_value.__enter__.return_value = False
        on_create_alert_async(alert.pk)

    create_message.assert_not_called()
    assert not alert_group.discord_messages.exists()


@pytest.mark.django_db
def test_a_failed_record_write_does_not_post_a_second_card(
    make_organization, make_discord_channel, make_alert_for_channel
):
    """Discord accepted the message, then writing the placement row failed and celery retried the whole task."""
    organization = make_organization()
    channel = make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, alert = make_alert_for_channel(organization)
    posted = DiscordAPIMessage(message_id="1300000000000000001", channel_id=channel.channel_id)

    with patch("apps.discord.tasks.DiscordClient.create_message", return_value=posted) as create_message:
        with patch("apps.discord.tasks.DiscordMessage.create_message", side_effect=DatabaseError("connection lost")):
            with pytest.raises(DatabaseError):
                on_create_alert_async(alert.pk)

        # The retry. Discord answers it with the message it already has, because the nonce is the same.
        on_create_alert_async(alert.pk)

    assert alert_group.discord_messages.count() == 1
    assert alert_group.discord_messages.get().message_id == posted.message_id

    nonces = {call.kwargs["nonce"] for call in create_message.call_args_list}
    assert nonces == {f"ag-{alert_group.public_primary_key}"}


@pytest.mark.django_db
def test_recording_the_same_placement_twice_keeps_one_row(
    make_organization, make_discord_channel, make_alert_for_channel
):
    organization = make_organization()
    channel = make_discord_channel(organization=organization, is_default_channel=True)
    _, alert_group, _ = make_alert_for_channel(organization)
    posted = DiscordAPIMessage(message_id="1300000000000000001", channel_id=channel.channel_id)

    for _ in range(2):
        DiscordMessage.create_message(
            alert_group=alert_group, message=posted, message_type=DiscordMessage.ALERT_GROUP_MESSAGE
        )

    assert alert_group.discord_messages.count() == 1
