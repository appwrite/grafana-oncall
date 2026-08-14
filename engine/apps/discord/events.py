import enum
import logging
import typing

from apps.alerts.constants import ActionSource
from apps.alerts.models import AlertGroup
from apps.user_management.models import User

logger = logging.getLogger(__name__)

# Discord echoes a component's custom_id back to the interactions endpoint verbatim, so it carries everything needed
# to act: which control, on which alert group. It is limited to 100 characters, which a public primary key fits inside.
CUSTOM_ID_PREFIX = "oncall"


class EventAction(enum.StrEnum):
    ACKNOWLEDGE = "acknowledge"
    UNACKNOWLEDGE = "unacknowledge"
    RESOLVE = "resolve"
    UNRESOLVE = "unresolve"
    SILENCE = "silence"
    UNSILENCE = "unsilence"
    PAGE_RESPONDER = "page"
    RESOLUTION_NOTE = "note"
    RESOLUTION_NOTE_SUBMIT = "note-submit"


# The actions that are one call on the alert group and nothing else.
ACTION_TO_ALERT_GROUP_METHOD = {
    EventAction.ACKNOWLEDGE: "acknowledge_by_user_or_backsync",
    EventAction.UNACKNOWLEDGE: "un_acknowledge_by_user_or_backsync",
    EventAction.RESOLVE: "resolve_by_user_or_backsync",
    EventAction.UNRESOLVE: "un_resolve_by_user_or_backsync",
    EventAction.UNSILENCE: "un_silence_by_user_or_backsync",
}


def custom_id(action: EventAction, alert_group: AlertGroup) -> str:
    return f"{CUSTOM_ID_PREFIX}:{action.value}:{alert_group.public_primary_key}"


def parse_custom_id(value: str) -> typing.Optional[typing.Tuple[EventAction, str]]:
    parts = value.split(":")
    if len(parts) != 3 or parts[0] != CUSTOM_ID_PREFIX:
        return None
    try:
        return EventAction(parts[1]), parts[2]
    except ValueError:
        logger.info(f"Unknown discord interaction action in custom_id {value}")
        return None


def get_alert_group(public_primary_key: str, user: User) -> typing.Optional[AlertGroup]:
    """The alert group a control names, if it is one the presser is allowed to touch.

    Scoped to the presser's organization: a custom_id is whatever was in the message they pressed, and the permission
    check upstream only speaks for their own tenant.
    """
    try:
        return AlertGroup.objects.get(public_primary_key=public_primary_key, channel__organization=user.organization)
    except AlertGroup.DoesNotExist:
        logger.info(f"Alert group {public_primary_key} from discord interaction not found")
        return None


def process_interaction(value: str, user: User, values: typing.Optional[list] = None) -> None:
    """Apply the control a Discord user used to its alert group.

    `values` is what a select carried — a silence duration, or the user to page. A button carries none.
    """
    parsed = parse_custom_id(value)
    if parsed is None:
        return

    action, public_primary_key = parsed
    alert_group = get_alert_group(public_primary_key, user)
    if alert_group is None:
        return

    selected = values[0] if values else None

    if action in ACTION_TO_ALERT_GROUP_METHOD:
        getattr(alert_group, ACTION_TO_ALERT_GROUP_METHOD[action])(user=user, action_source=ActionSource.DISCORD)
    elif action == EventAction.SILENCE:
        alert_group.silence_by_user_or_backsync(
            user=user, silence_delay=int(selected), action_source=ActionSource.DISCORD
        )
    elif action == EventAction.PAGE_RESPONDER:
        page_responder(alert_group, user, selected)


def page_responder(alert_group: AlertGroup, from_user: User, public_primary_key: typing.Optional[str]) -> None:
    """Add somebody to an alert group's escalation, the way Slack's Responders button does."""
    from apps.alerts.paging import direct_paging

    responder = User.objects.filter(public_primary_key=public_primary_key, organization=from_user.organization).first()
    if responder is None:
        logger.info(f"User {public_primary_key} to page from discord not found")
        return

    direct_paging(
        organization=from_user.organization,
        from_user=from_user,
        message="",
        users=[(responder, False)],
        alert_group=alert_group,
    )


def add_resolution_note(alert_group: AlertGroup, author: User, text: str) -> None:
    from apps.alerts.models import ResolutionNote

    ResolutionNote.objects.create(
        alert_group=alert_group, author=author, source=ResolutionNote.Source.DISCORD, message_text=text
    )
