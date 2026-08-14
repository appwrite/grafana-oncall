from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.alerts.models import AlertGroupLogRecord, AlertReceiveChannel
from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative
from apps.discord.models import DiscordMessage


@pytest.fixture()
def make_acknowledged_log_record(
    make_organization, make_alert_receive_channel, make_alert_group, make_alert, make_alert_group_log_record
):
    def _make_acknowledged_log_record(organization=None):
        organization = organization or make_organization()
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(
            alert_receive_channel=alert_receive_channel, acknowledged=True, acknowledged_at=timezone.now()
        )
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        return alert_group, make_alert_group_log_record(alert_group, type=AlertGroupLogRecord.TYPE_ACK, author=None)

    return _make_acknowledged_log_record


@pytest.mark.django_db
def test_is_applicable_needs_a_channel(make_organization, make_discord_channel, make_acknowledged_log_record):
    organization = make_organization()
    _, log_record = make_acknowledged_log_record(organization)
    assert not AlertGroupDiscordRepresentative(log_record=log_record).is_applicable()

    make_discord_channel(organization=organization, is_default_channel=True)
    assert AlertGroupDiscordRepresentative(log_record=log_record).is_applicable()


@pytest.mark.django_db
def test_is_applicable_ignores_unhandled_log_record_types(
    make_organization, make_discord_channel, make_alert_receive_channel, make_alert_group, make_alert_group_log_record
):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    alert_receive_channel = make_alert_receive_channel(organization)
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    log_record = make_alert_group_log_record(alert_group, type=AlertGroupLogRecord.TYPE_DELETED, author=None)

    assert not AlertGroupDiscordRepresentative(log_record=log_record).is_applicable()


@pytest.mark.django_db
def test_alert_group_action_edits_the_posted_message(
    make_organization, make_discord_channel, make_acknowledged_log_record, make_discord_message
):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    alert_group, log_record = make_acknowledged_log_record(organization)
    message = make_discord_message(alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE)

    representative = AlertGroupDiscordRepresentative(log_record=log_record)
    assert representative.get_handler().__name__ == "on_alert_group_action"

    with patch("apps.discord.alert_group_representative.DiscordClient.update_message") as update_message:
        representative.get_handler()(alert_group)

    _, kwargs = update_message.call_args
    assert kwargs["message_id"] == message.message_id
    assert kwargs["channel_id"] == message.channel_id
    assert kwargs["data"]["embeds"][0]["title"].startswith("🟡")
