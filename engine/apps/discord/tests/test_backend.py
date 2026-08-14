import datetime
from unittest.mock import patch

import jwt
import pytest
from django.utils import timezone
from rest_framework import serializers

from apps.alerts.models import AlertReceiveChannel
from apps.base.models import UserNotificationPolicy, UserNotificationPolicyLogRecord
from apps.discord.backend import DiscordBackend
from apps.discord.exceptions import DiscordAPIException
from apps.discord.models import DiscordMessage, DiscordUser
from apps.discord.tasks import notify_user_about_alert_async
from apps.discord.utils import link_user


@pytest.fixture()
def make_notification(
    make_organization_and_user,
    make_alert_receive_channel,
    make_alert_group,
    make_alert,
    make_discord_message,
    make_user_notification_policy,
):
    def _make_notification():
        organization, user = make_organization_and_user()
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        make_discord_message(alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE)
        notification_policy = make_user_notification_policy(
            user=user,
            step=UserNotificationPolicy.Step.NOTIFY,
            notify_by=UserNotificationPolicy.NotificationChannel.TESTONLY,
        )
        return user, alert_group, notification_policy

    return _make_notification


@pytest.mark.django_db
def test_serialize_user(make_organization_and_user, make_discord_user):
    _, user = make_organization_and_user()
    assert DiscordBackend().serialize_user(user) is None

    discord_user = make_discord_user(user)
    assert DiscordBackend().serialize_user(user) == {
        "discord_user_id": discord_user.discord_user_id,
        "username": discord_user.username,
    }


@pytest.mark.django_db
def test_unlink_user(make_organization_and_user, make_discord_user):
    _, user = make_organization_and_user()
    make_discord_user(user)

    DiscordBackend().unlink_user(user)

    assert not DiscordUser.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_verification_code_links_the_account(make_organization_and_user):
    _, user = make_organization_and_user()
    code = DiscordBackend().generate_user_verification_code(user)

    discord_user = link_user(code=code, discord_user_id="1300000000000000042", username="responder")

    assert discord_user.user == user
    assert user.discord_user_identity.discord_user_id == "1300000000000000042"


@pytest.mark.django_db
def test_expired_verification_code_links_nothing(make_organization_and_user, settings):
    _, user = make_organization_and_user()
    expired = jwt.encode(
        {"user_id": user.public_primary_key, "exp": timezone.now() - datetime.timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    assert link_user(code=expired, discord_user_id="1300000000000000042", username="responder") is None


@pytest.mark.django_db
def test_garbage_verification_code_links_nothing(make_organization_and_user):
    assert link_user(code="not-a-code", discord_user_id="1300000000000000042", username="responder") is None


@pytest.mark.django_db
def test_notify_user_mentions_only_that_user(make_notification, make_discord_user):
    user, alert_group, notification_policy = make_notification()
    discord_user = make_discord_user(user)

    with patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        notify_user_about_alert_async(user.pk, alert_group.pk, notification_policy.pk)

    _, kwargs = create_message.call_args
    assert discord_user.mention_username in kwargs["data"]["content"]
    assert kwargs["data"]["allowed_mentions"] == {"parse": [], "users": [discord_user.discord_user_id]}
    assert kwargs["data"]["message_reference"]["message_id"] == alert_group.discord_messages.first().message_id
    assert (
        alert_group.personal_log_records.last().type
        == UserNotificationPolicyLogRecord.TYPE_PERSONAL_NOTIFICATION_SUCCESS
    )


@pytest.mark.django_db
def test_notify_user_in_a_forum_pings_inside_the_post(make_notification, make_discord_user):
    """Discord refuses a message addressed to a forum channel, so the ping has to go into the post itself."""
    user, alert_group, notification_policy = make_notification()
    make_discord_user(user)
    placement = alert_group.discord_messages.first()
    placement.thread_id = "1300000000000000777"
    placement.save(update_fields=["thread_id"])

    with patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        notify_user_about_alert_async(user.pk, alert_group.pk, notification_policy.pk)

    _, kwargs = create_message.call_args
    assert kwargs["channel_id"] == placement.thread_id
    # Inside the post there is nothing to quote: the card is the post.
    assert "message_reference" not in kwargs["data"]


@pytest.mark.django_db
def test_notify_unlinked_user_is_logged_as_failed(make_notification):
    user, alert_group, notification_policy = make_notification()

    with patch("apps.discord.tasks.DiscordClient.create_message") as create_message:
        notify_user_about_alert_async(user.pk, alert_group.pk, notification_policy.pk)

    assert create_message.call_args[1]["data"]["allowed_mentions"]["users"] == []
    log_record = alert_group.personal_log_records.first()
    assert log_record.type == UserNotificationPolicyLogRecord.TYPE_PERSONAL_NOTIFICATION_FAILED
    assert (
        log_record.notification_error_code
        == UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_USER_NOT_IN_DISCORD
    )


@pytest.mark.django_db
def test_notify_user_records_an_unauthorized_bot(make_notification, make_discord_user):
    user, alert_group, notification_policy = make_notification()
    make_discord_user(user)

    with patch(
        "apps.discord.tasks.DiscordClient.create_message",
        side_effect=DiscordAPIException(status=403, url="", msg="Missing Access", method="POST"),
    ):
        notify_user_about_alert_async(user.pk, alert_group.pk, notification_policy.pk)

    log_record = alert_group.personal_log_records.last()
    assert log_record.type == UserNotificationPolicyLogRecord.TYPE_PERSONAL_NOTIFICATION_FAILED
    assert (
        log_record.notification_error_code
        == UserNotificationPolicyLogRecord.ERROR_NOTIFICATION_IN_DISCORD_API_UNAUTHORIZED
    )


@pytest.mark.django_db
def test_relinking_an_account_moves_it_off_the_previous_user(make_organization_and_user, make_discord_user):
    _, previous = make_organization_and_user()
    _, current = make_organization_and_user()
    make_discord_user(previous, discord_user_id="1300000000000000042")

    link_user(
        code=DiscordBackend().generate_user_verification_code(current),
        discord_user_id="1300000000000000042",
        username="responder",
    )

    assert not DiscordUser.objects.filter(user=previous).exists()
    assert DiscordUser.objects.get(discord_user_id="1300000000000000042").user == current


@pytest.mark.django_db
@pytest.mark.parametrize("severity", ["critical", "warning", "info"])
def test_validate_channel_filter_severity(make_organization, severity):
    organization = make_organization()

    validated = DiscordBackend().validate_channel_filter_data(organization, {"severity": severity})

    assert validated == {"severity": severity}


@pytest.mark.django_db
def test_validate_channel_filter_rejects_an_unknown_severity(make_organization):
    organization = make_organization()

    with pytest.raises(serializers.ValidationError):
        DiscordBackend().validate_channel_filter_data(organization, {"severity": "catastrophe"})
