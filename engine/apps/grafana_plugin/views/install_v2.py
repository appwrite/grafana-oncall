import logging
from dataclasses import asdict, is_dataclass

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.grafana_plugin.helpers import GrafanaAPIClient
from apps.grafana_plugin.views.sync_v2 import SyncException, SyncV2View
from common.api_helpers.errors import SELF_HOSTED_ONLY_FEATURE_ERROR
from common.constants.plugin_ids import PluginID

logger = logging.getLogger(__name__)


class InstallV2View(SyncV2View):
    authentication_classes = ()
    permission_classes = ()

    @staticmethod
    def _is_authorized(request: Request) -> bool:
        configured_grafana_url = settings.SELF_HOSTED_SETTINGS["GRAFANA_API_URL"]
        try:
            sync_settings = request.data["settings"]
            supplied_grafana_url = sync_settings["grafana_url"]
            grafana_token = sync_settings["grafana_token"]
        except (KeyError, TypeError):
            return False

        if (
            not configured_grafana_url
            or not isinstance(supplied_grafana_url, str)
            or supplied_grafana_url.rstrip("/") != configured_grafana_url.rstrip("/")
            or not GrafanaAPIClient.validate_grafana_token_format(grafana_token)
        ):
            return False

        grafana_api_client = GrafanaAPIClient(api_url=configured_grafana_url, api_token=grafana_token)
        permissions, call_status = grafana_api_client.get_service_account_token_permissions()
        required_scope = f"plugins:id:{PluginID.ONCALL}"
        return (
            call_status["connected"]
            and isinstance(permissions, dict)
            and required_scope in permissions.get("plugins:write", [])
        )

    def post(self, request: Request) -> Response:
        if settings.LICENSE != settings.OPEN_SOURCE_LICENSE_NAME:
            return Response(data=asdict(SELF_HOSTED_ONLY_FEATURE_ERROR), status=status.HTTP_403_FORBIDDEN)

        if not self._is_authorized(request):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            organization = self.do_sync(request)
        except SyncException as e:
            return Response(
                data=asdict(e.error_data) if is_dataclass(e.error_data) else e.error_data,
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization.revoke_plugin()
        provisioned_data = organization.provision_plugin()

        return Response(data=provisioned_data, status=status.HTTP_200_OK)
