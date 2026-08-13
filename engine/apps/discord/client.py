import json
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from requests.auth import AuthBase
from requests.models import PreparedRequest

from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid

DISCORD_API_URL = "https://discord.com/api/v10"


class BotAuth(AuthBase):
    def __init__(self, token: str) -> None:
        self.token = token

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Authorization"] = f"Bot {self.token}"
        return request


@dataclass
class DiscordChannel:
    channel_id: str
    guild_id: str
    channel_name: str


@dataclass
class DiscordMessage:
    message_id: str
    channel_id: str


class DiscordClient:
    """
    Discord's REST API.

    Discord rate limits per route and answers 429 with a `retry_after` in seconds. Nothing here sleeps on it: the
    caller is a celery task with retry backoff, and a 429 is just another API error to retry.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or settings.DISCORD_BOT_TOKEN
        self.base_url = DISCORD_API_URL
        self.timeout: int = 10

        if not self.token:
            raise DiscordAPITokenInvalid

    def _request(self, method: str, url: str, data: Optional[dict] = None) -> dict:
        try:
            response = requests.request(
                method=method,
                url=url,
                data=json.dumps(data) if data is not None else None,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
                auth=BotAuth(self.token),
            )
            response.raise_for_status()
        except requests.HTTPError as ex:
            raise DiscordAPIException(
                status=ex.response.status_code,
                url=url,
                msg=_error_message(ex.response),
                method=method,
            )
        except requests.RequestException as ex:
            raise DiscordAPIException(status=None, url=url, msg=str(ex), method=method)
        return response.json()

    def get_channel(self, channel_id: str) -> DiscordChannel:
        data = self._request("GET", f"{self.base_url}/channels/{channel_id}")
        return DiscordChannel(
            channel_id=data["id"],
            guild_id=data.get("guild_id", ""),
            channel_name=data.get("name", ""),
        )

    def create_message(self, channel_id: str, data: dict) -> DiscordMessage:
        response = self._request("POST", f"{self.base_url}/channels/{channel_id}/messages", data=data)
        return DiscordMessage(message_id=response["id"], channel_id=response["channel_id"])

    def update_message(self, channel_id: str, message_id: str, data: dict) -> DiscordMessage:
        response = self._request("PATCH", f"{self.base_url}/channels/{channel_id}/messages/{message_id}", data=data)
        return DiscordMessage(message_id=response["id"], channel_id=response["channel_id"])


def _error_message(response: requests.models.Response) -> str:
    try:
        return response.json().get("message", response.text)
    except ValueError:
        return response.text
