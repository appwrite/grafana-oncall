import factory

from apps.discord.models import DiscordChannel, DiscordMessage, DiscordUser


def snowflake(offset):
    """Discord ids are 64 bit snowflakes rendered as strings."""
    return factory.Sequence(lambda n: str(10**17 + offset * 10**9 + n))


class DiscordChannelFactory(factory.DjangoModelFactory):
    guild_id = snowflake(1)
    channel_id = snowflake(2)
    channel_name = factory.Faker("word")

    class Meta:
        model = DiscordChannel


class DiscordMessageFactory(factory.DjangoModelFactory):
    message_id = snowflake(3)
    channel_id = snowflake(4)

    class Meta:
        model = DiscordMessage


class DiscordUserFactory(factory.DjangoModelFactory):
    discord_user_id = snowflake(5)
    username = factory.Faker("word")

    class Meta:
        model = DiscordUser
