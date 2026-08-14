from django.urls import include, path

from common.api_helpers.optional_slash_router import OptionalSlashRouter, optional_slash_path

from .views import DiscordChannelViewSet, DiscordInteractionView

app_name = "discord"
router = OptionalSlashRouter()
router.register(r"channels", DiscordChannelViewSet, basename="channel")

urlpatterns = [
    path("", include(router.urls)),
    optional_slash_path("interaction", DiscordInteractionView.as_view(), name="incoming_discord_interaction"),
]
