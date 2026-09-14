import importlib
import json
import logging
from unittest.mock import patch

import pytest
from jinja2.exceptions import SecurityError

from common.jinja_templater.apply_jinja_template import JinjaTemplateError, apply_jinja_template


@pytest.mark.parametrize("error", [SecurityError("secret\nforged=true"), RuntimeError("secret\nforged=true")])
def test_template_failure_does_not_log_template_payload_or_exception(error, caplog):
    with patch("common.jinja_templater.apply_jinja_template.jinja_template_env.from_string", side_effect=error):
        with pytest.raises(JinjaTemplateError):
            apply_jinja_template("secret\nforged=true", payload={"secret": "private"})
    assert caplog.records
    assert "secret" not in caplog.text
    assert "private" not in caplog.text
    assert "forged" not in caplog.text


@pytest.mark.parametrize(
    "module,function,args",
    [
        ("apps.twilioapp.status_callback", "update_twilio_call_status", ("sid\nforged=true", "bad\nstatus")),
        ("apps.twilioapp.status_callback", "update_twilio_sms_status", ("sid\nforged=true", "bad\nstatus")),
        ("apps.exotel.status_callback", "update_exotel_call_status", ("sid\nforged=true", "bad\nstatus")),
        ("apps.zvonok.status_callback", "update_zvonok_call_status", ("sid\nforged=true", "bad\nstatus")),
    ],
)
def test_unknown_callback_fields_are_json_quoted(module, function, args, caplog):
    caplog.set_level(logging.INFO)
    getattr(importlib.import_module(module), function)(*args)
    assert caplog.records
    for record in caplog.records:
        message = record.getMessage()
        assert "\n" not in message
        assert json.dumps(args[0]) in message
        assert json.dumps(args[1]) in message


def test_gather_fields_are_json_quoted(caplog):
    from apps.twilioapp.gather import process_digit

    caplog.set_level(logging.INFO)
    with patch("apps.twilioapp.gather.TwilioPhoneCall.objects.filter") as calls:
        calls.return_value.first.return_value = None
        process_digit("sid\nforged=true", "1\nforged=true")
    assert caplog.records
    assert all("\n" not in record.getMessage() for record in caplog.records)
    assert 'sid="sid\\nforged=true"' in caplog.records[0].getMessage()


def test_slack_request_id_is_quoted_before_signature_validation(caplog):
    from rest_framework.test import APIRequestFactory

    from apps.slack.views import SlackEventApiEndpointView

    caplog.set_level(logging.INFO)
    request_id = 'untrusted" forged=true\tvalue'
    request = APIRequestFactory().post("/", {}, HTTP_X_REQUEST_ID=request_id)
    response = SlackEventApiEndpointView.as_view()(request)
    assert response.status_code == 403
    assert caplog.records[0].getMessage() == "Request id: " + json.dumps(request_id)


@pytest.mark.parametrize("user_id", [None, 7])
def test_status_logs_ids_and_supports_unprovisioned_users(user_id, settings, caplog):
    from types import SimpleNamespace

    from apps.grafana_plugin.views.status import StatusView

    settings.CURRENTLY_UNDERGOING_MAINTENANCE_MESSAGE = "Maintenance"
    user = SimpleNamespace(pk=user_id, username="untrusted\nname") if user_id else None
    request = SimpleNamespace(
        successful_authenticator=None,
        user=user,
        auth=SimpleNamespace(organization=SimpleNamespace(pk=42, stack_slug="untrusted\nslug")),
    )
    caplog.set_level(logging.INFO)
    response = StatusView().post(request)
    assert response.status_code == 200
    assert caplog.records[0].getMessage() == f"authenticated via NoneType user_id={user_id} organization_id=42"
