from unittest.mock import patch

import pytest
import responses
from django.test import override_settings

from apps.msg91.phone_provider import MSG91_FLOW_URL, MSG91PhoneProvider
from apps.phone_notifications.exceptions import FailedToSendSMS, FailedToStartVerification


@pytest.fixture
def provider():
    return MSG91PhoneProvider()


@pytest.fixture(autouse=True)
def msg91_settings():
    with override_settings(MSG91_AUTH_KEY="auth-key", MSG91_SENDER_ID="ONCALL", MSG91_TEMPLATE_ID="template-id"):
        yield


@pytest.mark.django_db
@responses.activate
def test_send_notification_sms(provider):
    responses.add(responses.POST, MSG91_FLOW_URL, json={"message": "req-id", "type": "success"}, status=200)

    provider.send_notification_sms("+1234567890", "dummy message")

    request = responses.calls[0].request
    assert request.headers["Authkey"] == "auth-key"
    assert responses.calls[0].request.body == (
        b'{"sender": "ONCALL", "template_id": "template-id", "recipients": '
        b'[{"mobiles": "1234567890", "content": "dummy message", "otp": "dummy message"}]}'
    )


@pytest.mark.django_db
@responses.activate
def test_send_sms_http_error(provider):
    responses.add(responses.POST, MSG91_FLOW_URL, json={"message": "unauthorized"}, status=401)

    with pytest.raises(FailedToSendSMS):
        provider.send_sms("+1234567890", "dummy message")


@pytest.mark.django_db
@responses.activate
def test_send_sms_rejected(provider):
    responses.add(responses.POST, MSG91_FLOW_URL, json={"message": "invalid template", "type": "error"}, status=200)

    with pytest.raises(FailedToSendSMS):
        provider.send_sms("+1234567890", "dummy message")


@pytest.mark.django_db
@responses.activate
def test_send_verification_sms(provider):
    responses.add(responses.POST, MSG91_FLOW_URL, json={"message": "req-id", "type": "success"}, status=200)

    with patch("django.core.cache.cache.set") as cache_set:
        with patch.object(provider, "_generate_verification_code", return_value="123456"):
            provider.send_verification_sms("+1234567890")

    assert b"Your verification code for Grafana OnCall is 123456" in responses.calls[0].request.body
    cache_set.assert_called_once_with("msg91_provider_+1234567890", "123456", timeout=600)


@pytest.mark.django_db
@responses.activate
def test_send_verification_sms_rejected(provider):
    responses.add(responses.POST, MSG91_FLOW_URL, json={"type": "error"}, status=200)

    with patch("django.core.cache.cache.set"):
        with pytest.raises(FailedToStartVerification):
            provider.send_verification_sms("+1234567890")


@pytest.mark.django_db
def test_finish_verification(provider):
    number = "+1234567890"

    with patch("django.core.cache.cache.get", return_value="123456"):
        assert provider.finish_verification(number, "123456") == number
        assert provider.finish_verification(number, "654321") is None
