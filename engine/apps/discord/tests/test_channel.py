import pytest

from apps.discord.models import DiscordChannel


@pytest.fixture()
def make_alert_group_for_route(make_alert_receive_channel, make_channel_filter, make_alert_group):
    def _make_alert_group_for_route(organization, notification_backends):
        alert_receive_channel = make_alert_receive_channel(organization)
        channel_filter = make_channel_filter(alert_receive_channel, notification_backends=notification_backends)
        return make_alert_group(alert_receive_channel, channel_filter=channel_filter)

    return _make_alert_group_for_route


@pytest.mark.django_db
def test_route_channel_wins_over_the_default(make_organization, make_discord_channel, make_alert_group_for_route):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    channel = make_discord_channel(organization=organization)
    alert_group = make_alert_group_for_route(
        organization, {"DISCORD": {"channel": channel.public_primary_key, "enabled": True}}
    )

    assert DiscordChannel.get_channel_for_alert_group(alert_group) == channel


@pytest.mark.django_db
def test_route_without_discord_falls_back_to_the_default(
    make_organization, make_discord_channel, make_alert_group_for_route
):
    organization = make_organization()
    default_channel = make_discord_channel(organization=organization, is_default_channel=True)
    alert_group = make_alert_group_for_route(organization, None)

    assert DiscordChannel.get_channel_for_alert_group(alert_group) == default_channel


@pytest.mark.django_db
def test_route_with_discord_disabled_posts_nowhere(make_organization, make_discord_channel, make_alert_group_for_route):
    organization = make_organization()
    make_discord_channel(organization=organization, is_default_channel=True)
    channel = make_discord_channel(organization=organization)
    alert_group = make_alert_group_for_route(
        organization, {"DISCORD": {"channel": channel.public_primary_key, "enabled": False}}
    )

    assert DiscordChannel.get_channel_for_alert_group(alert_group) is None


@pytest.mark.django_db
def test_make_channel_default_moves_the_flag(make_organization, make_discord_channel, make_user_for_organization):
    organization = make_organization()
    user = make_user_for_organization(organization)
    old_default = make_discord_channel(organization=organization, is_default_channel=True)
    channel = make_discord_channel(organization=organization)

    channel.make_channel_default(user)

    old_default.refresh_from_db()
    channel.refresh_from_db()
    assert not old_default.is_default_channel
    assert channel.is_default_channel
