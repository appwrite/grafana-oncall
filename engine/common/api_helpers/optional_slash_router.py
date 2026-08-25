from typing import Callable, Optional

from django.urls import URLPattern, re_path
from rest_framework import routers


class OptionalSlashRouter(routers.SimpleRouter):
    """
    A router with optional trailing slash at the end
    APIRouter().register("users", ...) will match both "users" and "users/"
    """

    def __init__(self):
        super().__init__()
        self.trailing_slash = "/?"


def optional_slash_path(route: str, view: Callable, name: Optional[str] = None) -> URLPattern:
    regex_route = "^{}/?$".format(route)
    return re_path(route=regex_route, view=view, name=name)
