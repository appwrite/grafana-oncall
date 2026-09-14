import json
import re
import time

import regex as bounded_regex
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.incident_appearance.renderers.web_renderer import AlertWebRenderer
from apps.alerts.models import Alert, AlertGroup
from apps.auth_token.auth import PluginAuthentication
from common.api_helpers.exceptions import BadRequest

MAX_REGEX_LENGTH = 4096
MAX_PAYLOAD_LENGTH = 1_000_000
REGEX_TIME_BUDGET = 0.2


class RouteRegexDebuggerView(APIView):
    authentication_classes = (PluginAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        organization = self.request.auth.organization
        team = self.request.user.current_team

        regex = request.query_params.get("regex", None)

        if regex is None:
            raise BadRequest(detail={"regex": ["This field is required."]})
        if regex == "":
            return Response([])
        if len(regex) > MAX_REGEX_LENGTH:
            raise BadRequest(detail={"regex": ["Regex exceeds length limit."]})
        try:
            re.compile(regex)
            pattern = bounded_regex.compile(regex, bounded_regex.VERSION0)
        except (re.error, bounded_regex.error, OverflowError, RecursionError) as e:
            raise BadRequest(detail={"regex": ["Invalid regex."]}) from e

        remaining_time = REGEX_TIME_BUDGET
        incidents_matching_regex = []
        MAX_INCIDENTS_TO_SHOW = 5
        INCIDENTS_TO_LOOKUP = 100
        for ag in (
            AlertGroup.objects.prefetch_related(Prefetch("alerts", queryset=Alert.objects.order_by("pk")))
            .filter(channel__organization=organization, channel__team=team)
            .order_by("-started_at")[:INCIDENTS_TO_LOOKUP]
        ):
            if len(incidents_matching_regex) < MAX_INCIDENTS_TO_SHOW:
                first_alert = ag.alerts.all()[0]
                payload = json.dumps(first_alert.raw_request_data)
                if len(payload) > MAX_PAYLOAD_LENGTH:
                    raise BadRequest(detail={"regex": ["Alert payload exceeds regex debugger length limit."]})
                started = time.monotonic()
                try:
                    if remaining_time <= 0:
                        raise TimeoutError
                    match = pattern.search(payload, timeout=remaining_time)
                except TimeoutError as e:
                    raise BadRequest(detail={"regex": ["Regex evaluation exceeded time limit."]}) from e
                remaining_time -= time.monotonic() - started
                if match:
                    title = AlertWebRenderer(first_alert).render()["title"]
                    incidents_matching_regex.append(
                        {
                            "title": title,
                            "pk": ag.public_primary_key,
                            "payload": first_alert.raw_request_data,
                            "inside_organization_number": ag.inside_organization_number,
                        }
                    )

        return Response(incidents_matching_regex)
