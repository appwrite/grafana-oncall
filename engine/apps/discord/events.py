import enum
import logging
import typing

from apps.alerts.constants import ActionSource
from apps.alerts.models import AlertGroup

logger = logging.getLogger(__name__)

# Discord echoes a component's custom_id back to the interactions endpoint verbatim, so it carries everything needed
# to act: which button, on which alert group. It is limited to 100 characters, which a public primary key fits inside.
CUSTOM_ID_PREFIX = "oncall"


class EventAction(enum.StrEnum):
    ACKNOWLEDGE = "acknowledge"
    UNACKNOWLEDGE = "unacknowledge"
    RESOLVE = "resolve"
    UNRESOLVE = "unresolve"


ACTION_TO_ALERT_GROUP_METHOD = {
    EventAction.ACKNOWLEDGE: "acknowledge_by_user_or_backsync",
    EventAction.UNACKNOWLEDGE: "un_acknowledge_by_user_or_backsync",
    EventAction.RESOLVE: "resolve_by_user_or_backsync",
    EventAction.UNRESOLVE: "un_resolve_by_user_or_backsync",
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


def process_interaction(value: str, user) -> None:
    """Apply the button a Discord user pressed to its alert group."""
    parsed = parse_custom_id(value)
    if parsed is None:
        return

    action, alert_group_public_primary_key = parsed
    try:
        # Scoped to the presser's organization: the custom_id is whatever was in the message they pressed, and the
        # permission check upstream only speaks for their own tenant.
        alert_group = AlertGroup.objects.get(
            public_primary_key=alert_group_public_primary_key,
            channel__organization=user.organization,
        )
    except AlertGroup.DoesNotExist:
        logger.info(f"Alert group {alert_group_public_primary_key} from discord interaction not found")
        return

    action_fn = getattr(alert_group, ACTION_TO_ALERT_GROUP_METHOD[action])
    action_fn(user=user, action_source=ActionSource.DISCORD)
