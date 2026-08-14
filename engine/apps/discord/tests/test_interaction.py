import json
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.alerts.models import AlertReceiveChannel
from apps.discord.views import CHANNEL_MESSAGE_WITH_SOURCE, DEFERRED_UPDATE_MESSAGE, MODAL, PONG


def interaction_url():
    return reverse("discord:incoming_discord_interaction")


def message_component(custom_id, discord_user_id):
    return {
        "type": 3,
        "data": {"custom_id": custom_id, "component_type": 2},
        "member": {"user": {"id": discord_user_id, "username": "responder"}},
    }


@pytest.fixture()
def make_alert_group_with_discord_message(
    make_organization_and_user, make_alert_receive_channel, make_alert_group, make_alert, make_discord_user
):
    def _make(**alert_group_kwargs):
        organization, user = make_organization_and_user()
        alert_receive_channel = make_alert_receive_channel(
            organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA
        )
        alert_group = make_alert_group(alert_receive_channel=alert_receive_channel, **alert_group_kwargs)
        make_alert(alert_group=alert_group, raw_request_data=alert_receive_channel.config.example_payload)
        discord_user = make_discord_user(user)
        return alert_group, user, discord_user

    return _make


@pytest.mark.django_db
def test_ping_is_ponged(sign_discord_interaction):
    body, headers = sign_discord_interaction({"type": 1})

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"type": PONG}


@pytest.mark.django_db
def test_bad_signature_is_rejected(sign_discord_interaction):
    body, headers = sign_discord_interaction({"type": 1})
    headers["HTTP_X_SIGNATURE_ED25519"] = "00" * 64

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_missing_signature_is_rejected():
    response = APIClient().post(interaction_url(), data=json.dumps({"type": 1}), content_type="application/json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_acknowledge_button_acknowledges_the_alert_group(
    make_alert_group_with_discord_message, sign_discord_interaction
):
    alert_group, user, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        message_component(f"oncall:acknowledge:{alert_group.public_primary_key}", discord_user.discord_user_id)
    )

    with patch("apps.discord.tasks.on_alert_group_action_triggered_async.apply_async"):
        response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"type": DEFERRED_UPDATE_MESSAGE}
    alert_group.refresh_from_db()
    assert alert_group.acknowledged
    assert alert_group.acknowledged_by_user == user


@pytest.mark.django_db
def test_resolve_button_resolves_the_alert_group(make_alert_group_with_discord_message, sign_discord_interaction):
    alert_group, user, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        message_component(f"oncall:resolve:{alert_group.public_primary_key}", discord_user.discord_user_id)
    )

    with patch("apps.discord.tasks.on_alert_group_action_triggered_async.apply_async"):
        APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    alert_group.refresh_from_db()
    assert alert_group.resolved


@pytest.mark.django_db
def test_unlinked_discord_account_is_told_so(make_alert_group_with_discord_message, sign_discord_interaction):
    alert_group, _, _ = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        message_component(f"oncall:acknowledge:{alert_group.public_primary_key}", "1300000000000009999")
    )

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.json()["type"] == CHANNEL_MESSAGE_WITH_SOURCE
    assert response.json()["data"]["flags"] == 64
    alert_group.refresh_from_db()
    assert not alert_group.acknowledged


@pytest.mark.django_db
def test_unknown_custom_id_does_nothing(make_alert_group_with_discord_message, sign_discord_interaction):
    alert_group, _, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(message_component("something:else:entirely", discord_user.discord_user_id))

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_200_OK
    alert_group.refresh_from_db()
    assert not alert_group.acknowledged


def slash_command(code, discord_user_id, name="oncall-link"):
    return {
        "type": 2,
        "data": {"name": name, "options": [{"name": "code", "value": code}]},
        "member": {"user": {"id": discord_user_id, "username": "responder"}},
    }


@pytest.mark.django_db
def test_link_command_links_the_account(make_organization_and_user, sign_discord_interaction):
    from apps.discord.backend import DiscordBackend

    _, user = make_organization_and_user()
    code = DiscordBackend().generate_user_verification_code(user)
    body, headers = sign_discord_interaction(slash_command(code, "1300000000000000042"))

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.json()["data"]["flags"] == 64
    user.refresh_from_db()
    assert user.discord_user_identity.discord_user_id == "1300000000000000042"


@pytest.mark.django_db
def test_link_command_with_a_bad_code_links_nothing(make_organization_and_user, sign_discord_interaction):
    _, user = make_organization_and_user()
    body, headers = sign_discord_interaction(slash_command("not-a-code", "1300000000000000042"))

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert "not valid" in response.json()["data"]["content"]
    assert not hasattr(user, "discord_user_identity")


@pytest.mark.django_db
def test_unknown_command_is_ignored(make_organization_and_user, sign_discord_interaction):
    body, headers = sign_discord_interaction(slash_command("code", "1300000000000000042", name="something-else"))

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_button_for_another_organization_does_nothing(
    make_alert_group_with_discord_message,
    make_organization_and_user,
    make_alert_receive_channel,
    make_alert_group,
    make_alert,
    sign_discord_interaction,
):
    _, _, discord_user = make_alert_group_with_discord_message()
    other_organization, _ = make_organization_and_user()
    other_channel = make_alert_receive_channel(other_organization, integration=AlertReceiveChannel.INTEGRATION_GRAFANA)
    other_alert_group = make_alert_group(alert_receive_channel=other_channel)
    make_alert(alert_group=other_alert_group, raw_request_data=other_channel.config.example_payload)

    body, headers = sign_discord_interaction(
        message_component(f"oncall:acknowledge:{other_alert_group.public_primary_key}", discord_user.discord_user_id)
    )
    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.status_code == status.HTTP_200_OK
    other_alert_group.refresh_from_db()
    assert not other_alert_group.acknowledged


def select(custom_id, values, discord_user_id):
    return {
        "type": 3,
        "data": {"custom_id": custom_id, "component_type": 3, "values": values},
        "member": {"user": {"id": discord_user_id, "username": "responder"}},
    }


@pytest.mark.django_db
def test_silence_select_silences_for_the_chosen_duration(
    make_alert_group_with_discord_message, sign_discord_interaction
):
    alert_group, user, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        select(f"oncall:silence:{alert_group.public_primary_key}", ["3600"], discord_user.discord_user_id)
    )

    with patch("apps.discord.tasks.on_alert_group_action_triggered_async.apply_async"):
        response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.json() == {"type": DEFERRED_UPDATE_MESSAGE}
    alert_group.refresh_from_db()
    assert alert_group.silenced
    assert alert_group.silenced_by_user == user


@pytest.mark.django_db
def test_paging_a_responder_adds_them_to_the_escalation(
    make_alert_group_with_discord_message, make_user_for_organization, sign_discord_interaction
):
    alert_group, user, discord_user = make_alert_group_with_discord_message()
    responder = make_user_for_organization(user.organization, username="eldad")
    body, headers = sign_discord_interaction(
        select(
            f"oncall:page:{alert_group.public_primary_key}",
            [responder.public_primary_key],
            discord_user.discord_user_id,
        )
    )

    with patch("apps.alerts.paging.direct_paging") as direct_paging:
        APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    _, kwargs = direct_paging.call_args
    assert kwargs["users"] == [(responder, False)]
    assert kwargs["alert_group"] == alert_group
    assert kwargs["from_user"] == user


@pytest.mark.django_db
def test_paging_a_user_from_another_organization_does_nothing(
    make_alert_group_with_discord_message, make_organization_and_user, sign_discord_interaction
):
    alert_group, _, discord_user = make_alert_group_with_discord_message()
    _, outsider = make_organization_and_user()
    body, headers = sign_discord_interaction(
        select(
            f"oncall:page:{alert_group.public_primary_key}",
            [outsider.public_primary_key],
            discord_user.discord_user_id,
        )
    )

    with patch("apps.alerts.paging.direct_paging") as direct_paging:
        APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    direct_paging.assert_not_called()


@pytest.mark.django_db
def test_resolution_note_button_opens_a_modal(make_alert_group_with_discord_message, sign_discord_interaction):
    alert_group, _, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        message_component(f"oncall:note:{alert_group.public_primary_key}", discord_user.discord_user_id)
    )

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    modal = response.json()
    assert modal["type"] == MODAL
    assert modal["data"]["custom_id"] == f"oncall:note-submit:{alert_group.public_primary_key}"
    # A Label wrapping one input, not the deprecated action row.
    label = modal["data"]["components"][0]
    assert label["type"] == 18
    assert label["component"]["custom_id"] == "text"
    assert label["component"]["type"] == 4


def label_submission(alert_group, discord_user_id, text):
    """What Discord sends back from a Label-wrapped input."""
    return {
        "type": 5,
        "data": {
            "custom_id": f"oncall:note-submit:{alert_group.public_primary_key}",
            "components": [
                {"type": 18, "id": 1, "component": {"type": 4, "id": 2, "custom_id": "text", "value": text}}
            ],
        },
        "member": {"user": {"id": discord_user_id, "username": "responder"}},
    }


def action_row_submission(alert_group, discord_user_id, text):
    """What a modal opened before the Label migration still sends back."""
    return {
        "type": 5,
        "data": {
            "custom_id": f"oncall:note-submit:{alert_group.public_primary_key}",
            "components": [{"type": 1, "components": [{"type": 4, "custom_id": "text", "value": text}]}],
        },
        "member": {"user": {"id": discord_user_id, "username": "responder"}},
    }


@pytest.mark.django_db
@pytest.mark.parametrize("submission", [label_submission, action_row_submission])
def test_submitting_the_modal_saves_a_resolution_note(
    make_alert_group_with_discord_message, sign_discord_interaction, submission
):
    from apps.alerts.models import ResolutionNote

    alert_group, user, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(
        submission(alert_group, discord_user.discord_user_id, "restarted the pooler")
    )

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert response.json()["data"]["flags"] == 64
    note = alert_group.resolution_notes.get()
    assert note.message_text == "restarted the pooler"
    assert note.author == user
    assert note.source == ResolutionNote.Source.DISCORD


@pytest.mark.django_db
def test_an_empty_resolution_note_is_refused(make_alert_group_with_discord_message, sign_discord_interaction):
    alert_group, _, discord_user = make_alert_group_with_discord_message()
    body, headers = sign_discord_interaction(label_submission(alert_group, discord_user.discord_user_id, "   "))

    response = APIClient().post(interaction_url(), data=body, content_type="application/json", **headers)

    assert "needs some text" in response.json()["data"]["content"]
    assert not alert_group.resolution_notes.exists()
