from importlib import import_module

import pytest
from django.utils import timezone

from apps.alerts.models import AlertGroup, AlertReceiveChannel
from apps.discord.alert_rendering import CARD_STYLE, RESOLVED, STRING_SELECT, DiscordMessageRenderer
from common.jinja_templater import apply_jinja_template


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
    assert embed["color"] == CARD_STYLE["critical"][1]
    assert button_labels(payload) == ["Acknowledge", "Resolve", "Add note", "OnCall"]


@pytest.mark.django_db
def test_render_acknowledged_alert_group(make_rendered_message):
    payload = make_rendered_message(acknowledged=True, acknowledged_at=timezone.now())

    embed = payload["embeds"][0]
    assert embed["title"].startswith("🟡")
    assert button_labels(payload) == ["Unacknowledge", "Resolve", "Add note", "OnCall"]
    assert embed["fields"][-1]["name"] == "Timeline"


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
        ({"DISCORD": {"severity": "info", "enabled": True}}, "📘"),
        ({"DISCORD": {"severity": "critical", "enabled": True}}, "🚨"),
        # A route that says nothing about severity, or says something unknown, is critical.
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
def test_a_full_card_stays_within_discord_row_limits(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    """A silenced alert group with a dashboard link is the widest the card gets: six buttons for a five-wide row."""
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA_ALERTING
    )
    alert_group = make_alert_group(
        alert_receive_channel=alert_receive_channel, silenced=True, silenced_at=timezone.now()
    )
    make_alert(
        alert_group=alert_group,
        raw_request_data={
            "status": "firing",
            "groupLabels": {"alertname": "DiskSpaceLow"},
            "alerts": [{"status": "firing", "generatorURL": "https://telemetry.appwrite.systems/d/abc/disk"}],
        },
    )

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert len(payload["components"]) <= 5
    for row in payload["components"]:
        assert len(row["components"]) <= 5
    assert button_labels(payload) == ["Acknowledge", "Resolve", "Unsilence", "Source", "Add note"]
    assert [c["label"] for c in payload["components"][1]["components"]] == ["OnCall"]


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


def timeline(payload):
    return next(field["value"] for field in payload["embeds"][0]["fields"] if field["name"] == "Timeline")


@pytest.mark.django_db
def test_timeline_of_a_firing_alert_group(make_rendered_message):
    lines = timeline(make_rendered_message()).split("\n")

    assert len(lines) == 1
    assert lines[0].startswith("🔥 Fired <t:")
    # Discord renders the same instant twice: as a clock, and as how long ago.
    assert lines[0].endswith(":R>)")


@pytest.mark.django_db
def test_timeline_records_who_acknowledged_and_when(
    make_organization_and_user, make_alert_receive_channel, make_alert_group, make_alert
):
    organization, user = make_organization_and_user()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    alert_group = make_alert_group(
        alert_receive_channel=alert_receive_channel,
        acknowledged=True,
        acknowledged_at=timezone.now(),
        acknowledged_by=AlertGroup.USER,
        acknowledged_by_user=user,
    )
    make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    lines = timeline(DiscordMessageRenderer(alert_group).render_alert_group_message()).split("\n")

    assert lines[0].startswith("🔥 Fired")
    assert lines[1].startswith(f"🟡 Acknowledged by {user.username} <t:")


@pytest.mark.django_db
def test_timeline_of_a_resolved_alert_group(make_rendered_message):
    lines = timeline(make_rendered_message(resolved=True, resolved_at=timezone.now())).split("\n")

    assert len(lines) == 2
    assert lines[1].startswith("✅ Resolved")


@pytest.mark.django_db
def test_a_long_title_keeps_the_number_that_identifies_the_post(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    """Two alerts whose long titles agree must still get distinguishable post names."""
    from apps.discord.client import THREAD_NAME_LIMIT

    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA_ALERTING
    )
    payload = {"status": "firing", "groupLabels": {"alertname": "DiskSpaceLow" * 20}}

    names = []
    for _ in range(2):
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
        make_alert(alert_group=alert_group, raw_request_data=payload)
        names.append(DiscordMessageRenderer(alert_group).render_thread_name())

    assert all(len(name) <= THREAD_NAME_LIMIT for name in names), names
    assert names[0] != names[1], names
    assert names[0].endswith("· #1") and names[1].endswith("· #2"), names


@pytest.mark.django_db
def test_a_grafana_alert_gets_a_dashboard_button(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA_ALERTING
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(
        alert_group=alert_group,
        raw_request_data={
            "status": "firing",
            "groupLabels": {"alertname": "DiskSpaceLow"},
            "alerts": [{"status": "firing", "generatorURL": "https://telemetry.appwrite.systems/d/abc/disk"}],
        },
    )

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    source = [c for c in payload["components"][0]["components"] if c.get("label") == "Source"]
    assert source, button_labels(payload)
    assert source[0]["url"] == "https://telemetry.appwrite.systems/d/abc/disk"


@pytest.mark.django_db
def test_a_link_that_is_not_a_url_gets_no_button(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(alert_group=alert_group, raw_request_data={"title": "no link here"})

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert "Dashboard" not in button_labels(payload)
    assert "Source" not in button_labels(payload)


@pytest.mark.django_db
@pytest.mark.parametrize("severity", ["critical", "warning", "info"])
def test_the_timeline_reads_by_status_whatever_the_severity(
    make_organization, make_alert_receive_channel, make_channel_filter, make_alert_group, make_alert, severity
):
    """A timeline line names a status, so it shows that status — the severity is the card's title.

    Firing used to borrow the severity emoji here, which left one line of the four speaking a different
    vocabulary from the tag beside it.
    """
    organization = make_organization()
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
    )
    channel_filter = make_channel_filter(
        alert_receive_channel, notification_backends={"DISCORD": {"severity": severity, "enabled": True}}
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, channel_filter=channel_filter)
    make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert timeline(payload).startswith("🔥 Fired")
    # The severity still leads the title, so nothing about it is lost.
    assert payload["embeds"][0]["title"].startswith(CARD_STYLE[severity][0])


# The shape Grafana Alerting actually sends: its own identifiers are wrapped in double underscores, as labels
# and as annotations. Taken from a live payload rather than written by hand.
ALERTMANAGER_PAYLOAD = {
    "status": "firing",
    "groupLabels": {"alertname": "Test failing", "name": "backups-tor", "severity": "critical"},
    "commonLabels": {
        "__alert_rule_namespace_uid__": "terraform-alerts",
        "__alert_rule_uid__": "afsxq6b2qb85cb",
        "alertname": "Test failing",
        "cluster": "assets-fra1-prod",
        "grafana_folder": "Terraform Alerts",
        "kind": "PlaywrightTest",
        "name": "backups-tor",
        "service": "backups",
        "severity": "critical",
        "team": "databases",
    },
    "commonAnnotations": {
        "__alert_rule_namespace_uid__": "terraform-alerts",
        "__orgId__": "1",
        "__value_string__": "[ var='A' labels={name=backups-tor} type='query' value=0 ]",
        "__values__": '{"A":0}',
        "dashboard_url": "https://grafana.example/d/synthetics",
        "impact": "backups unverified",
        "summary": "Synthetic test failed two consecutive runs.",
        "runbook_url": "https://runbooks.example/synthetics",
    },
    "alerts": [{"status": "firing", "labels": {}, "annotations": {}, "generatorURL": ""}],
}


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_card_keeps_every_label_and_drops_what_is_said_twice(integration):
    """The web template ends with three headings and a bullet per label, which is a page rather than a message.

    A card says the same things in a few lines. Nothing is dropped for being uninteresting — only what the card
    already says elsewhere, and the long form of a value the payload also gives compactly.
    """
    config = import_module(f"config_integrations.{integration}")
    rendered = apply_jinja_template(
        config.discord_message,
        payload=ALERTMANAGER_PAYLOAD,
        source_link="https://alertmanager.example/#/alerts",
        integration_name="Alertmanager",
    )

    assert "Synthetic test failed two consecutive runs." in rendered
    # One per line, named, so a reader can scan them rather than unpick a wrapped line of pairs.
    lines = rendered.splitlines()
    assert "**Labels**" in lines
    for label in (
        "- name: `backups-tor`",
        "- cluster: `assets-fra1-prod`",
        "- kind: `PlaywrightTest`",
        "- service: `backups`",
        "- team: `databases`",
    ):
        assert label in lines, f"{label} should be a bullet of its own"
    # An annotation of the sender's own, under its own heading, and a runbook.
    assert "**Annotations**" in lines
    assert "- impact: `backups unverified`" in lines
    assert "https://runbooks.example/synthetics" in rendered

    # alertname is the card's title and severity is its title emoji and its tag.
    assert "alertname:" not in rendered
    assert "severity:" not in rendered
    # Grafana reserves the double-underscore names for itself and hides them in its own UI. It uses them for
    # labels as well as annotations, which is what the live cards showed.
    for reserved in ("__alert_rule_uid__", "__alert_rule_namespace_uid__", "__orgId__", "__values__"):
        assert reserved not in rendered, f"{reserved} should not reach a card"
    assert "terraform-alerts" not in rendered
    # The dashboard link is a button on the card.
    assert "dashboard_url" not in rendered

    # The headings that made it a page.
    for heading in ("Severity:", "Status:", "CommonLabels", "GroupLabels", "Annotations:"):
        assert heading not in rendered, f"{heading} should not reach a card"

    assert len(rendered) < len(config.web_message)


def test_a_card_says_something_when_the_alert_carries_no_annotations():
    """A bare payload still has to render, and to say what the alert is about."""
    rendered = apply_jinja_template(
        import_module("config_integrations.alertmanager").discord_message,
        payload={"groupLabels": {"alertname": "InstanceDown", "instance": "localhost:8082"}, "commonLabels": {}},
        source_link="",
        integration_name="Alertmanager",
    )

    assert "- instance: `localhost:8082`" in rendered.splitlines()


# The default Grafana route groups by grafana_folder and alertname only, so one rule watching many workers in many
# regions arrives as a single group. service_name differs between the instances, which keeps it out of
# commonLabels, and each summary is written from it, which keeps every summary out of commonAnnotations.
QUEUE_FAILURES_PAYLOAD = {
    "status": "firing",
    "groupLabels": {"alertname": "Queue has failed jobs"},
    "commonLabels": {
        "alertname": "Queue has failed jobs",
        "deployment_cluster_name": "cloud",
        "grafana_folder": "Utopia",
        "severity": "warning",
        "team": "cloud",
    },
    "commonAnnotations": {"description": "This alert starts when a queue is holding more failed jobs than it was."},
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "Queue has failed jobs",
                "deployment_region_name": "fra",
                "k8s_cluster_name": "cloud-fra1-prod",
                "service_name": "builds",
                "severity": "warning",
            },
            "annotations": {"summary": "The `builds` queue on `cloud-fra1-prod` gained 2384 failed jobs in an hour."},
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "Queue has failed jobs",
                "deployment_region_name": "syd",
                "k8s_cluster_name": "cloud-syd1-prod",
                "service_name": "domains",
                "severity": "warning",
            },
            "annotations": {"summary": "The `domains` queue on `cloud-syd1-prod` gained 12825 failed jobs in an hour."},
        },
    ],
}


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_card_names_each_instance_a_group_holds(integration):
    """A group of many says what is in it.

    The card can only print what the instances share, and what they share is the part that does not identify
    them. Without a line per instance the reader is told a queue somewhere has failed jobs and not which queue.
    """
    config = import_module(f"config_integrations.{integration}")
    rendered = apply_jinja_template(
        config.discord_message,
        payload=QUEUE_FAILURES_PAYLOAD,
        source_link="https://grafana.example/alerting/list",
        integration_name="Grafana Alerting",
    )
    lines = rendered.splitlines()

    assert "**Instances**" in lines
    for instance in (
        "- The `builds` queue on `cloud-fra1-prod` gained 2384 failed jobs in an hour.",
        "- The `domains` queue on `cloud-syd1-prod` gained 12825 failed jobs in an hour.",
    ):
        assert instance in lines, f"{instance} should be a line of its own"
    # The names that only the instances carry, which is the whole reason the card lists them.
    for name in ("builds", "domains", "cloud-fra1-prod", "cloud-syd1-prod"):
        assert name in rendered, f"{name} is in no common label and would be lost"
    # What they do share is still said once, above.
    assert "This alert starts when a queue is holding more failed jobs than it was." in rendered
    assert "- team: `cloud`" in lines


def test_a_card_does_not_list_the_one_instance_it_already_describes():
    """A group of one has its labels and its summary in the lines above, so a list of it repeats them."""
    rendered = apply_jinja_template(
        import_module("config_integrations.grafana_alerting").discord_message,
        payload={
            "groupLabels": {"alertname": "Queue has failed jobs", "service_name": "builds"},
            "commonLabels": {"alertname": "Queue has failed jobs", "service_name": "builds"},
            "commonAnnotations": {"summary": "The `builds` queue gained 12 failed jobs in an hour."},
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Queue has failed jobs", "service_name": "builds"},
                    "annotations": {"summary": "The `builds` queue gained 12 failed jobs in an hour."},
                }
            ],
        },
        source_link="",
        integration_name="Grafana Alerting",
    )

    assert "**Instances**" not in rendered.splitlines()
    # Said once, by the summary that a group of one puts in commonAnnotations.
    assert rendered.count("The `builds` queue gained 12 failed jobs in an hour.") == 1


@pytest.mark.django_db
def test_a_dashboard_annotation_becomes_a_button_of_its_own(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    """An alert's source and its dashboard are two different places, so they are two different buttons.

    For a Grafana-managed rule the source link opens the rule itself, which is why calling that button
    "Dashboard" was wrong: the dashboard is an annotation, and it used to be reachable only by copying a URL
    out of the card's body.
    """
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_ALERTMANAGER
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(
        alert_group=alert_group,
        raw_request_data={
            "status": "firing",
            "groupLabels": {"alertname": "Test failing"},
            "commonAnnotations": {"dashboard_url": "https://grafana.example/d/synthetics"},
            "alerts": [{"status": "firing", "generatorURL": "https://grafana.example/alerting/grafana/abc/view"}],
        },
    )

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()
    buttons = {
        component["label"]: component.get("url")
        for row in payload["components"]
        for component in row["components"]
        if component.get("label")
    }

    assert buttons["Source"] == "https://grafana.example/alerting/grafana/abc/view"
    assert buttons["Dashboard"] == "https://grafana.example/d/synthetics"
    # And the body does not repeat a link that is a button.
    assert "dashboard_url" not in payload["embeds"][0].get("description", "")


@pytest.mark.django_db
def test_a_dashboard_annotation_matching_the_source_link_gets_one_button(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_ALERTMANAGER
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(
        alert_group=alert_group,
        raw_request_data={
            "status": "firing",
            "groupLabels": {"alertname": "Test failing"},
            "commonAnnotations": {"dashboard_url": "https://grafana.example/d/synthetics"},
            "alerts": [{"status": "firing", "generatorURL": "https://grafana.example/d/synthetics"}],
        },
    )

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()

    assert button_labels(payload).count("Dashboard") == 0
    assert button_labels(payload).count("Source") == 1


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_card_reads_a_legacy_payload_too(integration):
    """The legacy alertmanager integration puts labels and annotations at the top level.

    Reading only the common* keys left such an alert with a card that said nothing about itself.
    """
    rendered = apply_jinja_template(
        import_module(f"config_integrations.{integration}").discord_message,
        payload={
            "status": "firing",
            "labels": {"alertname": "InstanceDown", "instance": "localhost:8082", "job": "node"},
            "annotations": {
                "summary": "Instance is down",
                "impact": "checkout unavailable",
                "dashboard_url": "https://grafana.example/d/nodes",
            },
        },
        source_link="",
        integration_name="Alertmanager",
    )

    lines = rendered.splitlines()
    assert "Instance is down" in lines
    assert "- instance: `localhost:8082`" in lines
    assert "- job: `node`" in lines
    assert "- impact: `checkout unavailable`" in lines
    # Left to the Dashboard button, which reads the same top-level annotations.
    assert "dashboard_url" not in rendered


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_card_says_both_the_summary_and_the_description(integration):
    """A rule that wrote both meant both: one says what happened, the other what it means."""
    rendered = apply_jinja_template(
        import_module(f"config_integrations.{integration}").discord_message,
        payload={
            "groupLabels": {"alertname": "DiskSpaceLow"},
            "commonAnnotations": {
                "summary": "Disk is nearly full",
                "description": "Writes will fail within the hour at the current rate.",
            },
        },
        source_link="",
        integration_name="Alertmanager",
    )

    lines = rendered.splitlines()
    summary_at = lines.index("Disk is nearly full")
    # A blank line between them, or the two read as one run-on paragraph.
    assert lines[summary_at + 1] == ""
    assert lines[summary_at + 2] == "Writes will fail within the hour at the current rate."


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_description_alone_starts_the_card(integration):
    """The blank line parts a description from a summary, so without one there is nothing to part it from."""
    rendered = apply_jinja_template(
        import_module(f"config_integrations.{integration}").discord_message,
        payload={
            "groupLabels": {"alertname": "DiskSpaceLow"},
            "commonAnnotations": {"description": "Writes will fail within the hour at the current rate."},
        },
        source_link="",
        integration_name="Alertmanager",
    )

    assert rendered.startswith("Writes will fail within the hour at the current rate.")


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_value_string_survives_when_there_is_no_values_to_read_instead(integration):
    """It is dropped for being the long form of `values`, so without `values` it is the only form there is."""
    template = import_module(f"config_integrations.{integration}").discord_message
    annotations = {"summary": "Threshold crossed", "value_string": "[ var='A' value=42 ]"}

    without_values = apply_jinja_template(
        template,
        payload={"groupLabels": {"alertname": "Slow"}, "commonAnnotations": annotations},
        source_link="",
        integration_name="Alertmanager",
    )
    with_values = apply_jinja_template(
        template,
        payload={"groupLabels": {"alertname": "Slow"}, "commonAnnotations": {**annotations, "values": '{"A":42}'}},
        source_link="",
        integration_name="Alertmanager",
    )

    assert "- value_string: `[ var='A' value=42 ]`" in without_values.splitlines()
    assert "value_string" not in with_values
    assert '- values: `{"A":42}`' in with_values.splitlines()


@pytest.mark.django_db
def test_a_legacy_payloads_dashboard_link_still_gets_a_button(
    make_organization, make_user_for_organization, make_alert_receive_channel, make_alert_group, make_alert
):
    """The body leaves the dashboard to the button, so the button has to look where the body looks.

    A legacy alertmanager payload keeps its annotations at the top level. Reading only `commonAnnotations` here
    took the link off the card altogether: out of the body by the template, and never onto a button.
    """
    organization = make_organization()
    make_user_for_organization(organization, username="loks0n")
    alert_receive_channel = make_alert_receive_channel(
        organization, integration=AlertReceiveChannel.INTEGRATION_ALERTMANAGER
    )
    alert_group = make_alert_group(alert_receive_channel=alert_receive_channel)
    make_alert(
        alert_group=alert_group,
        raw_request_data={
            "status": "firing",
            "labels": {"alertname": "InstanceDown", "instance": "localhost:8082"},
            "annotations": {"summary": "Instance is down", "dashboard_url": "https://grafana.example/d/nodes"},
        },
    )

    payload = DiscordMessageRenderer(alert_group).render_alert_group_message()
    buttons = {
        component["label"]: component.get("url")
        for row in payload["components"]
        for component in row["components"]
        if component.get("label")
    }

    assert buttons["Dashboard"] == "https://grafana.example/d/nodes"


@pytest.mark.parametrize("integration", ["alertmanager", "grafana_alerting"])
def test_a_value_cannot_break_the_bullet_it_sits_in(integration):
    """A value is the sender's text. A newline in one would split its bullet, and a backtick would close the
    code span early, leaving the rest of the card formatted as code."""
    rendered = apply_jinja_template(
        import_module(f"config_integrations.{integration}").discord_message,
        payload={
            "groupLabels": {"alertname": "Weird"},
            "commonLabels": {"multiline": "first line\nsecond line", "ticked": "a `b` c", "plain": "fine"},
            "commonAnnotations": {"summary": "Something broke", "note": "line one\nline two"},
        },
        source_link="",
        integration_name="Alertmanager",
    )

    lines = rendered.splitlines()
    # Whitespace is collapsed, so one entry stays one bullet.
    assert "- multiline: `first line second line`" in lines
    assert "- note: `line one line two`" in lines
    # A value carrying a backtick is left unwrapped rather than altered.
    assert "- ticked: a `b` c" in lines
    assert "- plain: `fine`" in lines
    # Every bullet is still a bullet.
    for line in lines:
        assert not line.startswith("second line"), rendered
