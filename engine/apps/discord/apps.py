from django.apps import AppConfig


class DiscordConfig(AppConfig):
    name = "apps.discord"

    def ready(self) -> None:
        import apps.discord.signals  # noqa: F401
