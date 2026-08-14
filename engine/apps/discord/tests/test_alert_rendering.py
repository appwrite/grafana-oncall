import pytest
from django.utils import timezone

from apps.alerts.models import AlertReceiveChannel
from apps.discord.alert_rendering import CARD_STYLE, RESOLVED, STRING_SELECT, DiscordMessageRenderer


@pytest.fixture()
def make_rendered_message(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    def _make_rendered_message(**alert_group_kwargs):
        organization = make_organization()
        make_user_for_organization(organization, username="loks0n")
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, **alert_group_kwargs)
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        return DiscordMessageRenderer(alert_group).render_alert_group_message()

    return _make_rendered_message


def button_labels(payload):
    return [component["label"] for component in payload["components"][0]["components"]]


def selects(payload):
    return [
        component
        for row in payload["components"]
        for component in row["components"]
        if component["type"] == STRING_SELECT
    ]


@pytest.mark.django_db
def test_render_firing_alert_group(make_rendered_message):
    payload = make_rendered_message()

    embed = payload["embeds"][0]
    assert embed["title"].startswith("🚨")
    assert embed["color"] == CARD_STYLE["alert"][1]
    assert button_labels(payload) == ["Acknowledge", "Resolve", "Add note", "OnCall"]


@pytest.mark.django_db
def test_render_acknowledged_alert_group(make_rendered_message):
    payload = make_rendered_message(acknowledged=True, acknowledged_at=timezone.now())

    embed = payload["embeds"][0]
    assert embed["title"].startswith("🟡")
    assert button_labels(payload) == ["Unacknowledge", "Resolve", "Add note", "OnCall"]
    assert embed["fields"][-1]["name"] == "Status"


@pytest.mark.django_db
def test_render_resolved_alert_group(make_rendered_message):
    payload = make_rendered_message(resolved=True, resolved_at=timezone.now())

    embed = payload["embeds"][0]
    assert embed["title"].startswith("✅")
    assert embed["color"] == CARD_STYLE[RESOLVED][1]
    assert button_labels(payload) == ["Unresolve", "Add note", "OnCall"]


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "notification_backends,emoji",
    [
        ({"DISCORD": {"severity": "warning", "enabled": True}}, "⚠️"),
        ({"DISCORD": {"severity": "alert", "enabled": True}}, "🚨"),
        # A route that says nothing about severity, or says something unknown, is an alert.
        ({"DISCORD": {"enabled": True}}, "🚨"),
        ({"DISCORD": {"severity": "whatever", "enabled": True}}, "🚨"),
        (None, "🚨"),
    ],
)
def test_route_severity_sets_how_a_firing_card_reads(
    make_organization,
    make_alert_receive_channel,
    make_channel_filter,
    make_alert_group,
    make_alert,
    notification_backends,
    emoji,
):
    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    channel_filter = make_channel_filter(alert_receive_channel, notification_backends=notification_backends)
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, channel_filter=channel_filter)
    make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert payload["embeds"][0]["title"].startswith(emoji)


@pytest.mark.django_db
def test_acknowledging_a_warning_outranks_its_severity(
    make_organization, make_alert_receive_channel, make_channel_filter, make_alert_group, make_alert
):
    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    channel_filter = make_channel_filter(
        alert_receive_channel, notification_backends={"DISCORD": {"severity": "warning", "enabled": True}}
    )
    alert_group = make_alert_group(
        alert_receive_channel=alert_receive_channel,
        channel_filter=channel_filter,
        acknowledged=True,
        acknowledged_at=timezone.now(),
    )
    make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert payload["embeds"][0]["title"].startswith("🟡")


@pytest.mark.django_db
def test_a_firing_card_offers_silence_and_paging(make_rendered_message):
    payload = make_rendered_message()

    silence, responders = selects(payload)
    assert silence["placeholder"] == "Silence"
    assert [option["label"] for option in silence["options"]][:2] == ["30 minutes", "1 hour"]
    assert silence["options"][-1] == {"label": "Forever", "value": "-1"}
    assert responders["placeholder"] == "Page a responder"
    # A select has to be alone in its row.
    assert [len(row["components"]) for row in payload["components"]] == [4, 1, 1]


@pytest.mark.django_db
def test_a_silenced_card_offers_unsilence_instead(make_rendered_message):
    payload = make_rendered_message(silenced=True, silenced_at=timezone.now())

    assert "Unsilence" in button_labels(payload)
    assert [select["placeholder"] for select in selects(payload)] == ["Page a responder"]


@pytest.mark.django_db
def test_a_resolved_card_offers_neither(make_rendered_message):
    payload = make_rendered_message(resolved=True, resolved_at=timezone.now())

    assert selects(payload) == []


@pytest.mark.django_db
def test_footer_says_where_the_alert_came_from(
    make_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    for _ in range(3):
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    footer = DiscordMessageRenderer(alert_group).render_alert_group_message()["embeds"][0]["footer"]["text"]

    assert (
        footer
        == f"via Grafana Legacy Alerting · #{alert_group.inside_organization_number} · showing the last of 3 alerts"
    )


@pytest.mark.django_db
def test_footer_leaves_the_count_out_for_a_single_alert(make_rendered_message):
    payload = make_rendered_message()

    assert "alerts" not in payload["embeds"][0]["footer"]["text"]


def test_a_trimmed_message_says_where_to_read_the_rest():
    from apps.discord.alert_rendering import EMBED_DESCRIPTION_LIMIT, TRIMMED_NOTICE, truncate

    trimmed = truncate("x" * (EMBED_DESCRIPTION_LIMIT + 10), EMBED_DESCRIPTION_LIMIT, TRIMMED_NOTICE)

    assert len(trimmed) <= EMBED_DESCRIPTION_LIMIT
    assert trimmed.endswith(TRIMMED_NOTICE)


@pytest.mark.django_db
def test_paging_is_disabled_when_the_organization_has_no_users(
    make_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    responders = selects(payload)[-1]
    assert responders["disabled"] is True
    # Discord rejects a select with no options at all, even a disabled one.
    assert responders["options"] == [{"label": "No users to page", "value": "none"}]
