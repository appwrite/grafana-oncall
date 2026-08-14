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
the OnCall UI, Slack or the API. Once a user links their Discord account, Discord is also selectable as a step in
escalation chains and personal notification policies.

At the moment, this integration is only available for OSS installations.

![An alert group posted to Discord, with Acknowledge, Resolve and OnCall buttons](img/alert-firing.png)

Acknowledging or resolving — from Discord or anywhere else — edits the same message in place:

![The same alert group after being acknowledged, showing who acknowledged it](img/alert-acknowledged.png)

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

```text
https://<your-oncall-engine>/api/internal/v1/discord/interaction/
```

Discord verifies the endpoint by sending a signed ping, which OnCall answers using `DISCORD_PUBLIC_KEY`. Requests
that are not signed by your application are rejected with a 401.

## Connect a Discord channel

Turn on Developer Mode in Discord (**Settings → Advanced**), right-click the channel you want alerts in and choose
**Copy Channel ID**. Then, in Grafana OnCall, go to **Settings → ChatOps → Discord**, click **Add Discord channel**
and paste it in.

**Make default** marks the channel alert groups are posted to. A route can override it: on an integration's route,
switch on **Post to Discord channel** and pick another one.

## Split alerts from warnings

A route also chooses how loud its alert groups read. Set it to **⚠️ Warning** and a still-open group from that route
is amber rather than red:

![A warning alert group, amber rather than red](img/alert-warning.png)

Severity lives on the route rather than in the payload, because which label means "wake somebody up" differs per
deployment — `severity=critical`, `incident=true`, a label of your own — and the route already decides where an
alert goes and who it pages. So a route matching `{{ payload.commonLabels.severity == "warning" }}` can post to
`#alerts-low`, read as a warning and skip escalation entirely, while everything else keeps the default channel and
an escalation chain.

Acknowledging outranks severity: once somebody owns the group, the card turns 🟡 whichever route it came in on.

## Register the slash command

Linking a Discord account to an OnCall user is done with a slash command, which has to be registered with the
application once per deployment (and again whenever it changes):

```bash
python manage.py register_discord_commands
```

## Link a Discord account

A button press acts as the OnCall user linked to the pressing Discord account, and a Discord notification step
mentions that account. To link one:

1. In OnCall, open your user profile and go to the **Discord Connection** tab. It shows a verification code, valid
   for ten minutes.
2. In Discord, run `/oncall-link` and paste the code as the `code` option. The reply is only visible to you.
3. Refresh the page. The **Discord** row of your profile now shows the linked account, with a button to unlink it.

Until an account is linked, a button press gets an ephemeral reply saying so, and a Discord notification step is
recorded as failed with "has not linked a Discord account".

## Shift announcements

Every ten minutes OnCall checks each schedule for shifts that have just started and announces them in the default
Discord channel, mentioning whoever is going on call:

![A shift announcement mentioning the users going on call](img/shift-announcement.png)

Someone on call without a linked Discord account is named in plain text rather than left out. Only shift starts are
announced: in a follow-the-sun rota every shift ending coincides with another starting, so "ended" messages would be
daily noise. Overrides and swaps announce too, because the announcement reads the schedule's final events rather
than its rotations.
