"""The slash commands OnCall registers with its Discord application."""

from apps.discord.client import DiscordClient

LINK_COMMAND_NAME = "oncall-link"

# https://discord.com/developers/docs/interactions/application-commands
CHAT_INPUT, STRING_OPTION = 1, 3

COMMANDS = [
    {
        "name": LINK_COMMAND_NAME,
        "type": CHAT_INPUT,
        "description": "Link this Discord account to your Grafana OnCall user",
        "options": [
            {
                "name": "code",
                "type": STRING_OPTION,
                "description": "The verification code from your Grafana OnCall user settings",
                "required": True,
            }
        ],
    }
]


def register_commands() -> list:
    """Replace the application's global commands with `COMMANDS`.

    Registration is a deploy-time action rather than something the engine does on boot: Discord rate limits it hard,
    and the set only changes when this file does.
    """
    client = DiscordClient()
    return client.overwrite_commands(application_id=client.get_application_id(), commands=COMMANDS)
