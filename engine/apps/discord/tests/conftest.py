import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings

if not settings.FEATURE_DISCORD_INTEGRATION_ENABLED:
    pytest.skip("Discord integration is not enabled", allow_module_level=True)
else:
    from apps.discord.tests.factories import DiscordChannelFactory, DiscordMessageFactory, DiscordUserFactory


@pytest.fixture()
def make_discord_channel():
    def _make_discord_channel(organization, **kwargs):
        return DiscordChannelFactory(organization=organization, **kwargs)

    return _make_discord_channel


@pytest.fixture()
def make_discord_message():
    def _make_discord_message(alert_group, message_type, **kwargs):
        return DiscordMessageFactory(alert_group=alert_group, message_type=message_type, **kwargs)

    return _make_discord_message


@pytest.fixture()
def make_discord_user():
    def _make_discord_user(user, **kwargs):
        return DiscordUserFactory(user=user, **kwargs)

    return _make_discord_user


@pytest.fixture()
def sign_discord_interaction(settings):
    """Sign an interaction the way Discord does, with a key the engine will accept for the duration of the test."""
    private_key = Ed25519PrivateKey.generate()
    settings.DISCORD_PUBLIC_KEY = private_key.public_key().public_bytes_raw().hex()

    def _sign(payload, timestamp="1728823418"):
        body = json.dumps(payload).encode()
        signature = private_key.sign(timestamp.encode() + body).hex()
        return body, {
            "HTTP_X_SIGNATURE_ED25519": signature,
            "HTTP_X_SIGNATURE_TIMESTAMP": timestamp,
        }

    return _sign


@pytest.fixture()
def make_discord_message_response():
    def _make_discord_message_response(**kwargs):
        return {
            "id": kwargs.get("id", "1300000000000000001"),
            "channel_id": kwargs.get("channel_id", "1300000000000000002"),
        }

    return _make_discord_message_response
