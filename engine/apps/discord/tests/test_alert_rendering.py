import pytest
from django.utils import timezone

from apps.alerts.models import AlertReceiveChannel
from apps.discord.alert_rendering import CARD_STYLE, RESOLVED, DiscordMessageRenderer


@pytest.fixture()
def make_rendered_message(make_organization, make_alert_receive_channel, make_alert_group, make_alert):
    def _make_rendered_message(**alert_group_kwargs):
        organization = make_organization()
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, **alert_group_kwargs)
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        return DiscordMessageRenderer(alert_group).render_alert_group_message()

    return _make_rendered_message


def button_labels(payload):
    return [component["label"] for component in payload["components"][0]["components"]]


@pytest.mark.django_db
def test_render_firing_alert_group(make_rendered_message):
    payload = make_rendered_message()

    embed = payload["embeds"][0]
    assert embed["title"].startswith("🚨")
    assert embed["color"] == CARD_STYLE["alert"][1]
    assert button_labels(payload) == ["Acknowledge", "Resolve", "OnCall"]


@pytest.mark.django_db
def test_render_acknowledged_alert_group(make_rendered_message):
    payload = make_rendered_message(acknowledged=True, acknowledged_at=timezone.now())

    embed = payload["embeds"][0]
    assert embed["title"].startswith("🟡")
    assert button_labels(payload) == ["Unacknowledge", "Resolve", "OnCall"]
    assert embed["fields"][-1]["name"] == "Status"


@pytest.mark.django_db
def test_render_resolved_alert_group(make_rendered_message):
    payload = make_rendered_message(resolved=True, resolved_at=timezone.now())

    embed = payload["embeds"][0]
    assert embed["title"].startswith("✅")
    assert embed["color"] == CARD_STYLE[RESOLVED][1]
    assert button_labels(payload) == ["Unresolve", "OnCall"]


@pytest.mark.django_db
def test_render_silenced_alert_group(make_rendered_message):
    payload = make_rendered_message(silenced=True, silenced_at=timezone.now())

    assert payload["embeds"][0]["title"].startswith("🔕")


@pytest.mark.django_db
def test_buttons_carry_the_alert_group(make_rendered_message, make_organization, make_alert_receive_channel):
    payload = make_rendered_message()

    acknowledge = payload["components"][0]["components"][0]
    assert acknowledge["custom_id"].startswith("oncall:acknowledge:")
    assert len(acknowledge["custom_id"]) <= 100


@pytest.mark.parametrize(
    "templated,expected",
    [
        # Discord expands a shortcode only client-side, so anything OnCall's shared defaults emit must arrive as
        # the character itself.
        (":fire: it is on fire", "🔥 it is on fire"),
        (":rotating_light: critical", "🚨 critical"),
        # A masked link with nothing to point at renders as its own brackets, so drop the markup and keep the label.
        ("[View in AlertManager]()", "View in AlertManager"),
        ("[Runbook](https://runbooks.appwrite.io/db)", "[Runbook](https://runbooks.appwrite.io/db)"),
        # An unknown shortcode is left alone rather than guessed at.
        (":not_an_emoji: stays", ":not_an_emoji: stays"),
        ("", ""),
        (None, None),
    ],
)
def test_for_discord(templated, expected):
    from apps.discord.alert_rendering import _for_discord

    assert _for_discord(templated) == expected


@pytest.mark.django_db
def test_templater_fixes_up_the_shared_web_defaults(
    make_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    from apps.alerts.incident_appearance.templaters.alert_templater import TemplatedAlert
    from apps.discord.alert_rendering import AlertDiscordTemplater

    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    alert = make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    templated = AlertDiscordTemplater(alert)._postformat(
        TemplatedAlert(title=":fire: Down", message="Status: firing :fire:\n[View in AlertManager]()")
    )

    assert templated.title == "🔥 Down"
    assert templated.message == "Status: firing 🔥\nView in AlertManager"
