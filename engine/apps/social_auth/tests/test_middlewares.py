from types import SimpleNamespace
from unittest import mock

import pytest
from social_core.exceptions import AuthCanceled, AuthCredentialError

from apps.social_auth.backends import InstallSlackOAuth2V2, LoginSlackOAuth2V2
from apps.social_auth.middlewares import SocialAuthAuthCanceledExceptionMiddleware


@pytest.mark.parametrize("backend_type,page", [(InstallSlackOAuth2V2, "chat-ops"), (LoginSlackOAuth2V2, "users/me")])
@pytest.mark.parametrize("exception_type,query", [(AuthCanceled, ""), (AuthCredentialError, "?slack_error=auth_failed")])
def test_authentication_errors_redirect_to_the_originating_page(backend_type, page, exception_type, query):
    organization = SimpleNamespace(grafana_url="https://grafana.example/", is_grafana_irm_enabled=False)
    request = SimpleNamespace(user=SimpleNamespace(organization=organization), social_strategy=mock.Mock())
    middleware = SocialAuthAuthCanceledExceptionMiddleware(lambda request: None)
    exception = exception_type(mock.Mock(spec=backend_type))

    with mock.patch.object(middleware, "raise_exception", return_value=False):
        response = middleware.process_exception(request, exception)

    assert response.status_code == 302
    assert response.url == f"https://grafana.example/a/grafana-oncall-app/{page}{query}"
