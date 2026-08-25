# Main
enabled = True
title = "Grafana Alerting"
slug = "grafana_alerting"
short_description = (
    "Your current Grafana Cloud stack. Automatically create an alerting contact point and a route in Grafana"
)
description = None
is_displayed_on_web = True
is_featured = True
featured_tag_name = "Quick Connect"
is_able_to_autoresolve = True
is_demo_alert_enabled = True
based_on_alertmanager = True


# Behaviour
source_link = "{{ payload.alerts[0].generatorURL }}"

grouping_id = "{{ payload.groupKey }}"

resolve_condition = """{{ payload.status == "resolved" }}"""

acknowledge_condition = None

# Web
web_title = """\
{% set groupLabels = payload.get("groupLabels", {}).copy() -%}
{% if "labels" in payload -%}
{# backward compatibility with legacy alertmanager integration -#}
{% set alertname = payload.get("labels", {}).get("alertname", "") -%} 
{% else -%}
{% set alertname = groupLabels.pop("alertname", "")  -%}
{% endif -%}

{{ alertname }} {% if groupLabels | length > 0 %}({{ groupLabels.values()|join(", ") }}){% endif %}
"""  # noqa

web_message = """\
{% set annotations = payload.get("commonAnnotations", {}).copy() -%}
{% set groupLabels = payload.get("groupLabels", {}) -%}
{% set commonLabels = payload.get("commonLabels", {}) -%}
{% set severity = groupLabels.severity -%}
{% set legacyLabels = payload.get("labels", {}) -%}
{% set legacyAnnotations = payload.get("annotations", {}) -%}

{% if severity -%}
{% set severity_emoji = {"critical": ":rotating_light:", "warning": ":warning:" }[severity] | default(":question:") -%}
Severity: {{ severity }} {{ severity_emoji }}
{% endif -%}

{% set status = payload.get("status", "Unknown") -%}
{% set status_emoji = {"firing": ":fire:", "resolved": ":white_check_mark:"}[status] | default(":warning:") -%}
Status: {{ status }} {{ status_emoji }} (on the source)
{% if status == "firing" and payload.numFiring -%}
Firing alerts – {{ payload.numFiring }}
Resolved alerts – {{ payload.numResolved }}
{% endif -%}

{% if "runbook_url" in annotations -%}
[:book: Runbook:link:]({{ annotations.runbook_url }})
{% set _ = annotations.pop('runbook_url') -%}
{% endif -%}

{% if "runbook_url_internal" in annotations -%}
[:closed_book: Runbook (internal):link:]({{ annotations.runbook_url_internal }})
{% set _ = annotations.pop('runbook_url_internal') -%}
{% endif %}

{%- if groupLabels | length > 0 %}
GroupLabels:
{% for k, v in groupLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if commonLabels | length > 0 -%}
CommonLabels:
{% for k, v in commonLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if annotations | length > 0 -%}
Annotations:
{% for k, v in annotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{# backward compatibility with legacy alertmanager integration -#}
{% if legacyLabels | length > 0 -%}
Labels:
{% for k, v in legacyLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if legacyAnnotations | length > 0 -%}
Annotations:
{% for k, v in legacyAnnotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}
[View in AlertManager]({{ source_link }})
"""


# Slack
slack_title = """\
*<{{ grafana_oncall_link }}|#{{ grafana_oncall_incident_id }} {{ web_title }}>* via {{ integration_name }}
{% if source_link and (source_link[:8] == "https://" or source_link[:7] == "http://") %}
 (*<{{ source_link }}|source>*)
{%- endif %}
"""

# default slack message template is identical to web message template, except urls
# It can be based on web message template (see example), but it can affect existing templates
# slack_message = """
# {% set mkdwn_link_regex = "\[([\w\s\d:]+)\]\((https?:\/\/[\w\d./?=#]+)\)" %}
# {{ web_message
#   | regex_replace(mkdwn_link_regex, "<\\2|\\1>")
# }}
# """

slack_message = """\
{% set annotations = payload.get("commonAnnotations", {}).copy() -%}
{% set groupLabels = payload.get("groupLabels", {}) -%}
{% set commonLabels = payload.get("commonLabels", {}) -%}
{% set severity = groupLabels.severity -%}
{% set legacyLabels = payload.get("labels", {}) -%}
{% set legacyAnnotations = payload.get("annotations", {}) -%}

{% if severity -%}
{% set severity_emoji = {"critical": ":rotating_light:", "warning": ":warning:" }[severity] | default(":question:") -%}
Severity: {{ severity }} {{ severity_emoji }}
{% endif -%}

{% set status = payload.get("status", "Unknown") -%}
{% set status_emoji = {"firing": ":fire:", "resolved": ":white_check_mark:"}[status] | default(":warning:") -%}
Status: {{ status }} {{ status_emoji }} (on the source)
{% if status == "firing" and payload.numFiring -%}
Firing alerts – {{ payload.numFiring }}
Resolved alerts – {{ payload.numResolved }}
{% endif -%}

{% if "runbook_url" in annotations -%}
<{{ annotations.runbook_url }}|:book: Runbook:link:>
{% set _ = annotations.pop('runbook_url') -%}
{% endif -%}

{% if "runbook_url_internal" in annotations -%}
<{{ annotations.runbook_url_internal }}|:closed_book: Runbook (internal):link:>
{% set _ = annotations.pop('runbook_url_internal') -%}
{% endif %}

{%- if groupLabels | length > 0 %}
GroupLabels:
{% for k, v in groupLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if commonLabels | length > 0 -%}
CommonLabels:
{% for k, v in commonLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if annotations | length > 0 -%}
Annotations:
{% for k, v in annotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{# backward compatibility with legacy alertmanager integration -#}
{% if legacyLabels | length > 0 -%}
Labels:
{% for k, v in legacyLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if legacyAnnotations | length > 0 -%}
Annotations:
{% for k, v in legacyAnnotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}
"""
# noqa: W291


slack_image_url = None

web_image_url = None

# Discord
#
# A card is read in a chat channel rather than opened as a page, so it keeps every label and annotation the alert
# carries — the sender chose them — and drops the three headings and the bullets that made a page of them. One
# entry per line: a long line of joined pairs wraps into something nobody can scan on a phone.
#
# Only what is genuinely said twice is dropped. `alertname` is the card's title and `severity` is its title emoji
# and its forum tag; `value_string` is the long form of `values`, so the compact one is kept; and a key that
# appears in both the labels and the annotations with the same value is printed once.
discord_title = web_title

discord_message = """\
{# A webhook carries one authoritative thing: `alerts`, every instance the group holds, each with its own labels
   and annotations. Everything else is a view Alertmanager derives from them — `groupLabels` is what the route
   grouped by, `commonLabels` and `commonAnnotations` are what the instances happen to agree on. The legacy
   integration sends no `alerts` and puts a single instance's labels and annotations at the top level, so it is
   read here as a group of one and nothing after this block has to know which shape arrived.

   A card says the agreed part once, and lists a summary per instance when it holds more than one, because what
   sets the instances apart is exactly what the agreed part cannot carry. -#}
{% macro pair(key, value) -%}
{% set flat = (value | string).split() | join(" ") -%}
{% if "`" in flat -%}
{{ key }}: {{ flat }}
{%- else -%}
{{ key }}: `{{ flat }}`
{%- endif -%}
{% endmacro -%}

{# alertname titles the card, and severity is its title emoji and its forum tag, so neither is a line on it.
   Grafana wraps its own identifiers in double underscores and hides them in its own UI. -#}
{% set said_elsewhere = ["alertname", "severity"] -%}
{% set instances = payload.get("alerts") or [{"labels": payload.get("labels", {}), "annotations": payload.get("annotations", {})}] -%}
{% set grouped_by = payload.get("groupLabels", {}) -%}
{% set annotations = payload.get("commonAnnotations") or payload.get("annotations", {}) -%}
{% set agreed = {} -%}
{% for source in [grouped_by, payload.get("commonLabels", {}), payload.get("labels", {})] -%}
{% for key, value in source.items()
   if key not in agreed
   and key not in said_elsewhere
   and not key.startswith("__") -%}
{% set _ = agreed.update({key: value}) -%}
{% endfor -%}
{% endfor -%}

{% set summary = annotations.get("summary") -%}
{% set description = annotations.get("description") -%}

{# What identifies an instance is the labels the group does not share; a summary is prose that usually names them
   and is not required to. So an instance says its own summary when its rule wrote one that is not already the
   summary above, and then adds whichever of its own labels that sentence does not carry. A rule that writes
   every instance the same sentence identifies none of them, and then the labels are all a line has to go on. -#}
{% set summaries = [] -%}
{% for instance in instances -%}
{% set own = instance.get("annotations", {}).get("summary") -%}
{% if own and own != summary -%}
{% set prose = (own | string).split() | join(" ") -%}
{% else -%}
{% set prose = "" -%}
{% endif -%}
{# "Carries" means says as a word of its own: matching anywhere in the sentence read `shard: 1` into "12 jobs"
   and dropped the one label telling two shards apart. -#}
{% set carried = [] -%}
{% for token in prose.split() -%}
{% set _ = carried.append(token | trim("`.,:;!?()[]{}" ~ '"' ~ "'")) -%}
{% endfor -%}
{% set apart = [] -%}
{% for key, value in instance.get("labels", {}).items()
   if key not in said_elsewhere
   and not key.startswith("__")
   and agreed.get(key) != value
   and (value | string) not in carried -%}
{% set _ = apart.append(pair(key, value) | trim) -%}
{% endfor -%}
{% if prose and apart -%}
{% set line = prose ~ " — " ~ (apart | join(", ")) -%}
{% elif prose -%}
{% set line = prose -%}
{% else -%}
{% set line = apart | join(", ") -%}
{% endif -%}
{# Two instances reduced to the same line are the same instance as far as a reader can tell. -#}
{% if line and line not in summaries -%}
{% set _ = summaries.append(line) -%}
{% endif -%}
{% endfor -%}

{# The prose above and the link buttons are not repeated as lines to copy out of. `value_string` is the long form
   of `values`, dropped only when there is a `values` to read instead of it. -#}
{% set spoken = ["summary", "description", "runbook_url", "runbook_url_internal", "dashboard_url", "dashboardURL"] -%}
{% set spoken = spoken + ["value_string"] if annotations.get("values") else spoken -%}
{% set notes = [] -%}
{% for key, value in annotations.items()
   if key not in spoken
   and not key.startswith("__")
   and agreed.get(key) != value -%}
{% set _ = notes.append(pair(key, value) | trim) -%}
{% endfor -%}

{% if summary -%}
{{ summary }}
{% endif -%}
{# Both, when a rule bothered to write both: a summary says what happened and a description says what it means. -#}
{% if description and description != summary -%}
{# Parted from the summary above, when there is one: run together, the two read as one paragraph. -#}
{% if summary %}
{% endif -%}
{{ description }}
{% endif -%}

{# A group of one has said its summary above. A group of many says one per instance, even when only one of them
   turned out to carry anything of its own: that line is then the only thing naming what failed. -#}
{% if summaries and (instances | length) > 1 %}
**Summaries**
{% for line in summaries[:20] -%}
- {{ line }}
{% endfor -%}
{% if summaries | length > 20 -%}
- and {{ summaries | length - 20 }} more
{% endif -%}
{% endif -%}

{# What the route grouped by, and then what the instances turned out to share beyond it. Kept apart because they
   answer different questions: the first is why these alerts arrived as one card, the second is what they have in
   common once they had. -#}
{% if agreed.keys() | select("in", grouped_by) | list %}
**Group**
{% for key, value in agreed.items() if key in grouped_by -%}
- {{ pair(key, value) | trim }}
{% endfor -%}
{% endif -%}

{% if agreed.keys() | reject("in", grouped_by) | list %}
**Labels**
{% for key, value in agreed.items() if key not in grouped_by -%}
- {{ pair(key, value) | trim }}
{% endfor -%}
{% endif -%}

{% if notes %}
**Annotations**
{% for note in notes -%}
- {{ note }}
{% endfor -%}
{% endif -%}

{% if annotations.get("runbook_url") -%}
[:book: Runbook]({{ annotations.runbook_url }})
{% endif -%}
{% if annotations.get("runbook_url_internal") -%}
[:closed_book: Runbook (internal)]({{ annotations.runbook_url_internal }})
{% endif -%}
"""  # noqa

discord_image_url = web_image_url

# SMS
sms_title = web_title

# Phone
phone_call_title = """{{ payload.get("groupLabels", {}).values() |join(", ") }}"""

# Telegram
telegram_title = web_title

telegram_message = """\
{% set annotations = payload.get("commonAnnotations", {}).copy() -%}
{% set groupLabels = payload.get("groupLabels", {}) -%}
{% set commonLabels = payload.get("commonLabels", {}) -%}
{% set severity = groupLabels.severity -%}
{% set legacyLabels = payload.get("labels", {}) -%}
{% set legacyAnnotations = payload.get("annotations", {}) -%}

{% if severity -%}
{% set severity_emoji = {"critical": ":rotating_light:", "warning": ":warning:" }[severity] | default(":question:") -%}
Severity: {{ severity }} {{ severity_emoji }}
{% endif -%}

{% set status = payload.get("status", "Unknown") -%}
{% set status_emoji = {"firing": ":fire:", "resolved": ":white_check_mark:"}[status] | default(":warning:") -%}
Status: {{ status }} {{ status_emoji }} (on the source)
{% if status == "firing" and payload.numFiring -%}
Firing alerts – {{ payload.numFiring }}
Resolved alerts – {{ payload.numResolved }}
{% endif -%}

{% if "runbook_url" in annotations -%}
<a href='{{ annotations.runbook_url }}'>:book: Runbook:link:</a>
{% set _ = annotations.pop('runbook_url') -%}
{% endif -%}

{% if "runbook_url_internal" in annotations -%}
<a href='{{ annotations.runbook_url_internal }}'>:closed_book: Runbook (internal):link:</a>
{% set _ = annotations.pop('runbook_url_internal') -%}
{% endif %}

{%- if groupLabels | length > 0 %}
GroupLabels:
{% for k, v in groupLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if commonLabels | length > 0 -%}
CommonLabels:
{% for k, v in commonLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if annotations | length > 0 -%}
Annotations:
{% for k, v in annotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{# backward compatibility with legacy alertmanager integration -#}
{% if legacyLabels | length > 0 -%}
Labels:
{% for k, v in legacyLabels.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}

{% if legacyAnnotations | length > 0 -%}
Annotations:
{% for k, v in legacyAnnotations.items() -%}
- {{ k }}: {{ v }}
{% endfor %}
{% endif -%}
<a href='{{ source_link }}'>View in AlertManager</a>
"""

telegram_image_url = None


example_payload = {
    "alerts": [
        {
            "endsAt": "0001-01-01T00:00:00Z",
            "labels": {
                "job": "node",
                "group": "production",
                "instance": "localhost:8081",
                "severity": "critical",
                "alertname": "InstanceDown",
            },
            "status": "firing",
            "startsAt": "2023-06-12T08:24:38.326Z",
            "annotations": {
                "title": "Instance localhost:8081 down",
                "description": "localhost:8081 of job node has been down for more than 1 minute.",
            },
            "fingerprint": "f404ecabc8dd5cd7",
            "generatorURL": "",
        },
        {
            "endsAt": "0001-01-01T00:00:00Z",
            "labels": {
                "job": "node",
                "group": "canary",
                "instance": "localhost:8082",
                "severity": "critical",
                "alertname": "InstanceDown",
            },
            "status": "firing",
            "startsAt": "2023-06-12T08:24:38.326Z",
            "annotations": {
                "title": "Instance localhost:8082 down",
                "description": "localhost:8082 of job node has been down for more than 1 minute.",
            },
            "fingerprint": "f8f08d4e32c61a9d",
            "generatorURL": "",
        },
        {
            "endsAt": "0001-01-01T00:00:00Z",
            "labels": {
                "job": "node",
                "group": "production",
                "instance": "localhost:8083",
                "severity": "critical",
                "alertname": "InstanceDown",
            },
            "status": "firing",
            "startsAt": "2023-06-12T08:24:38.326Z",
            "annotations": {
                "title": "Instance localhost:8083 down",
                "description": "localhost:8083 of job node has been down for more than 1 minute.",
            },
            "fingerprint": "39f38c0611ee7abd",
            "generatorURL": "",
        },
    ],
    "status": "firing",
    "version": "4",
    "groupKey": '{}:{alertname="InstanceDown"}',
    "receiver": "combo",
    "numFiring": 3,
    "externalURL": "",
    "groupLabels": {"alertname": "InstanceDown"},
    "numResolved": 0,
    "commonLabels": {"job": "node", "severity": "critical", "alertname": "InstanceDown"},
    "truncatedAlerts": 0,
    "commonAnnotations": {},
}
