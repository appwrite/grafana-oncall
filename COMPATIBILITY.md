# Compatibility and lifecycle policy

Appwrite maintains this fork for its own deployments. This document defines what the automated test suite verifies. It
does not create a general support commitment for external deployments.

## Release support

- The latest stable release is the maintained release line.
- Engine and plugin versions must match.
- A version becomes stable only when its GitHub release is published. A Git tag or container tag without a published
  GitHub release is an incomplete release and must not be deployed.
- Security and correctness fixes target the latest stable release. Backports are exceptional and are not guaranteed.
- A superseded release stops receiving regular fixes when a new stable release is published.
- Breaking configuration or migration changes require a major version. Deprecations should remain available for one
  minor release when safe operation permits it.

## Tested matrix

The pull request and scheduled compatibility workflows test these versions:

| Component | Tested versions | Policy |
| --- | --- | --- |
| Grafana | 12.4.8 and 13.2.0 | The latest tested release in each listed Grafana minor line |
| Python | 3.13.11 | The engine build and backend test runtime |
| Node.js | 24.20.0 | The plugin build and test runtime |
| MySQL | 8.4.11 | Backend migrations and tests, with RabbitMQ |
| PostgreSQL | 18.6 | Backend migrations and tests, with RabbitMQ |
| SQLite | Python runtime version | Backend migrations and tests, with Redis |
| Redis | 8.2.9 | Broker tests and development deployment |
| RabbitMQ | 4.3.5 | Broker tests with MySQL and PostgreSQL |
| Container architecture | linux/amd64 and linux/arm64 | Published engine images and plugin backend binaries |

A version is supported only after it passes the repository test suite. A newer patch or minor version is not assumed to
be compatible until the matrix is updated and passes. Versions outside the matrix can work, but the maintainers do not
make a compatibility claim for them.

## Validation cadence

Every pull request runs linting, unit tests, database migrations, Helm tests, plugin builds, and Grafana end-to-end tests.
The same compatibility suite runs every week even when the repository has no code changes. A scheduled failure is
treated as a compatibility regression and must be resolved before the next release.

## Upgrade policy

Read the release notes before an upgrade. Back up the database before migrations run. Upgrade the engine and plugin in
the same maintenance window. The automated suite validates migrations from a clean database, but it does not yet test
an upgrade from persisted data. Use intermediate releases instead of skipping release lines unless the release notes
state that the direct path is safe.
