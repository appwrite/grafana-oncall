import datetime
import logging
import typing

import jwt
from django.conf import settings
from django.utils import timezone

from apps.discord.models import DiscordUser
from apps.user_management.models import User
from common.insight_log.chatops_insight_logs import ChatOpsEvent, ChatOpsTypePlug, write_chatops_insight_log

logger = logging.getLogger(__name__)

VERIFICATION_CODE_TTL = datetime.timedelta(minutes=10)


def beside_card(discord_message) -> typing.Tuple[str, dict]:
    """Where a follow-up to a card goes, and what it takes to sit beside it.

    A forum card is a post, so a follow-up is just a message in that post. A card in a text channel shares the
    channel with everything else, so a follow-up has to quote it to read as a reply. Posting to a forum channel
    itself is not a thing Discord allows at all ("Cannot send messages in a non-text channel").
    """
    if discord_message.thread_id:
        return discord_message.thread_id, {}
    return discord_message.channel_id, {
        "message_reference": {"message_id": discord_message.message_id, "fail_if_not_exists": False}
    }


def create_verification_code(user: User) -> str:
    """A short-lived proof that whoever holds it is signed in to OnCall as `user`.

    Signed rather than stored: Discord has no way to carry a payload into a slash command, so the code is pasted by
    hand and only has to survive the seconds between reading it in OnCall and typing it in Discord.
    """
    return jwt.encode(
        {"user_id": user.public_primary_key, "exp": timezone.now() + VERIFICATION_CODE_TTL},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def link_user(code: str, discord_user_id: str, username: str) -> typing.Optional[DiscordUser]:
    """Link the Discord account that used `code` to the OnCall user the code was issued to."""
    try:
        payload = jwt.decode(code, settings.SECRET_KEY, algorithms=["HS256"])
        user = User.objects.get(public_primary_key=payload["user_id"])
    except (jwt.InvalidTokenError, KeyError, User.DoesNotExist) as e:
        logger.info(f"Discord verification code rejected: {e}")
        return None

    # One Discord account speaks for one OnCall user: leaving an older claim in place would make a button press
    # ambiguous about who pressed it.
    DiscordUser.objects.filter(discord_user_id=discord_user_id).exclude(user=user).delete()
    discord_user, _ = DiscordUser.objects.update_or_create(
        user=user, defaults={"discord_user_id": discord_user_id, "username": username}
    )
    write_chatops_insight_log(
        author=user,
        event_name=ChatOpsEvent.USER_LINKED,
        chatops_type=ChatOpsTypePlug.DISCORD.value,
        linked_user=user.username,
        linked_user_id=user.public_primary_key,
    )
    return discord_user
