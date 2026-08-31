# Security policy

## Supported versions

Security fixes are released for the latest stable version of this fork. Older versions do not receive regular fixes.
Upgrade the engine and plugin together because mixed versions are not supported.

See [COMPATIBILITY.md](COMPATIBILITY.md) for the tested runtime matrix and lifecycle policy.

## Report a vulnerability

Do not report a security vulnerability through a public issue, discussion, or pull request.

Report it privately using either:

1. [GitHub private vulnerability reporting](https://github.com/appwrite/grafana-oncall/security/advisories/new)
2. Email [security@appwrite.io](mailto:security@appwrite.io)

Include the affected version or commit, reproduction steps, impact, and any known mitigation. A minimal proof of concept
is useful when it does not contain sensitive data.

Appwrite aims to acknowledge a report within two business days and complete an initial severity assessment within seven
business days. Remediation and disclosure timing depend on severity, exploitability, and release risk. Appwrite will
coordinate disclosure with the reporter when the issue is confirmed.

## Scope

This policy covers the engine, Grafana plugin, container images, Helm chart, and release artifacts in this repository.
Report vulnerabilities in another Appwrite project through that project's security policy or to
[security@appwrite.io](mailto:security@appwrite.io).
