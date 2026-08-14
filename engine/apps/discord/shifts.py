"""Announce on-call shift starts in Discord.

OnCall computes who is on call — `OnCallSchedule.final_events` already resolves rotations, overrides and swaps — so
this only has to notice a shift that has just begun and say so once. Announcing starts rather than ends is deliberate:
in a follow-the-sun rota every shift ending coincides with another starting, so "ended" messages are pure noise.
"""

import datetime
import logging

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.discord.client import DiscordClient
from apps.discord.exceptions import DiscordAPITokenInvalid
from apps.discord.models import DiscordChannel
from apps.schedules.models.on_call_schedule import OnCallSchedule, ScheduleEvent
from apps.user_management.models import User
from common.cache import ensure_cache_key_allocates_to_the_same_hash_slot
from common.custom_celery_tasks import shared_dedicated_queue_retry_task

logger = get_task_logger(__name__)
logger.setLevel(logging.DEBUG)

# How far back a run looks for shifts that have started. Wider than the beat interval so a skipped run still
# announces, a little late, rather than not at all; the cache key is what keeps it from announcing twice.
ANNOUNCEMENT_WINDOW = datetime.timedelta(minutes=15)
ANNOUNCED_CACHE_TTL = 60 * 60


def _cache_key(schedule: OnCallSchedule, event: ScheduleEvent) -> str:
    KEY_PREFIX = "discord_shift_announcement"
    return ensure_cache_key_allocates_to_the_same_hash_slot(
        f"{KEY_PREFIX}:{schedule.public_primary_key}:{event['shift']['pk']}:{event['start'].isoformat()}", KEY_PREFIX
    )


def _mentions(event: ScheduleEvent) -> tuple:
    """Who to name, and the Discord ids allowed to be pinged by naming them.

    A user with no linked Discord account is named in plain text rather than skipped: the shift is theirs whether or
    not OnCall can reach them here.
    """
    names, user_ids = [], []
    for event_user in event["users"]:
        user = User.objects.filter(public_primary_key=event_user["pk"]).first()
        discord_user = getattr(user, "discord_user_identity", None) if user else None
        if discord_user:
            names.append(discord_user.mention_username)
            user_ids.append(discord_user.discord_user_id)
        else:
            names.append(event_user["display_name"])
    return ", ".join(names), user_ids


@shared_dedicated_queue_retry_task(
    autoretry_for=(Exception,), retry_backoff=True, max_retries=1 if settings.DEBUG else None
)
def announce_shift_starts_for_schedule(schedule_pk) -> None:
    try:
        schedule = OnCallSchedule.objects.get(pk=schedule_pk)
    except OnCallSchedule.DoesNotExist:
        logger.info(f"Tried to announce shift starts for non-existing schedule {schedule_pk}")
        return

    channel = DiscordChannel.objects.filter(organization=schedule.organization, is_default_channel=True).first()
    if not channel:
        return

    now = timezone.now()
    window_start = now - ANNOUNCEMENT_WINDOW
    events = schedule.final_events(window_start, now, with_empty=False, with_gap=False)

    for event in events:
        # `final_events` returns everything overlapping the window, including shifts that began before it.
        if not window_start <= event["start"] <= now:
            continue

        cache_key = _cache_key(schedule, event)
        if cache.get(cache_key):
            continue

        names, user_ids = _mentions(event)
        if not names:
            continue

        payload = {
            "content": f"📅 {names} — your **{schedule.name}** on-call shift just started.",
            # A schedule name is user-supplied text, so only the users going on call may be pinged.
            "allowed_mentions": {"parse": [], "users": user_ids},
        }

        try:
            if channel.is_forum:
                # A forum channel takes posts, not messages, so the announcement becomes a post of its own.
                DiscordClient().create_thread(
                    channel_id=channel.channel_id,
                    name=f"📅 {schedule.name} — shift change",
                    data=payload,
                )
            else:
                DiscordClient().create_message(channel_id=channel.channel_id, data=payload)
        except DiscordAPITokenInvalid:
            logger.error(f"Discord bot token is invalid, could not announce shifts for schedule {schedule_pk}")
            return
        else:
            # Set only after the announcement lands, so a failed one is retried by the next run.
            cache.set(cache_key, True, ANNOUNCED_CACHE_TTL)


@shared_dedicated_queue_retry_task()
def announce_shift_starts_for_all_schedules() -> None:
    if not DiscordChannel.objects.filter(is_default_channel=True).exists():
        return

    for schedule in OnCallSchedule.objects.filter(organization__deleted_at__isnull=True):
        announce_shift_starts_for_schedule.apply_async((schedule.pk,))
