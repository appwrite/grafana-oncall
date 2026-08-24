from django.db import migrations, models
import django.db.models.deletion


def backfill_guild_ids(apps, schema_editor):
    DiscordChannel = apps.get_model("discord", "DiscordChannel")
    DiscordMessage = apps.get_model("discord", "DiscordMessage")

    messages = DiscordMessage.objects.filter(guild_id__isnull=True).select_related("alert_group__channel")
    for message in messages.iterator():
        channel = DiscordChannel.objects.filter(
            organization_id=message.alert_group.channel.organization_id,
            channel_id=message.channel_id,
        ).first()
        if channel:
            DiscordMessage.objects.filter(pk=message.pk).update(guild_id=channel.guild_id)


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0077_alter_resolutionnote_source"),
        ("discord", "0002_discordchannel_available_tags_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordmessage",
            name="guild_id",
            field=models.CharField(default=None, max_length=100, null=True),
        ),
        migrations.RunPython(backfill_guild_ids, migrations.RunPython.noop),
        migrations.CreateModel(
            name="DiscordResolutionNoteMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_id", models.CharField(max_length=100)),
                ("channel_id", models.CharField(max_length=100)),
                ("thread_id", models.CharField(default=None, max_length=100, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "resolution_note",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discord_message",
                        to="alerts.resolutionnote",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["channel_id", "message_id"], name="discord_dis_channel_51254e_idx")],
            },
        ),
    ]
