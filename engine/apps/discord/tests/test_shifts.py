import datetime
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.discord.exceptions import DiscordAPIException
from apps.discord.shifts import announce_shift_starts_for_all_schedules, announce_shift_starts_for_schedule
from apps.schedules.models import CustomOnCallShift, OnCallScheduleWeb


@pytest.fixture()
def make_schedule_with_shift(make_organization, make_user_for_organization, make_schedule, make_on_call_shift):
    def _make_schedule_with_shift(started_minutes_ago=5, **user_kwargs):
        organization = make_organization()
        user = make_user_for_organization(organization, **user_kwargs)
        schedule = make_schedule(organization, schedule_class=OnCallScheduleWeb, name="Primary")
        start = (timezone.now() - datetime.timedelta(minutes=started_minutes_ago)).replace(microsecond=0)
        on_call_shift = make_on_call_shift(
            organization=organization,
            shift_type=CustomOnCallShift.TYPE_ROLLING_USERS_EVENT,
            schedule=schedule,
            start=start,
            rotation_start=start,
            duration=datetime.timedelta(hours=8),
            priority_level=1,
        )
        on_call_shift.add_rolling_users([[user]])
        return organization, user, schedule

    return _make_schedule_with_shift


@pytest.fixture(autouse=True)
def clear_announcement_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_shift_start_is_announced_once(make_schedule_with_shift, make_discord_channel, make_discord_user):
    organization, user, schedule = make_schedule_with_shift()
    channel = make_discord_channel(organization=organization, is_default_channel=True)
    discord_user = make_discord_user(user)

    with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
        announce_shift_starts_for_schedule(schedule.pk)
        announce_shift_starts_for_schedule(schedule.pk)

    create_message.assert_called_once()
    _, kwargs = create_message.call_args
    assert kwargs["channel_id"] == channel.channel_id
    assert discord_user.mention_username in kwargs["data"]["content"]
    assert "Primary" in kwargs["data"]["content"]
    assert kwargs["data"]["allowed_mentions"] == {"parse": [], "users": [discord_user.discord_user_id]}


@pytest.mark.django_db
def test_unlinked_user_is_named_but_not_pinged(make_schedule_with_shift, make_discord_channel):
    organization, user, schedule = make_schedule_with_shift()
    make_discord_channel(organization=organization, is_default_channel=True)

    with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
        announce_shift_starts_for_schedule(schedule.pk)

    data = create_message.call_args[1]["data"]
    assert user.username in data["content"]
    assert data["allowed_mentions"]["users"] == []


@pytest.mark.django_db
def test_shift_that_started_before_the_window_is_not_announced(make_schedule_with_shift, make_discord_channel):
    organization, _, schedule = make_schedule_with_shift(started_minutes_ago=120)
    make_discord_channel(organization=organization, is_default_channel=True)

    with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
        announce_shift_starts_for_schedule(schedule.pk)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_no_default_channel_announces_nothing(make_schedule_with_shift, make_discord_channel):
    organization, _, schedule = make_schedule_with_shift()
    make_discord_channel(organization=organization)

    with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
        announce_shift_starts_for_schedule(schedule.pk)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_failed_announcement_is_retried_on_the_next_run(make_schedule_with_shift, make_discord_channel):
    organization, _, schedule = make_schedule_with_shift()
    make_discord_channel(organization=organization, is_default_channel=True)

    with patch("apps.discord.shifts.DiscordClient.create_message", side_effect=DiscordAPIException(500, "", "boom")):
        with pytest.raises(DiscordAPIException):
            announce_shift_starts_for_schedule(schedule.pk)

    with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
        announce_shift_starts_for_schedule(schedule.pk)

    create_message.assert_called_once()


@pytest.mark.django_db
def test_fan_out_skips_organizations_without_a_channel(make_schedule_with_shift, make_discord_channel):
    make_schedule_with_shift()

    with patch("apps.discord.shifts.announce_shift_starts_for_schedule.apply_async") as apply_async:
        announce_shift_starts_for_all_schedules()
    apply_async.assert_not_called()

    organization, _, schedule = make_schedule_with_shift()
    make_discord_channel(organization=organization, is_default_channel=True)

    with patch("apps.discord.shifts.announce_shift_starts_for_schedule.apply_async") as apply_async:
        announce_shift_starts_for_all_schedules()
    assert (schedule.pk,) in [call.args[0] for call in apply_async.call_args_list]
