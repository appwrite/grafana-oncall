import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_regex_is_required_for_route_regex_debugger(
    make_organization_and_user_with_plugin_token, make_user_auth_headers, make_escalation_chain
):
    organization, user, token = make_organization_and_user_with_plugin_token()
    make_escalation_chain(organization)
    client = APIClient()
    url = reverse("api-internal:route_regex_debugger")
    response = client.get(url, format="text/plain", **make_user_auth_headers(user, token))
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_invalid_regex_for_route_regex_debugger(
    make_organization_and_user_with_plugin_token, make_user_auth_headers, make_escalation_chain
):
    organization, user, token = make_organization_and_user_with_plugin_token()
    make_escalation_chain(organization)
    client = APIClient()
    url = reverse("api-internal:route_regex_debugger")
    response = client.get(f"{url}?regex=invalid_regex\\", format="text/plain", **make_user_auth_headers(user, token))
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pattern,payload,expected_status",
    [
        (r"message.*hello", {"message": "hello"}, 200),
        (r"(a+)+$", {"message": "a" * 10000 + "!"}, 400),
        ("a" * 4097, {"message": "hello"}, 400),
        ("(" * 1000 + "a" + ")" * 1000, {"message": "hello"}, 400),
        ("hello", {"message": "x" * 1_000_001}, 400),
    ],
)
def test_regex_debugger_bounds_work(
    make_organization_and_user_with_plugin_token,
    make_user_auth_headers,
    make_alert_receive_channel,
    make_alert_group,
    make_alert,
    pattern,
    payload,
    expected_status,
):
    organization, user, token = make_organization_and_user_with_plugin_token()
    channel = make_alert_receive_channel(organization, team=user.current_team)
    group = make_alert_group(channel)
    make_alert(group, raw_request_data=payload)
    response = APIClient().get(
        reverse("api-internal:route_regex_debugger"),
        {"regex": pattern},
        **make_user_auth_headers(user, token),
    )
    assert response.status_code == expected_status
    if expected_status == 200:
        assert len(response.data) == 1
    else:
        assert "regex" in response.data


@pytest.mark.django_db
def test_regex_debugger_shares_timeout_across_alerts(
    make_organization_and_user_with_plugin_token,
    make_user_auth_headers,
    make_alert_receive_channel,
    make_alert_group,
    make_alert,
    monkeypatch,
):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from apps.api.views import route_regex_debugger

    organization, user, token = make_organization_and_user_with_plugin_token()
    channel = make_alert_receive_channel(organization, team=user.current_team)
    for _ in range(2):
        make_alert(make_alert_group(channel), raw_request_data={"message": "hello"})
    pattern = Mock()
    pattern.search.side_effect = [None, TimeoutError]
    monkeypatch.setattr(route_regex_debugger.bounded_regex, "compile", Mock(return_value=pattern))
    clock = iter([1.0, 1.15, 2.0])
    monkeypatch.setattr(route_regex_debugger, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    response = APIClient().get(
        reverse("api-internal:route_regex_debugger"),
        {"regex": "hello"},
        **make_user_auth_headers(user, token),
    )
    assert response.status_code == 400
    assert response.data == {"regex": ["Regex evaluation exceeded time limit."]}
    assert pattern.search.call_args_list[0].kwargs["timeout"] == pytest.approx(0.2)
    assert pattern.search.call_args_list[1].kwargs["timeout"] == pytest.approx(0.05)
