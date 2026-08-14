"""OnCall escalating to "everyone" says so in the channel, as well as reaching people through their policies."""

from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.alerts.models import AlertGroupLogRecord, AlertReceiveChannel, EscalationPolicy
from apps.discord.alert_group_representative import AlertGroupDiscordRepresentative
from apps.discord.models import DiscordMessage

ROLE = "1300000000000000777"


@pytest.fixture()
def escalate(
    make_organization,
    make_discord_channel,
    make_alert_receive_channel,
    make_channel_filter,
    make_alert_group,
    make_alert,
    make_discord_message,
    make_alert_group_log_record,
):
    def _escalate(
        step=EscalationPolicy.STEP_FINAL_NOTIFYALL,
        notification_backends=None,
        thread_id=None,
        **alert_group_kwargs,
    ):
        if notification_backends is None:
            notification_backends = {"DISCORD": {"role": ROLE}}
        organization = make_organization()
        make_discord_channel(organization=organization, is_default_channel=True)
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        channel_filter = make_channel_filter(alert_receive_channel, notification_backends=notification_backends)
        alert_group = make_alert_group(
            alert_receive_channel=alert_receive_channel, channel_filter=channel_filter, **alert_group_kwargs
        )
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        make_discord_message(
            alert_group=alert_group, message_type=DiscordMessage.ALERT_GROUP_MESSAGE, thread_id=thread_id
        )
        log_record = make_alert_group_log_record(
            alert_group, type=AlertGroupLogRecord.TYPE_ESCALATION_TRIGGERED, author=None, escalation_policy_step=step
        )
        return alert_group, AlertGroupDiscordRepresentative(log_record=log_record)

    return _escalate


def posted(create_message):
    return create_message.call_args[1]["data"]


@pytest.mark.django_db
def test_escalating_to_everyone_pings_the_route_role(escalate):
    alert_group, representative = escalate()

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    data = posted(create_message)
    assert "<@&1300000000000000777>" in data["content"]
    # Only the role being escalated to, whatever the alert text happens to name.
    assert data["allowed_mentions"] == {"parse": [], "roles": [ROLE]}
    assert data["message_reference"]["message_id"] == alert_group.discord_messages.get().message_id


@pytest.mark.django_db
def test_escalating_inside_a_forum_post_needs_no_reply(escalate):
    alert_group, representative = escalate(thread_id="1300000000000000009")

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    assert create_message.call_args[1]["channel_id"] == "1300000000000000009"
    assert "message_reference" not in posted(create_message)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "step",
    [EscalationPolicy.STEP_NOTIFY_GROUP, EscalationPolicy.STEP_NOTIFY_GROUP_IMPORTANT],
)
def test_notify_group_steps_broadcast_too(escalate, step):
    alert_group, representative = escalate(step=step)

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    create_message.assert_called_once()


@pytest.mark.django_db
def test_a_step_that_reaches_one_person_stays_quiet(escalate):
    alert_group, representative = escalate(step=EscalationPolicy.STEP_NOTIFY_SCHEDULE)

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_a_route_with_no_role_still_tells_the_channel(escalate):
    """A step that means "notify everyone" has to say something, ping or no ping.

    The role is what makes it loud, not what makes it happen — and whether a route names one is not
    knowable when the step is added to a chain, so silence here would be silence nobody could predict.
    """
    alert_group, representative = escalate(notification_backends={"DISCORD": {"enabled": True}})

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    _, kwargs = create_message.call_args
    assert "still unacknowledged" in kwargs["data"]["content"]
    assert "<@&" not in kwargs["data"]["content"]
    assert kwargs["data"]["allowed_mentions"] == {"parse": [], "roles": []}


@pytest.mark.django_db
def test_an_already_acknowledged_alert_group_is_not_escalated(escalate):
    alert_group, representative = escalate(acknowledged=True, acknowledged_at=timezone.now())

    with patch("apps.discord.alert_group_representative.DiscordClient.create_message") as create_message:
        representative.get_handler()(alert_group)

    create_message.assert_not_called()


@pytest.mark.django_db
def test_the_public_api_accepts_notify_whole_channel_for_a_discord_organization(
    make_organization_and_user_with_token,
    make_discord_channel,
):
    """A connected forum is something that can be notified, so the step can be provisioned.

    The reconciler that owns the escalation chain writes it through the public API, which used to refuse
    this step to anyone without Slack — leaving a chain that pages on-call and then stops.
    """
    from django.urls import reverse
    from rest_framework import status
    from rest_framework.test import APIClient

    organization, _, token = make_organization_and_user_with_token()
    escalation_chain = organization.escalation_chains.create(name="test_chain")
    assert organization.slack_team_identity is None
    make_discord_channel(organization=organization, is_default_channel=True)

    response = APIClient().post(
        reverse("api-public:escalation_policies-list"),
        data={
            "escalation_chain_id": escalation_chain.public_primary_key,
            "type": EscalationPolicy.PUBLIC_STEP_CHOICES_MAP[EscalationPolicy.STEP_FINAL_NOTIFYALL],
            "position": 0,
        },
        format="json",
        HTTP_AUTHORIZATION=token,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert EscalationPolicy.objects.get(public_primary_key=response.json()["id"]).step == (
        EscalationPolicy.STEP_FINAL_NOTIFYALL
    )


@pytest.mark.django_db
def test_a_discord_organization_still_cannot_use_the_slack_user_group_steps(
    make_organization_and_user_with_plugin_token,
    make_discord_channel,
    make_user_auth_headers,
):
    """Notifying a Slack user group is served by a task that gives up without Slack.

    A connected forum makes "notify whole channel" serviceable; it does not conjure a user group.
    """
    from django.urls import reverse
    from rest_framework import status
    from rest_framework.test import APIClient

    organization, user, token = make_organization_and_user_with_plugin_token()
    escalation_chain = organization.escalation_chains.create(name="test_chain")
    make_discord_channel(organization=organization, is_default_channel=True)

    response = APIClient().post(
        reverse("api-internal:escalation_policy-list"),
        data={
            "escalation_chain": escalation_chain.public_primary_key,
            "step": EscalationPolicy.STEP_NOTIFY_GROUP,
        },
        format="json",
        **make_user_auth_headers(user, token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Slack-specific" in str(response.json())
