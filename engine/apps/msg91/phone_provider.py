import logging
from random import randint

import requests
from django.core.cache import cache

from apps.base.models import LiveSetting
from apps.base.utils import live_settings
from apps.phone_notifications.exceptions import FailedToSendSMS, FailedToStartVerification
from apps.phone_notifications.phone_provider import PhoneProvider, ProviderFlags

MSG91_FLOW_URL = "https://api.msg91.com/api/v5/flow/"

logger = logging.getLogger(__name__)


class MSG91PhoneProvider(PhoneProvider):
    """
    MSG91PhoneProvider is an implementation of phone provider which supports only SMS (msg91.com).
    """

    def send_notification_sms(self, number: str, message: str):
        self.send_sms(number, message)

    def send_sms(self, number: str, text: str):
        try:
            self._send(number, text)
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"MSG91PhoneProvider.send_sms: failed {e}")
            raise FailedToSendSMS(graceful_msg=f"Failed sending sms to {number}")

    def send_verification_sms(self, number: str):
        # MSG91 has no verification service of its own, so the code is generated and checked here.
        code = self._generate_verification_code()
        cache.set(self._cache_key(number), code, timeout=10 * 60)

        try:
            self._send(number, f"Your verification code for Grafana OnCall is {code}")
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"MSG91PhoneProvider.send_verification_sms: failed {e}")
            raise FailedToStartVerification(graceful_msg=f"Failed sending verification sms to {number}")

    def _send(self, number: str, text: str):
        response = self._flow_create(number, text)
        response.raise_for_status()

        # MSG91 answers 200 with {"type": "error"} when it rejects a request, so the body has to be checked too.
        body = response.json()
        if str(body.get("type", "")).lower() != "success":
            raise ValueError(f"MSG91 rejected sms: {body}")

        logger.info(f"MSG91PhoneProvider._send: success, request_id {body.get('message')}")

    def _flow_create(self, number: str, text: str):
        payload = {
            "sender": live_settings.MSG91_SENDER_ID,
            "template_id": live_settings.MSG91_TEMPLATE_ID,
            "recipients": [
                {
                    "mobiles": number.lstrip("+"),
                    # The variable name is chosen by the MSG91 template, so both spellings in use are populated.
                    "content": text,
                    "otp": text,
                }
            ],
        }
        headers = {"Authkey": live_settings.MSG91_AUTH_KEY}

        return requests.post(MSG91_FLOW_URL, headers=headers, json=payload, timeout=10)

    def finish_verification(self, number, code):
        has = cache.get(self._cache_key(number))
        if has is not None and has == code:
            return number
        else:
            return None

    def _cache_key(self, number):
        return f"msg91_provider_{number}"

    def _generate_verification_code(self):
        return str(randint(100000, 999999))

    @property
    def flags(self) -> ProviderFlags:
        return ProviderFlags(
            configured=not LiveSetting.objects.filter(name__startswith="MSG91", error__isnull=False).exists(),
            test_sms=True,
            test_call=False,
            verification_call=False,
            verification_sms=True,
        )
