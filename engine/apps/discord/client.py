import json
import typing
from dataclasses import dataclass
from typing import Any, Optional, Union

import requests
from django.conf import settings
from requests.auth import AuthBase
from requests.models import PreparedRequest

from apps.discord.exceptions import DiscordAPIException, DiscordAPITokenInvalid

DISCORD_API_URL = "https://discord.com/api/v10"

# https://discord.com/developers/docs/resources/channel#channel-object-channel-types
FORUM_CHANNEL = 15
# A forum post's name, which Discord fixes at creation.
THREAD_NAME_LIMIT = 100

# Discord truncates a longer nonce rather than rejecting it, which would silently break deduplication.
NONCE_LIMIT = 25


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
    channel_type: int = 0
    # A forum's tags, as {name: id}. Applying one is how a post shows its state in the channel list.
    available_tags: typing.Optional[dict] = None

    @property
    def is_forum(self) -> bool:
        return self.channel_type == FORUM_CHANNEL


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

    def _request(self, method: str, url: str, data: Union[dict, list, None] = None) -> Any:
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
        return response.json() if response.content else None

    def get_channel(self, channel_id: str) -> DiscordChannel:
        data = self._request("GET", f"{self.base_url}/channels/{channel_id}")
        return DiscordChannel(
            channel_id=data["id"],
            guild_id=data.get("guild_id", ""),
            channel_name=data.get("name", ""),
            channel_type=data.get("type", 0),
            available_tags={tag["name"]: tag["id"] for tag in data.get("available_tags") or []},
        )

    def get_application_id(self) -> str:
        return self._request("GET", f"{self.base_url}/applications/@me")["id"]

    def overwrite_commands(self, application_id: str, commands: list) -> list:
        return self._request("PUT", f"{self.base_url}/applications/{application_id}/commands", data=commands)

    def create_message(self, channel_id: str, data: dict, nonce: Optional[str] = None) -> DiscordMessage:
        """Post a message, optionally letting Discord deduplicate it.

        Posting and recording where it landed cannot be made one atomic step, so a task that posts successfully and
        then dies before it writes the row is retried with everything already done except the row. `enforce_nonce`
        makes Discord answer that retry with the message it already has rather than a second one.

        https://discord.com/developers/docs/resources/message#create-message
        """
        if nonce:
            data = data | {"nonce": nonce[:NONCE_LIMIT], "enforce_nonce": True}
        response = self._request("POST", f"{self.base_url}/channels/{channel_id}/messages", data=data)
        return DiscordMessage(message_id=response["id"], channel_id=response["channel_id"])

    def create_thread(
        self, channel_id: str, name: str, data: dict, applied_tags: typing.Optional[list] = None
    ) -> DiscordMessage:
        """Open a forum post carrying `data` as its first message.

        A thread and its first message share an id, so the post can be edited later with `update_message` passing
        that id as both the channel and the message.
        """
        payload: dict = {"name": name[:THREAD_NAME_LIMIT], "message": data}
        if applied_tags:
            payload["applied_tags"] = applied_tags
        response = self._request("POST", f"{self.base_url}/channels/{channel_id}/threads", data=payload)
        return DiscordMessage(message_id=response["id"], channel_id=response["id"])

    def get_message(self, channel_id: str, message_id: str) -> dict:
        return self._request("GET", f"{self.base_url}/channels/{channel_id}/messages/{message_id}")

    def find_thread_for(self, guild_id: str, channel_id: str, name: str, marker: str) -> typing.Optional[str]:
        """A forum post this application already opened for `marker`, active or archived.

        Thread creation takes no nonce, so unlike an ordinary message Discord cannot make it idempotent. This is how
        a task that posted and then died before recording the placement finds its own post again instead of opening
        a second one.

        The name only narrows the search and the card's own buttons decide, because a name is not an identity: two
        organizations may register the same forum, and Discord fixes a post's name at creation while an alert's
        title can be edited to match another's afterwards. A button's custom_id carries the alert group it acts on,
        which is exactly the question being asked.
        """
        wanted = name[:THREAD_NAME_LIMIT]
        for path in (
            f"{self.base_url}/guilds/{guild_id}/threads/active",
            f"{self.base_url}/channels/{channel_id}/threads/archived/public",
        ):
            for thread in self._request("GET", path).get("threads") or []:
                if thread.get("parent_id") != channel_id or thread.get("name") != wanted:
                    continue
                # A thread and its first message share an id, so this reads the card that opened the post.
                if _acts_on(self.get_message(thread["id"], thread["id"]), marker):
                    return thread["id"]
        return None

    def update_thread(self, thread_id: str, applied_tags: typing.Optional[list] = None, archived: bool = False) -> None:
        """Set a post's tags, and take it out of the archive so its card can still be edited.

        Discord archives a quiet post on its own, and an archived post will not accept an edit, so every update
        unarchives first. Nothing archives a post deliberately — leaving that to Discord is what keeps the active
        list honest about what is still open.
        """
        data: dict = {"archived": archived}
        if applied_tags is not None:
            data["applied_tags"] = applied_tags
        self._request("PATCH", f"{self.base_url}/channels/{thread_id}", data=data)

    def update_message(self, channel_id: str, message_id: str, data: dict) -> DiscordMessage:
        response = self._request("PATCH", f"{self.base_url}/channels/{channel_id}/messages/{message_id}", data=data)
        return DiscordMessage(message_id=response["id"], channel_id=response["channel_id"])

    def delete_message(self, channel_id: str, message_id: str) -> None:
        self._request("DELETE", f"{self.base_url}/channels/{channel_id}/messages/{message_id}")


def _acts_on(message: dict, marker: str) -> bool:
    """Whether a message's controls act on `marker` — the alert group a custom_id names."""
    for row in message.get("components") or []:
        for component in row.get("components") or []:
            if marker in (component.get("custom_id") or ""):
                return True
    return False


def _error_message(response: requests.models.Response) -> str:
    try:
        return response.json().get("message", response.text)
    except ValueError:
        return response.text
