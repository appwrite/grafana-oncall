import logging

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import RBACPermission, user_is_authorized
from apps.auth_token.auth import PluginAuthentication
from apps.discord.auth import get_user, verify_signature
from apps.discord.commands import LINK_COMMAND_NAME
from apps.discord.events import process_interaction
from apps.discord.models import DiscordChannel
from apps.discord.serializers import DiscordChannelSerializer
from apps.discord.utils import link_user
from common.api_helpers.mixins import PublicPrimaryKeyMixin
from common.insight_log.chatops_insight_logs import ChatOpsEvent, ChatOpsTypePlug, write_chatops_insight_log

logger = logging.getLogger(__name__)

# https://discord.com/developers/docs/interactions/receiving-and-responding
PING, APPLICATION_COMMAND, MESSAGE_COMPONENT = 1, 2, 3
PONG, CHANNEL_MESSAGE_WITH_SOURCE, DEFERRED_UPDATE_MESSAGE = 1, 4, 6
EPHEMERAL = 1 << 6


class DiscordChannelViewSet(
    PublicPrimaryKeyMixin[DiscordChannel],
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = (PluginAuthentication,)
    permission_classes = (IsAuthenticated, RBACPermission)

    rbac_permissions = {
        "list": [RBACPermission.Permissions.CHATOPS_READ],
        "retrieve": [RBACPermission.Permissions.CHATOPS_READ],
        "create": [RBACPermission.Permissions.CHATOPS_UPDATE_SETTINGS],
        "destroy": [RBACPermission.Permissions.CHATOPS_UPDATE_SETTINGS],
        "set_default": [RBACPermission.Permissions.CHATOPS_UPDATE_SETTINGS],
    }

    serializer_class = DiscordChannelSerializer

    def get_queryset(self):
        return DiscordChannel.objects.filter(organization=self.request.user.organization)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk):
        self.get_object().make_channel_default(request.user)
        return Response(status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save()
        write_chatops_insight_log(
            author=self.request.user,
            event_name=ChatOpsEvent.CHANNEL_CONNECTED,
            chatops_type=ChatOpsTypePlug.DISCORD.value,
            channel_name=serializer.instance.channel_name,
        )

    def perform_destroy(self, instance):
        write_chatops_insight_log(
            author=self.request.user,
            event_name=ChatOpsEvent.CHANNEL_DISCONNECTED,
            chatops_type=ChatOpsTypePlug.DISCORD.value,
            channel_name=instance.channel_name,
            channel_id=instance.channel_id,
        )
        instance.delete()


class DiscordInteractionView(APIView):
    """Discord's Interactions Endpoint URL: every button press on an alert group card arrives here.

    Authentication is the Ed25519 signature rather than a session, so the view takes no DRF authentication class; the
    OnCall user is whichever one the pressing Discord account is linked to.
    """

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        if not verify_signature(request):
            return Response("invalid request signature", status=status.HTTP_401_UNAUTHORIZED)

        interaction = request.data
        if interaction.get("type") == PING:
            return Response({"type": PONG})

        if interaction.get("type") == APPLICATION_COMMAND:
            return self._link_account(interaction)

        if interaction.get("type") != MESSAGE_COMPONENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        user = get_user(interaction)
        if user is None:
            return _ephemeral("Your Discord account is not linked to a Grafana OnCall user.")
        if not user_is_authorized(user, [RBACPermission.Permissions.ALERT_GROUPS_WRITE]):
            return _ephemeral("You do not have permission to update alert groups.")

        process_interaction(interaction.get("data", {}).get("custom_id", ""), user)

        # The card is edited by the alert group representative once OnCall records the action, so the press itself
        # needs no reply beyond acknowledging it.
        return Response({"type": DEFERRED_UPDATE_MESSAGE})

    def _link_account(self, interaction) -> Response:
        """`/oncall-link code:<code>`, the Discord half of linking an account to an OnCall user.

        Discord cannot carry a payload into a slash command, so the code is read from OnCall and pasted here. Every
        reply is ephemeral: the code is a bearer credential until it expires, and nobody else in the channel needs
        to see it.
        """
        data = interaction.get("data", {})
        if data.get("name") != LINK_COMMAND_NAME:
            return Response(status=status.HTTP_204_NO_CONTENT)

        author = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
        code = next((option.get("value", "") for option in data.get("options", []) if option.get("name") == "code"), "")

        discord_user = link_user(
            code=code,
            discord_user_id=author.get("id", ""),
            username=author.get("username", ""),
        )
        if discord_user is None:
            return _ephemeral("That verification code is not valid, or it has expired. Generate a new one in OnCall.")
        return _ephemeral(f"This Discord account is now linked to {discord_user.user.username} 🎉")


def _ephemeral(content: str) -> Response:
    return Response({"type": CHANNEL_MESSAGE_WITH_SOURCE, "data": {"content": content, "flags": EPHEMERAL}})
