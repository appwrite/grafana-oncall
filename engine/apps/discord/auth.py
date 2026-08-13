import logging
import typing

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings

from apps.discord.models import DiscordUser
from apps.user_management.models import User

logger = logging.getLogger(__name__)


def verify_signature(request) -> bool:
    """
    Discord signs every interaction with the application's Ed25519 key over `timestamp + body`, and refuses to
    register an endpoint that does not answer 401 to a bad signature.

    https://discord.com/developers/docs/interactions/overview#setting-up-an-endpoint-validating-security-request-headers
    """
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    public_key = settings.DISCORD_PUBLIC_KEY

    if not signature or not timestamp or not public_key:
        return False

    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
            bytes.fromhex(signature), timestamp.encode() + request.body
        )
    except (InvalidSignature, ValueError) as e:
        logger.info(f"Error while verifying discord interaction signature {e}")
        return False

    return True


def get_user(interaction: dict) -> typing.Optional[User]:
    """The OnCall user behind an interaction, or None when the Discord account is not linked to one.

    Discord nests the user under `member` in a guild and under `user` in a DM.
    """
    user = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    discord_user_id = user.get("id")
    if not discord_user_id:
        return None

    discord_user = DiscordUser.objects.filter(discord_user_id=discord_user_id).first()
    return discord_user.user if discord_user else None
