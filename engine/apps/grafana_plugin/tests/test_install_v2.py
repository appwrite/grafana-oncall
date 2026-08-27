from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grafana_plugin.views.sync_v2 import SyncException
from common.api_helpers.errors import INVALID_SELF_HOSTED_ID

GRAFANA_URL = "http://trusted-grafana:3000"
PUBLIC_GRAFANA_URL = "https://grafana.example.com"
GRAFANA_TOKEN = "a-valid-grafana-token"
SELF_HOSTED_SETTINGS = {**settings.SELF_HOSTED_SETTINGS, "GRAFANA_API_URL": GRAFANA_URL}


def install_data(grafana_url=GRAFANA_URL, grafana_token=GRAFANA_TOKEN):
    return {"settings": {"grafana_url": grafana_url, "grafana_token": grafana_token}}


@override_settings(SELF_HOSTED_SETTINGS={**SELF_HOSTED_SETTINGS, "GRAFANA_API_URL": None})
def test_install_v2_fails_closed_without_a_configured_grafana_url():
    client = APIClient()

    with patch("apps.grafana_plugin.views.InstallV2View.do_sync") as do_sync:
        response = client.post(reverse("grafana-plugin:install-v2"), install_data(), format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    do_sync.assert_not_called()


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
def test_install_v2_rejects_invalid_token():
    client = APIClient()

    with patch("apps.grafana_plugin.views.install_v2.GrafanaAPIClient.get_service_account_token_permissions") as auth:
        response = client.post(reverse("grafana-plugin:install-v2"), install_data(grafana_token="short"), format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    auth.assert_not_called()


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
def test_install_v2_validates_token_against_configured_grafana_url():
    client = APIClient()
    permissions = {"plugins:write": ["plugins:id:grafana-oncall-app"]}
    exc = SyncException(INVALID_SELF_HOSTED_ID)

    with (
        patch("apps.grafana_plugin.views.install_v2.GrafanaAPIClient") as grafana_api_client,
        patch("apps.grafana_plugin.views.InstallV2View.do_sync", side_effect=exc),
    ):
        grafana_api_client.validate_grafana_token_format.return_value = True
        grafana_api_client.return_value.get_service_account_token_permissions.return_value = (
            permissions,
            {"connected": True},
        )
        response = client.post(
            reverse("grafana-plugin:install-v2"), install_data(grafana_url=PUBLIC_GRAFANA_URL), format="json"
        )

    grafana_api_client.assert_called_once_with(api_url=GRAFANA_URL, api_token=GRAFANA_TOKEN)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
@pytest.mark.parametrize(
    ("permissions", "connected"),
    [
        ({"plugins:write": ["plugins:id:another-plugin"]}, True),
        ({"plugins:write": ["plugins:id:grafana-oncall-app"]}, False),
    ],
)
def test_install_v2_requires_plugin_write_permission_from_trusted_grafana(permissions, connected):
    client = APIClient()

    with (
        patch(
            "apps.grafana_plugin.views.install_v2.GrafanaAPIClient.get_service_account_token_permissions",
            return_value=(permissions, {"connected": connected}),
        ),
        patch("apps.grafana_plugin.views.InstallV2View.do_sync") as do_sync,
    ):
        response = client.post(reverse("grafana-plugin:install-v2"), install_data(), format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    do_sync.assert_not_called()


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
def test_install_v2_error_encoding_for_authorized_grafana_token():
    client = APIClient()
    permissions = {"plugins:write": ["plugins:id:grafana-oncall-app"]}
    exc = SyncException(INVALID_SELF_HOSTED_ID)

    with (
        patch(
            "apps.grafana_plugin.views.install_v2.GrafanaAPIClient.get_service_account_token_permissions",
            return_value=(permissions, {"connected": True}),
        ),
        patch("apps.grafana_plugin.views.InstallV2View.do_sync", side_effect=exc),
    ):
        response = client.post(reverse("grafana-plugin:install-v2"), install_data(), format="json")

    assert response.data["code"] == INVALID_SELF_HOSTED_ID.code
    assert response.data["message"] == INVALID_SELF_HOSTED_ID.message
    assert response.status_code == status.HTTP_400_BAD_REQUEST
