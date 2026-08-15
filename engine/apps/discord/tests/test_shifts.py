import datetime
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.discord.client import FORUM_CHANNEL
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
def test_forum_announcement_opens_a_post(make_schedule_with_shift, make_discord_channel, make_discord_user):
    """A forum channel takes posts, not messages, so an announcement there has to open one."""
    organization, user, schedule = make_schedule_with_shift()
    channel = make_discord_channel(organization=organization, is_default_channel=True, channel_type=FORUM_CHANNEL)
    discord_user = make_discord_user(user)

    with patch("apps.discord.shifts.DiscordClient.create_thread") as create_thread:
        with patch("apps.discord.shifts.DiscordClient.create_message") as create_message:
            announce_shift_starts_for_schedule(schedule.pk)

    create_message.assert_not_called()
    _, kwargs = create_thread.call_args
    assert kwargs["channel_id"] == channel.channel_id
    assert "Primary" in kwargs["name"]
    assert discord_user.mention_username in kwargs["data"]["content"]


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


def test_the_tasks_are_registered_by_autodiscovery():
    """Beat publishes a task by name, and a name the worker does not know is dropped with an error nobody reads.

    Autodiscovery imports each app's `tasks` module and nothing else, so this asks a fresh interpreter what the
    worker would end up with. Importing the module here instead would register the tasks and prove nothing.
    """
    program = (
        "import django; django.setup();"
        "from celery import current_app;"
        "current_app.loader.import_default_modules();"
        "print(' '.join(current_app.tasks))"
    )
    # The child reads DJANGO_SETTINGS_MODULE from the environment, the same as the worker does. pytest-django
    # leaves `settings.SETTINGS_MODULE` empty, so it is a fallback for a run that has no variable set, never an
    # override: putting its None in the environment is a TypeError before the child even starts.
    env = dict(os.environ)
    if not env.get("DJANGO_SETTINGS_MODULE") and settings.SETTINGS_MODULE:
        env["DJANGO_SETTINGS_MODULE"] = settings.SETTINGS_MODULE

    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, env=env)

    assert result.returncode == 0, result.stderr
    registered = set(result.stdout.split())
    assert "apps.discord.shifts.announce_shift_starts_for_all_schedules" in registered
    assert "apps.discord.shifts.announce_shift_starts_for_schedule" in registered
