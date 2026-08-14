from django.db import models


class DiscordUser(models.Model):
    user = models.OneToOneField("user_management.User", on_delete=models.CASCADE, related_name="discord_user_identity")
    discord_user_id = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["discord_user_id"]),
        ]

    @property
    def mention_username(self) -> str:
        return f"<@{self.discord_user_id}>"
