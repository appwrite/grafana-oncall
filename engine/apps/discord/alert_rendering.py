import re
import typing
from urllib.parse import urlparse

from emoji import emojize

from apps.alerts.incident_appearance.renderers.base_renderer import AlertBaseRenderer, AlertGroupBaseRenderer
from apps.alerts.incident_appearance.templaters.alert_templater import AlertTemplater
from apps.alerts.models import Alert, AlertGroup
from apps.discord.client import THREAD_NAME_LIMIT
from common.utils import is_string_with_visible_characters, str_or_backup

# https://discord.com/developers/docs/resources/message#embed-object-embed-limits
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_VALUE_LIMIT = 1024
EMBED_FOOTER_LIMIT = 2048

# https://discord.com/developers/docs/components/reference
ACTION_ROW = 1
BUTTON = 2
STRING_SELECT = 3
BUTTON_PRIMARY = 1
BUTTON_SECONDARY = 2
BUTTON_LINK = 5
SELECT_LABEL_LIMIT = 100
# A select carries at most 25 options, with no way to group them the way Slack does. Everything offered in one is
# therefore capped, and the cap is named here so the copy that explains it stays next to the number.
SELECT_OPTION_LIMIT = 25

TRIMMED_NOTICE = "… Message has been trimmed, open it in OnCall to read the whole thing."

# A link button carries a URL rather than a custom_id, and Discord refuses anything that is not a real http(s) URL.
BUTTON_URL_LIMIT = 512
# Which integrations call their source link a dashboard. Everything else gets the neutral word.
DASHBOARD_INTEGRATIONS = (
    "grafana",
    "grafana_alerting",
    "alertmanager",
    "legacy_grafana_alerting",
    "legacy_alertmanager",
)

# How a card reads for each state an alert group can be in: the emoji leads the title so a channel list shows the
# current state without opening anything, and the colour is the embed's left border.
ALERT, WARNING, ACKNOWLEDGED, SILENCED, RESOLVED = "alert", "warning", "acknowledged", "silenced", "resolved"
CARD_STYLE = {
    ALERT: ("🚨", 0xA30200),
    WARNING: ("⚠️", 0xE67E22),
    ACKNOWLEDGED: ("🟡", 0xDAA038),
    SILENCED: ("🔕", 0xDDDDDD),
    RESOLVED: ("✅", 0x2EB886),
}

# What a route may declare an alert group to be. Severity says how loud a still-open group reads; it is a property of
# the route rather than of the payload, because which label means "wake somebody" differs per deployment and OnCall
# already asks a route to decide where an alert goes and who it pages.
SEVERITIES = (ALERT, WARNING)


def truncate(value: str, limit: int, notice: str = "…") -> str:
    """Cut `value` to `limit`, ending with `notice` so a reader knows something is missing rather than guessing."""
    if len(value) <= limit:
        return value
    return value[: limit - len(notice)].rstrip() + notice


def valid_link(url: typing.Optional[str]) -> bool:
    if not url or len(url) > BUTTON_URL_LIMIT:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def stamp(moment) -> str:
    """A moment as Discord renders it: the reader's own clock, and how long ago in their own words."""
    seconds = int(moment.timestamp())
    return f"<t:{seconds}:t> (<t:{seconds}:R>)"


def route_config(alert_group: AlertGroup) -> dict:
    from apps.discord.backend import DiscordBackend  # To avoid circular import

    backends = getattr(alert_group.channel_filter, "notification_backends", None) or {}
    return backends.get(DiscordBackend.backend_id) or {}


def route_severity(alert_group: AlertGroup) -> str:
    severity = route_config(alert_group).get("severity")
    return severity if severity in SEVERITIES else ALERT


def route_escalation_role(alert_group: AlertGroup) -> typing.Optional[str]:
    """The Discord role a route escalates to, if it names one."""
    return route_config(alert_group).get("role") or None


def card_state(alert_group: AlertGroup) -> str:
    # An acknowledgement outranks severity: once somebody owns the group, who owns it is the more useful thing for
    # the channel to show.
    if alert_group.resolved:
        return RESOLVED
    if alert_group.acknowledged:
        return ACKNOWLEDGED
    if alert_group.silenced:
        return SILENCED
    return route_severity(alert_group)


class AlertDiscordTemplater(AlertTemplater):
    RENDER_FOR_DISCORD = "discord"

    def _render_for(self) -> str:
        return self.RENDER_FOR_DISCORD

    def _postformat(self, templated_alert):
        """Fix up what OnCall's shared defaults assume about the surface they land on.

        There are no `discord_*` default templates, so an integration falls back to the web ones, which were written
        for a client that turns `:fire:` into an emoji and shrugs at a link with no target. Discord expands a
        shortcode only in the client as somebody types it — never over the API, and never inside an embed — and shows
        an empty masked link as its literal brackets. Both are cheap to fix here, and fixing them here covers every
        integration, including ones added later.
        """
        templated_alert.title = _for_discord(templated_alert.title)
        templated_alert.message = _for_discord(templated_alert.message)
        return templated_alert


# `[label]()` — a masked link whose target the template had nothing to fill in with.
EMPTY_MASKED_LINK = re.compile(r"\[([^\]]*)\]\(\s*\)")


def _for_discord(text: typing.Optional[str]) -> typing.Optional[str]:
    if not text:
        return text
    return EMPTY_MASKED_LINK.sub(r"\1", emojize(text, language="alias"))


class AlertDiscordRenderer(AlertBaseRenderer):
    def __init__(self, alert: Alert):
        super().__init__(alert)
        self.channel = alert.group.channel

    @property
    def templater_class(self):
        return AlertDiscordTemplater

    def render_alert_embed(self) -> dict:
        embed = {
            "title": truncate(str_or_backup(self.templated_alert.title, "Alert"), EMBED_TITLE_LIMIT),
            "fields": [],
        }
        if self.templated_alert.source_link:
            embed["url"] = self.templated_alert.source_link
        if is_string_with_visible_characters(self.templated_alert.message):
            embed["description"] = truncate(self.templated_alert.message, EMBED_DESCRIPTION_LIMIT, TRIMMED_NOTICE)
        if self.templated_alert.image_url:
            embed["image"] = {"url": self.templated_alert.image_url}
        return embed


class AlertGroupDiscordRenderer(AlertGroupBaseRenderer):
    def __init__(self, alert_group: AlertGroup):
        super().__init__(alert_group)

        self.alert_renderer = self.alert_renderer_class(self.alert_group.alerts.last())

    @property
    def alert_renderer_class(self):
        return AlertDiscordRenderer

    def render_alert_group_message(self) -> dict:
        """The whole Discord message for an alert group: one embed, one row of buttons."""
        state = card_state(self.alert_group)
        emoji, color = CARD_STYLE[state]

        embed = self.alert_renderer.render_alert_embed()
        embed["title"] = truncate(f"{emoji} {embed['title']}", EMBED_TITLE_LIMIT)
        embed["color"] = color

        embed["fields"].append(
            {"name": "Timeline", "value": truncate(self._timeline(), EMBED_FIELD_VALUE_LIMIT), "inline": False}
        )

        embed["footer"] = {"text": truncate(self._footer(), EMBED_FOOTER_LIMIT)}

        return {"embeds": [embed], "components": self._components()}

    def _footer(self) -> str:
        """Where the alert came from and which group it is — the context Slack puts in its title line and a
        context block, in the one place a Discord embed has for it."""
        alert_group = self.alert_group
        parts = [
            f"via {alert_group.channel.get_integration_display()}",
            f"#{alert_group.inside_organization_number}",
        ]

        alerts_count = alert_group.alerts.count()
        if alerts_count > 1:
            parts.append(f"showing the last of {alerts_count} alerts")
        return " · ".join(parts)

    def _timeline(self) -> str:
        """What happened to this alert group and when, in the reader's own timezone.

        Discord renders `<t:…>` client-side, so an engineer in another timezone reads their own clock and everybody
        sees how long the alert has been open without subtracting timestamps by hand.
        """
        alert_group = self.alert_group
        lines = [f"{CARD_STYLE[ALERT][0]} Fired {stamp(alert_group.started_at)}"]

        if alert_group.acknowledged and alert_group.acknowledged_at:
            lines.append(
                f"{CARD_STYLE[ACKNOWLEDGED][0]} {alert_group.get_acknowledge_text()} "
                f"{stamp(alert_group.acknowledged_at)}"
            )
        if alert_group.silenced and alert_group.silenced_at:
            until = f" until {stamp(alert_group.silenced_until)}" if alert_group.silenced_until else ""
            lines.append(f"{CARD_STYLE[SILENCED][0]} Silenced {stamp(alert_group.silenced_at)}{until}")
        if alert_group.resolved and alert_group.resolved_at:
            lines.append(f"{CARD_STYLE[RESOLVED][0]} {alert_group.get_resolve_text()} {stamp(alert_group.resolved_at)}")
        return "\n".join(lines)

    def _components(self) -> list:
        """Rows of controls. A select has to occupy a row of its own, which is why these are not all one row."""
        rows = [{"type": ACTION_ROW, "components": self._buttons()}]
        if not self.alert_group.resolved:
            if not self.alert_group.silenced:
                rows.append({"type": ACTION_ROW, "components": [self._silence_select()]})
            rows.append({"type": ACTION_ROW, "components": [self._responders_select()]})
        return rows

    def _silence_select(self) -> dict:
        from apps.discord.events import EventAction, custom_id

        return {
            "type": STRING_SELECT,
            "custom_id": custom_id(EventAction.SILENCE, self.alert_group),
            "placeholder": "Silence",
            "options": [
                {"label": text, "value": str(value)}
                for value, text in AlertGroup.SILENCE_DELAY_OPTIONS[:SELECT_OPTION_LIMIT]
            ],
        }

    def _responders_select(self) -> dict:
        from apps.discord.events import EventAction, custom_id

        users = self.alert_group.channel.organization.users.order_by("username")[:SELECT_OPTION_LIMIT]
        options = [
            {"label": truncate(user.username, SELECT_LABEL_LIMIT), "value": user.public_primary_key} for user in users
        ]
        return {
            "type": STRING_SELECT,
            "custom_id": custom_id(EventAction.PAGE_RESPONDER, self.alert_group),
            "placeholder": "Page a responder" if options else "No users to page",
            "disabled": not options,
            # Discord rejects a select with no options, so a disabled one still needs a placeholder option.
            "options": options or [{"label": "No users to page", "value": "none"}],
        }

    def _buttons(self) -> list:
        from apps.discord.events import EventAction, custom_id

        def button(action: EventAction, label: str) -> dict:
            return {
                "type": BUTTON,
                "style": BUTTON_PRIMARY
                if action in (EventAction.ACKNOWLEDGE, EventAction.RESOLVE)
                else BUTTON_SECONDARY,
                "label": label,
                "custom_id": custom_id(action, self.alert_group),
            }

        buttons = []
        if not self.alert_group.resolved:
            if self.alert_group.acknowledged:
                buttons.append(button(EventAction.UNACKNOWLEDGE, "Unacknowledge"))
            else:
                buttons.append(button(EventAction.ACKNOWLEDGE, "Acknowledge"))
            buttons.append(button(EventAction.RESOLVE, "Resolve"))
            if self.alert_group.silenced:
                buttons.append(button(EventAction.UNSILENCE, "Unsilence"))
        else:
            buttons.append(button(EventAction.UNRESOLVE, "Unresolve"))

        source_link = self.alert_renderer.templated_alert.source_link
        if valid_link(source_link):
            buttons.append(
                {
                    "type": BUTTON,
                    "style": BUTTON_LINK,
                    "label": "Dashboard"
                    if self.alert_group.channel.integration in DASHBOARD_INTEGRATIONS
                    else "Source",
                    "url": source_link,
                }
            )

        notes_count = self.alert_group.resolution_notes.count()
        buttons.append(
            button(EventAction.RESOLUTION_NOTE, f"Resolution notes [{notes_count}]" if notes_count else "Add note")
        )
        buttons.append({"type": BUTTON, "style": BUTTON_LINK, "label": "OnCall", "url": self.alert_group.web_link})
        return buttons


class DiscordMessageRenderer:
    def __init__(self, alert_group: AlertGroup):
        self.alert_group = alert_group

    def render_alert_group_message(self) -> dict:
        return AlertGroupDiscordRenderer(self.alert_group).render_alert_group_message()

    def render_thread_name(self) -> str:
        """What a forum post is called. Discord fixes this at creation, so it carries the alert's identity and
        leaves current state to the card and the post's tag."""
        renderer = AlertGroupDiscordRenderer(self.alert_group)
        title = str_or_backup(renderer.alert_renderer.templated_alert.title, "Alert")
        return truncate(f"{title} · #{self.alert_group.inside_organization_number}", THREAD_NAME_LIMIT)

    def state_tag_name(self) -> str:
        """The forum tag this alert group should carry, matched against the forum's tags by name."""
        return card_state(self.alert_group).capitalize()
