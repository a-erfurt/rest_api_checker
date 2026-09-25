# Disposable SQL Server environment probe

This directory qualifies one local configuration using fabricated fixtures only.
It is not the application schema, a migration system, or a persistence layer.
See [the recorded result](../../docs/sqlserver_environment_check_2026-09-26.md).

The Compose project, database names and image digest are deliberately fixed for
this task. Do not point this probe at a study server or reuse existing resources.
`initialize` refuses an existing database; `restore` refuses an existing target;
evidence files and backup files cannot be overwritten by the probe. No phase
performs cleanup. Failures produce JSON diagnostics and a nonzero exit status.

## Requirements and credentials

Python 3.12, the project's uv environment, native unixODBC and Microsoft's ODBC
Driver 18 are required. The test used Driver 18.7.1.1, unixODBC 2.3.14 and
pyodbc 5.3.0. Install the optional group with `uv sync --locked --group sqlserver-probe`.
Do not update Docker/emulation settings or unrelated software to make it work.

Create a private directory **outside Git** and a mode-0600 `credentials.env` with
`RAC_SQL_PASSWORD` (new strong disposable password) and `RAC_SQL_PORT` (unused
localhost port). Do not print this file, a rendered Compose configuration, a full
container inspection, or a connection string containing the password. The
recorded run used `/private/tmp/rac-sqlserver-environment-20260926/credentials.env`
and port 14339. A temporary directory is not permanent backup retention.

The administrative login is used only for this disposable creation/backup test.
Connections explicitly use `Encrypt=yes;TrustServerCertificate=yes`: encryption
was observed, but server-certificate identity is not verified. This exception is
per connection, not a change to host trust or Docker security configuration.

## Explicit phases

From the technical repository root, after inspecting resources and selecting an
unused project/port (the recorded names must already belong to this task):

```sh
RAC_ENV=/private/tmp/rac-sqlserver-environment-20260926/credentials.env
RAC_COMPOSE=tools/sqlserver_environment/compose.yaml
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" config --quiet
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" up -d
.venv/bin/python tools/sqlserver_environment/probe.py initialize \
  --env-file "$RAC_ENV" --evidence /private/tmp/initialize-new.json
.venv/bin/python tools/sqlserver_environment/probe.py unique \
  --env-file "$RAC_ENV" --evidence /private/tmp/unique-new.json
docker restart rac-sql-env-20260926-sqlserver-1
.venv/bin/python tools/sqlserver_environment/probe.py verify \
  --env-file "$RAC_ENV" --evidence /private/tmp/restart-new.json
docker exec rac-sql-env-20260926-sqlserver-1 mkdir -p /var/opt/mssql/backup
.venv/bin/python tools/sqlserver_environment/probe.py backup \
  --env-file "$RAC_ENV" --evidence /private/tmp/backup-new.json
```

Wait for SQL Server readiness before each host connection; do not interpret a
startup timeout as success. Stop on a failed phase and retain its evidence.
Use a new evidence pathname each time. Do not rerun `initialize` or `backup` on
the retained completed probe. The report records the first run's timestamp
conversion failure, its diagnosis, and verification without recreating data.

Copy the new backup to a **previously absent**, private host path with `docker cp`,
then copy that host file to the previously absent container path
`/var/opt/mssql/backup/host_copy_for_restore.bak`. Assign only that file to the
container's `mssql` user (`docker exec --user root ... chown mssql <path>`), retain
mode 0600, and compare all three SHA-256 hashes. Then run:

```sh
.venv/bin/python tools/sqlserver_environment/probe.py restore \
  --env-file "$RAC_ENV" --evidence /private/tmp/restore-new.json
.venv/bin/python -m unittest discover -s tools/sqlserver_environment -p test_probe.py -v
docker stop rac-sql-env-20260926-sqlserver-1
```

Restore uses separate MDF/LDF paths, checksums and no `REPLACE`; the original
database is never a restore target. All four fixtures are compared against their
original bytes/values and against both databases. Timestamp reads use the native
ODBC structure so the original offset and 100 ns digit survive; Python's ordinary
microsecond `datetime` and SQL style-127 output conversion are not used.

## Safe cleanup after evidence retention

Inspect the project labels/names first. The following removes **only this
Compose project's** container, network and named volume, including both probe
databases and in-volume backups. It was **not executed** during qualification:

```sh
docker compose --env-file "$RAC_ENV" -f "$RAC_COMPOSE" down --volumes
```

Retain the external backup and credentials as long as needed. Their later removal
must name only `/private/tmp/rac-sqlserver-environment-20260926/`, after deciding
whether to retain its backup/logs elsewhere. Do not use global pruning. Do not
automatically uninstall the shared host driver, its dependencies or the image.
