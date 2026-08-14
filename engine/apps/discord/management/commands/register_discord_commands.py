from django.core.management.base import BaseCommand

from apps.discord.commands import register_commands


class Command(BaseCommand):
    help = "Register OnCall's slash commands with its Discord application"

    def handle(self, *args, **options):
        for command in register_commands():
            self.stdout.write(f"registered /{command['name']}")
