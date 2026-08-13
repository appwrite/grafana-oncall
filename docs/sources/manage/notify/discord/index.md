---
title: Discord
menuTitle: Discord
description: How to connect Discord for alert group notifications.
weight: 900
keywords:
  - OnCall
  - Notifications
  - ChatOps
  - Discord
---

# Discord integration for Grafana OnCall

The Discord integration posts every alert group to a Discord channel as an embed with Acknowledge and Resolve
buttons, and keeps that message up to date as the alert group changes state — whether the change came from Discord,
the OnCall UI, Slack or the API.

At the moment, this integration is only available for OSS installations.

## Before you begin

Create a Discord application at <https://discord.com/developers/applications>, add a bot to it, and invite the bot to
your server with the `bot` scope and the **Send Messages** and **Embed Links** permissions.

Set the following environment variables on the engine and the celery workers:

| Variable | Value |
| --- | --- |
| `FEATURE_DISCORD_INTEGRATION_ENABLED` | `True` |
| `DISCORD_BOT_TOKEN` | the bot token from the application's **Bot** page |
| `DISCORD_PUBLIC_KEY` | the **Public Key** from the application's **General Information** page |

Add `discord` to `CELERY_WORKER_QUEUE` so the alert group messages are actually posted.

## Receive button presses

Discord delivers button presses over HTTP rather than a gateway connection. On the application's **General
Information** page, set the **Interactions Endpoint URL** to:

```
https://<your-oncall-engine>/api/internal/v1/discord/interaction/
```

Discord verifies the endpoint by sending a signed ping, which OnCall answers using `DISCORD_PUBLIC_KEY`. Requests
that are not signed by your application are rejected with a 401.

## Connect a Discord channel

Turn on Developer Mode in Discord (**Settings → Advanced**), right-click the channel you want alerts in and choose
**Copy Channel ID**, then register it:

```bash
curl -X POST https://<your-oncall-engine>/api/internal/v1/discord/channels/ \
  -H "Authorization: <grafana-token>" \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "<channel id>"}'
```

`POST /api/internal/v1/discord/channels/<id>/set_default/` marks a channel as the default one alert groups are
posted to. A route can override it by setting `notification_backends.DISCORD.channel` to a channel's id.

## Acknowledge from Discord

A button press acts as the OnCall user linked to the pressing Discord account. Until an account is linked, OnCall
replies to the presser — and only to them — that their Discord account is not linked to a Grafana OnCall user.
