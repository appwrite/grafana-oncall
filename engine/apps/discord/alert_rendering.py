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
# A message carries five rows, and a row five buttons.
ACTION_ROW_LIMIT = 5
BUTTONS_PER_ROW = 5
# A select carries at most 25 options, with no way to group them the way Slack does. Everything offered in one is
# therefore capped, and the cap is named here so the copy that explains it stays next to the number.
SELECT_OPTION_LIMIT = 25

TRIMMED_NOTICE = "… Message has been trimmed, open it in OnCall to read the whole thing."

# A link button carries a URL rather than a custom_id, and Discord refuses anything that is not a real http(s) URL.
BUTTON_URL_LIMIT = 512
# Where a dashboard link hides when an alert carries one. Grafana Alerting sets `dashboardURL` for a rule attached
# to a panel, and a rule can set `dashboard_url` itself; neither is the alert's source link, which for a
# Grafana-managed rule is the rule's own page.
DASHBOARD_ANNOTATIONS = ("dashboard_url", "dashboardURL")

# The status an alert group is in, named the way OnCall names it everywhere else.
FIRING, ACKNOWLEDGED, SILENCED, RESOLVED = "firing", "acknowledged", "silenced", "resolved"

# What a route may declare a still-open alert group to be, in the words alerting labels already use. Severity
# belongs to the route rather than to the payload, because which label means "wake somebody" differs per deployment
# and OnCall already asks a route to decide where an alert goes and who it pages.
CRITICAL, WARNING, INFO = "critical", "warning", "info"
SEVERITIES = (CRITICAL, WARNING, INFO)

# The emoji for a status, used where a line names the status itself — the timeline, and the tag a post carries.
# Firing has no entry in CARD_STYLE because a firing card reads by its severity instead.
STATUS_EMOJI = {
    FIRING: "🔥",
    ACKNOWLEDGED: "🟡",
    SILENCED: "🔕",
    RESOLVED: "✅",
}

# How a card reads: the emoji leads the title so a channel list shows where a group stands without opening anything,
# and the colour is the embed's left border. A firing group reads by its severity, any other status by itself.
CARD_STYLE = {
    CRITICAL: ("🚨", 0xA30200),
    WARNING: ("⚠️", 0xE67E22),
    # A book rather than ℹ️: a forum tag is read by the letters of its words, and U+2139 is a lowercase
    # letter to Unicode, so "ℹ️ Info" reads as a word that is not "info". Keeping the card and the tag on
    # the same emoji keeps that trap out of a forum owner's way.
    INFO: ("📘", 0x3274D9),
    # The status half takes its emoji from STATUS_EMOJI rather than repeating it, so a card and the timeline line
    # for the same status cannot end up saying different things.
    ACKNOWLEDGED: (STATUS_EMOJI[ACKNOWLEDGED], 0xDAA038),
    SILENCED: (STATUS_EMOJI[SILENCED], 0xDDDDDD),
    RESOLVED: (STATUS_EMOJI[RESOLVED], 0x2EB886),
}


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
    return severity if severity in SEVERITIES else CRITICAL


def route_escalation_role(alert_group: AlertGroup) -> typing.Optional[str]:
    """The Discord role a route escalates to, if it names one."""
    return route_config(alert_group).get("role") or None


def card_status(alert_group: AlertGroup) -> str:
    """Where the group stands, in OnCall's own words."""
    if alert_group.resolved:
        return RESOLVED
    if alert_group.acknowledged:
        return ACKNOWLEDGED
    if alert_group.silenced:
        return SILENCED
    return FIRING


def card_style(alert_group: AlertGroup) -> tuple:
    # A status outranks severity: once somebody owns the group, or it is done, that is the more useful thing for the
    # channel to show than how loudly it arrived.
    status = card_status(alert_group)
    return CARD_STYLE[route_severity(alert_group) if status == FIRING else status]


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
        emoji, color = card_style(self.alert_group)

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
        # Every line names a status, so every line reads by its status — including this one. The severity is the
        # card's title, not an event in its history.
        lines = [f"{STATUS_EMOJI[FIRING]} Fired {stamp(alert_group.started_at)}"]

        if alert_group.acknowledged and alert_group.acknowledged_at:
            lines.append(
                f"{STATUS_EMOJI[ACKNOWLEDGED]} {alert_group.get_acknowledge_text()} "
                f"{stamp(alert_group.acknowledged_at)}"
            )
        if alert_group.silenced and alert_group.silenced_at:
            until = f" until {stamp(alert_group.silenced_until)}" if alert_group.silenced_until else ""
            lines.append(f"{STATUS_EMOJI[SILENCED]} Silenced {stamp(alert_group.silenced_at)}{until}")
        if alert_group.resolved and alert_group.resolved_at:
            lines.append(f"{STATUS_EMOJI[RESOLVED]} {alert_group.get_resolve_text()} {stamp(alert_group.resolved_at)}")
        return "\n".join(lines)

    def _components(self) -> list:
        """Rows of controls.

        A row holds five buttons at most and a select has to occupy one alone, so the buttons are chunked and the
        selects get rows of their own. A silenced alert group with a dashboard link is the case that overflows.
        """
        buttons = self._buttons()
        rows = [
            {"type": ACTION_ROW, "components": buttons[index : index + BUTTONS_PER_ROW]}
            for index in range(0, len(buttons), BUTTONS_PER_ROW)
        ]
        if not self.alert_group.resolved:
            if not self.alert_group.silenced:
                rows.append({"type": ACTION_ROW, "components": [self._silence_select()]})
            rows.append({"type": ACTION_ROW, "components": [self._responders_select()]})
        return rows[:ACTION_ROW_LIMIT]

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

    def _dashboard_link(self) -> typing.Optional[str]:
        """The dashboard an alert points at, if it carries one, so the card can offer it as a button.

        A raw URL in the body is a line to read and then copy; a button is one press. Taken from the payload
        rather than a template because it is a link, not prose — the templates leave it out for this reason.
        """
        alert = self.alert_group.alerts.last()
        annotations = (getattr(alert, "raw_request_data", None) or {}).get("commonAnnotations") or {}
        for name in DASHBOARD_ANNOTATIONS:
            candidate = annotations.get(name)
            if valid_link(candidate):
                return candidate
        return None

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

        def link_button(label: str, url: str) -> dict:
            return {"type": BUTTON, "style": BUTTON_LINK, "label": label, "url": url}

        source_link = self.alert_renderer.templated_alert.source_link
        if valid_link(source_link):
            # "Source", not "Dashboard": for a Grafana-managed rule this opens the rule, and for an external
            # Alertmanager it opens whatever raised the alert. Only a dashboard link gets called a dashboard.
            buttons.append(link_button("Source", source_link))

        dashboard_link = self._dashboard_link()
        if dashboard_link and dashboard_link != source_link:
            buttons.append(link_button("Dashboard", dashboard_link))

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
        leaves where it stands to the card and the post's tags.

        The number is what distinguishes two posts about similarly named alerts, so the title is trimmed to leave
        room for it rather than the pair being trimmed together — which would drop the number off a long title and
        make the two posts indistinguishable.
        """
        renderer = AlertGroupDiscordRenderer(self.alert_group)
        title = str_or_backup(renderer.alert_renderer.templated_alert.title, "Alert")
        suffix = f" · #{self.alert_group.inside_organization_number}"
        return truncate(title, THREAD_NAME_LIMIT - len(suffix)) + suffix

    def tag_names(self) -> list:
        """The forum tags this alert group should carry, matched against the forum's tags by name: where it stands,
        and how loudly it arrived."""
        return [card_status(self.alert_group).capitalize(), route_severity(self.alert_group).capitalize()]
