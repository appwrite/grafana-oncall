# Appwrite's fork of Grafana OnCall

Grafana archived [OnCall OSS](https://github.com/grafana/oncall) on 2026-03-24 at v1.16.11.
[Appwrite](https://appwrite.io) maintains this fork for its own use.

## What's different from upstream

New features:

- A [Discord integration](docs/sources/manage/notify/discord/index.md). Alert groups are posted as
  cards with working buttons, forum channels get a post per alert group, routes choose a channel and
  a severity, and escalation can mention a Discord role. Users link their account with
  `/oncall-link`.
- SMS through [MSG91](https://msg91.com), as a phone provider alongside Twilio, Zvonok and Exotel.

Kept working:

- Runs on Grafana 13 and React 19. Upstream's plugin crashes on mount there.
- Runs on Django 5.2 LTS. Upstream is on 4.2, whose extended support has ended.
- The Insights page renders again. Its alert group variable produced invalid PromQL on Grafana 13.
- Dependencies are patched, and end-to-end tests run against Grafana 12 and 13.

Published:

- Multi-arch engine images at
  [`ghcr.io/appwrite/grafana-oncall`](https://github.com/appwrite/grafana-oncall/pkgs/container/grafana-oncall).
- A plugin archive and its checksum on every
  [release](https://github.com/appwrite/grafana-oncall/releases), so a deployment can pin the
  frontend by version.

## What it does not offer

- No support and no roadmap. We keep it working for our own use.
- The plugin is unsigned, so Grafana needs
  `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=grafana-oncall-app`.
- The Helm chart is not published to a chart repository. Install it from a checkout.
- The mobile app does not work. It relied on Grafana Cloud's push relay.

## Grafana OnCall

<img width="400px" src="docs/img/logo.png">

[![Latest Release](https://img.shields.io/github/v/tag/appwrite/grafana-oncall?display_name=tag&sort=semver)](https://github.com/appwrite/grafana-oncall/tags)
[![License](https://img.shields.io/github/license/appwrite/grafana-oncall)](https://github.com/appwrite/grafana-oncall/blob/main/LICENSE)

Developer-friendly incident response with brilliant Slack integration.

<!-- markdownlint-disable MD013 MD033 -->
<table>
  <tbody>
    <tr>
    <td width="75%"><img src="docs/img/screenshot.png"></td>
      <td><div align="center"><a href="https://grafana.com/docs/oncall/latest/mobile-app/">Android & iOS</a>:<br><img src="docs/img/screenshot_mobile.png"></div></td>
    </tr>
  </tbody>
</table>
<!-- markdownlint-enable MD013 MD033 -->

- Collect and analyze alerts from multiple monitoring systems
- On-call rotations based on schedules
- Automatic escalations
- Phone calls, SMS, Slack, Telegram notifications

## Getting Started

> [!IMPORTANT]  
> These instructions are for using Grafana 11 or newer. You must enable the feature toggle for
> `externalServiceAccounts`. This is already done for the docker files and helm charts.  If you are running Grafana
> separately see the Grafana documentation on how to enable this.

We prepared multiple environments:

- [production](https://grafana.com/docs/oncall/latest/open-source/#production-environment)
- [developer](./dev/README.md)
- hobby (described in the following steps)

1. Download [`docker-compose.yml`](docker-compose.yml):

   ```bash
   curl -fsSL https://raw.githubusercontent.com/appwrite/grafana-oncall/main/docker-compose.yml -o docker-compose.yml
   ```

2. Set variables:

   ```bash
   echo "DOMAIN=http://localhost:8080
   # Remove 'with_grafana' below if you want to use existing grafana
   # Add 'with_prometheus' below to optionally enable a local prometheus for oncall metrics
   # e.g. COMPOSE_PROFILES=with_grafana,with_prometheus
   COMPOSE_PROFILES=with_grafana
   # to setup an auth token for prometheus exporter metrics:
   # PROMETHEUS_EXPORTER_SECRET=my_random_prometheus_secret
   # also, make sure to enable the /metrics endpoint:
   # FEATURE_PROMETHEUS_EXPORTER_ENABLED=True
   SECRET_KEY=my_random_secret_must_be_more_than_32_characters_long" > .env
   ```

3. (Optional) If you want to enable/setup the prometheus metrics exporter
(besides the changes above), create a `prometheus.yml` file (replacing
`my_random_prometheus_secret` accordingly), next to your `docker-compose.yml`:

   ```bash
   echo "global:
     scrape_interval:     15s
     evaluation_interval: 15s

   scrape_configs:
     - job_name: prometheus
       metrics_path: /metrics/
       authorization:
         credentials: my_random_prometheus_secret
       static_configs:
         - targets: [\"host.docker.internal:8080\"]" > prometheus.yml
   ```

   NOTE: you will need to setup a Prometheus datasource using `http://prometheus:9090`
   as the URL in the Grafana UI.

4. Launch services:

   ```bash
   docker-compose pull && docker-compose up -d
   ```

5. Provision the plugin (If you run Grafana outside the included docker files install the plugin before these steps):

   If you are using the included docker compose file use `admin`/`admin` credentials and `localhost:3000` to
   perform this task.  If you have configured Grafana differently adjust your credentials and hostnames accordingly.

   ```bash
   # Note: onCallApiUrl 'engine' and grafanaUrl 'grafana' use the name from the docker compose file.  If you are 
   # running your grafana or oncall engine instance with another hostname adjust accordingly. 
   curl -X POST 'http://admin:admin@localhost:3000/api/plugins/grafana-oncall-app/settings' -H "Content-Type: application/json" -d '{"enabled":true, "jsonData":{"stackId":5, "orgId":100, "onCallApiUrl":"http://engine:8080", "grafanaUrl":"http://grafana:3000"}}'
   curl -X POST 'http://admin:admin@localhost:3000/api/plugins/grafana-oncall-app/resources/plugin/install'
   ```

6. Start using OnCall, log in to Grafana with credentials
   as defined above: `admin`/`admin`

7. Enjoy! Check our [OSS docs](https://grafana.com/docs/oncall/latest/open-source/) if you want to set up
   Slack, Telegram, Twilio or SMS/calls through Grafana Cloud.

## Troubleshooting

Here are some API calls that can be made to help if you are having difficulty connecting Grafana and OnCall.
(Modify parameters to match your credentials and environment)

   ```bash
   # Use this to get more information about the connection between Grafana and OnCall
   curl -X GET 'http://admin:admin@localhost:3000/api/plugins/grafana-oncall-app/resources/plugin/status'
   ```

   ```bash
   # If you added a user or changed permissions and don't see it show up in OnCall you can manually trigger sync.
   # Note: This is called automatically when the app is loaded (page load/refresh) but there is a 5 min timeout so 
   # that it does not generate unnecessary activity.
   curl -X POST 'http://admin:admin@localhost:3000/api/plugins/grafana-oncall-app/resources/plugin/sync'
   ```

## Update version

The engine and plugin are released together and are not meant to be mixed across versions, so one
variable moves both. Set it to the [release](https://github.com/appwrite/grafana-oncall/releases) you
want in `.env`:

```shell
echo "ONCALL_VERSION=1.19.1" >> .env

docker-compose pull
docker-compose up -d
```

The plugin is not in the grafana.com catalog, so it does not update through the plugin page. Grafana
only installs a plugin that is not already present, so to move the plugin you also have to clear the
old copy from its volume:

```shell
docker-compose exec grafana rm -rf /var/lib/grafana/plugins/grafana-oncall-app
docker-compose restart grafana
```

## Join community

[<img width="200px" src="docs/img/slack.png">](https://slack.grafana.com/)
[<img width="200px" src="docs/img/GH_discussions.png">](https://community.grafana.com/)

Have a question, comment or feedback? Don't be afraid to [open an issue](https://github.com/appwrite/grafana-oncall/issues/new/choose)!

## Further Reading

- _Automated migration from other on-call tools_ - [Migrator](https://github.com/appwrite/grafana-oncall/tree/main/tools/migrators)
- _Documentation_ - [Grafana OnCall](https://grafana.com/docs/oncall/latest/)
- _Overview Webinar_ - [YouTube](https://www.youtube.com/watch?v=7uSe1pulgs8)
- _How To Add Integration_ - [How to Add Integration](https://github.com/appwrite/grafana-oncall/tree/main/engine/config_integrations/README.md)
- _Blog Post_ - [Announcing Grafana OnCall, the easiest way to do on-call management](https://grafana.com/blog/2021/11/09/announcing-grafana-oncall/)
- _Presentation_ - [Deep dive into the Grafana, Prometheus, and Alertmanager stack for alerting and on-call management](https://grafana.com/go/observabilitycon/2021/alerting/?pg=blog)
