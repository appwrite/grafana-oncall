import json
from unittest.mock import patch

import pytest
import responses
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grafana_plugin.views.sync_v2 import SyncException
from apps.user_management.models import Organization
from common.api_helpers.errors import INVALID_SELF_HOSTED_ID

GRAFANA_URL = "http://trusted-grafana:3000"
PUBLIC_GRAFANA_URL = "https://grafana.example.com"
GRAFANA_TOKEN = "a-valid-grafana-token"
SELF_HOSTED_SETTINGS = {
    **settings.SELF_HOSTED_SETTINGS,
    "GRAFANA_API_URL": GRAFANA_URL,
    "GRAFANA_PUBLIC_URL": PUBLIC_GRAFANA_URL,
}


def install_data(grafana_url=PUBLIC_GRAFANA_URL, grafana_token=GRAFANA_TOKEN):
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
def test_install_v2_rejects_untrusted_public_grafana_url():
    client = APIClient()

    with patch("apps.grafana_plugin.views.install_v2.GrafanaAPIClient.get_service_account_token_permissions") as auth:
        response = client.post(
            reverse("grafana-plugin:install-v2"),
            install_data(grafana_url="https://attacker.example.com"),
            format="json",
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    auth.assert_not_called()


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
@pytest.mark.parametrize("grafana_url", [PUBLIC_GRAFANA_URL, GRAFANA_URL, GRAFANA_URL + "/"])
def test_install_v2_validates_token_against_configured_grafana_url(grafana_url):
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
            reverse("grafana-plugin:install-v2"), install_data(grafana_url=grafana_url), format="json"
        )

    grafana_api_client.assert_called_once_with(api_url=GRAFANA_URL, api_token=GRAFANA_TOKEN)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
@pytest.mark.parametrize(
    ("permissions", "connected"),
    [
        ({"plugins:write": ["plugins:id:another-plugin"]}, True),
        ({"plugins:read": ["plugins:*"]}, True),
        ({"plugins:write": ["teams:*"]}, True),
        ({"plugins:write": ["plugins:*"]}, False),
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


@pytest.mark.django_db
@override_settings(SELF_HOSTED_SETTINGS=SELF_HOSTED_SETTINGS)
@pytest.mark.parametrize("grafana_url", [GRAFANA_URL, PUBLIC_GRAFANA_URL])
@pytest.mark.parametrize("write_scope", ["plugins:id:grafana-oncall-app", "plugins:*"])
def test_install_and_sync_keep_public_links_and_internal_callbacks(grafana_url, write_scope):
    token = "glsa_abcdefghijklmnopqrstuvwxyz"
    data = {
        "settings": {
            "grafana_url": grafana_url,
            "grafana_token": token,
            "stack_id": SELF_HOSTED_SETTINGS["STACK_ID"],
            "org_id": SELF_HOSTED_SETTINGS["ORG_ID"],
            "license": settings.OPEN_SOURCE_LICENSE_NAME,
            "oncall_api_url": "http://oncall:8080",
            "oncall_token": "",
            "rbac_enabled": False,
            "incident_enabled": False,
            "incident_backend_url": "",
            "labels_enabled": False,
        },
        "users": [],
        "teams": [],
        "team_members": {},
    }
    client = APIClient()
    with responses.RequestsMock() as http:
        http.get(
            GRAFANA_URL + "/api/access-control/user/permissions",
            json={"plugins:write": [write_scope]},
        )
        http.head(GRAFANA_URL + "/api/org", status=200)
        response = client.post(reverse("grafana-plugin:install-v2"), data, format="json")
        assert response.status_code == status.HTTP_200_OK
        organization = Organization.objects.get()
        assert organization.grafana_url == PUBLIC_GRAFANA_URL
        assert organization.api_token_status == Organization.API_TOKEN_STATUS_OK

        response = client.post(
            reverse("grafana-plugin:sync-v2"),
            data,
            format="json",
            HTTP_AUTHORIZATION=response.data["onCallToken"],
            HTTP_X_INSTANCE_CONTEXT=json.dumps({"stack_id": organization.stack_id, "org_id": organization.org_id}),
        )
        assert response.status_code == status.HTTP_200_OK
        organization.refresh_from_db()
        assert organization.grafana_url == PUBLIC_GRAFANA_URL
        assert all(call.request.headers["Authorization"] == f"Bearer {token}" for call in http.calls)
