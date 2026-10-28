import sys
from unittest import mock

from apps.social_auth.backends import SLACK_INSTALLATION_BACKEND
from apps.social_auth.pipeline.mattermost import connect_user_to_mattermost


def test_connect_user_to_mattermost_skips_other_backends_without_mattermost_app():
    # A None entry in sys.modules makes the import fail, as it does when apps.mattermost
    # is not in INSTALLED_APPS (FEATURE_MATTERMOST_INTEGRATION_ENABLED=False)
    backend = mock.Mock()
    backend.name = SLACK_INSTALLATION_BACKEND
    with mock.patch.dict(sys.modules, {"apps.mattermost.models": None}):
        assert connect_user_to_mattermost({}, backend, mock.Mock(), mock.Mock(), mock.Mock()) is None
