import re
import typing

from emoji import emojize

from apps.alerts.incident_appearance.renderers.base_renderer import AlertBaseRenderer, AlertGroupBaseRenderer
from apps.alerts.incident_appearance.templaters.alert_templater import AlertTemplater
from apps.alerts.models import Alert, AlertGroup
from common.utils import is_string_with_visible_characters, str_or_backup

# https://discord.com/developers/docs/resources/message#embed-object-embed-limits
EMBED_TITLE_LIMIT = 256
EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_VALUE_LIMIT = 1024

# Discord button style ids, https://discord.com/developers/docs/components/reference#button
BUTTON_PRIMARY = 1
BUTTON_SECONDARY = 2
BUTTON_LINK = 5

# How a card reads for each state an alert group can be in: the emoji leads the title so a channel list shows the
# current state without opening anything, and the colour is the embed's left border.
ALERT, ACKNOWLEDGED, SILENCED, RESOLVED = "alert", "acknowledged", "silenced", "resolved"
CARD_STYLE = {
    ALERT: ("🚨", 0xA30200),
    ACKNOWLEDGED: ("🟡", 0xDAA038),
    SILENCED: ("🔕", 0xDDDDDD),
    RESOLVED: ("✅", 0x2EB886),
}


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def card_state(alert_group: AlertGroup) -> str:
    if alert_group.resolved:
        return RESOLVED
    if alert_group.acknowledged:
        return ACKNOWLEDGED
    if alert_group.silenced:
        return SILENCED
    return ALERT


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
            embed["description"] = truncate(self.templated_alert.message, EMBED_DESCRIPTION_LIMIT)
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

        status = self._status_text(state)
        if status:
            embed["fields"].append(
                {"name": "Status", "value": truncate(status, EMBED_FIELD_VALUE_LIMIT), "inline": False}
            )

        return {"embeds": [embed], "components": [{"type": 1, "components": self._buttons()}]}

    def _status_text(self, state: str) -> str:
        if state == RESOLVED:
            return self.alert_group.get_resolve_text()
        if state == ACKNOWLEDGED:
            return self.alert_group.get_acknowledge_text()
        return ""

    def _buttons(self) -> list:
        from apps.discord.events import EventAction, custom_id

        def button(action: EventAction, label: str) -> dict:
            return {
                "type": 2,
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
        else:
            buttons.append(button(EventAction.UNRESOLVE, "Unresolve"))

        buttons.append({"type": 2, "style": BUTTON_LINK, "label": "OnCall", "url": self.alert_group.web_link})
        return buttons


class DiscordMessageRenderer:
    def __init__(self, alert_group: AlertGroup):
        self.alert_group = alert_group

    def render_alert_group_message(self) -> dict:
        return AlertGroupDiscordRenderer(self.alert_group).render_alert_group_message()
