# Local operator convenience

`rac` is an optional launcher over the authoritative argparse CLI, database status
validator, offline preflight and existing read-only web application. No scientific
policy, formula, parser, schedule, persistence schema or execution guard changes.
The original `rest-api-checker` and `rest-api-checker-web` commands remain intact.
Rich renders the terminal output; the interactive application uses numbered menus.

## Setup and direct commands

From the technical repository, run `uv sync --locked`, then register an **existing**
private credentials file (outside both repositories, mode exactly 0600):

```sh
uv run rac configure --env-file /absolute/path/to/credentials.env
uv run rac
uv run rac db start
uv run rac db stop
uv run rac web
uv run rac web --open
uv run rac preflight
uv run rac preflight --json
uv run rac db status --plain
uv run rac evaluate list
uv run rest-api-checker --help
```

The credential file uses the existing `RAC_SQL_PASSWORD` and `RAC_SQL_PORT` fields,
plus optional `RAC_SQL_USER`. Configure never asks for, echoes or copies a password,
and never rewrites credentials or an existing config. If config exists, edit only
its non-secret defaults explicitly. No credentials are embedded in commands or TOML.

Default config: `~/.config/rest-api-checker/config.toml`. `RAC_CONFIG` can select a
different file. Without a configured path, credentials are discovered as
`credentials.env` beside config.toml. Keep credentials in durable private storage;
`/private/tmp` is not a retention policy. Update `env_file` when moving them;
this launcher never relocates a credential file automatically.

| TOML key | CLI override | Environment | Project default |
|---|---|---|---|
| `root` | `--root` | `RAC_ROOT` | source checkout |
| `research` | `--research` | `RAC_RESEARCH` | sibling `bachelor_rest_api_checker` |
| `env_file` | `--env-file` | `RAC_ENV_FILE` | config directory / `credentials.env` |
| `database` | `--database` | `RAC_DATABASE` | `rest_api_checker` |
| `container` | `--container` | `RAC_CONTAINER` | `rac-sql-env-20260926-sqlserver-1` |
| `compose_project` | `--compose-project` | `RAC_COMPOSE_PROJECT` | `rac-sql-env-20260926` |
| `host` | `--host` | `RAC_WEB_HOST` | `127.0.0.1` |
| `port` | `--port` | `RAC_WEB_PORT` | `8000` |

Precedence: **explicit CLI > environment > local config > project defaults**.
`RAC_WEB_ENV_FILE` and `RAC_WEB_DATABASE` remain supported as environment aliases,
below the corresponding `RAC_ENV_FILE` / `RAC_DATABASE` names. These defaults apply
only to `rac`; the original CLI keeps its explicit arguments and behavior.
CLI options work before or after the command. Web hosts are restricted to loopback.

## Menus

Bare `rac` opens **Run API response check**, **Browse previous results**,
**Open Web UI**, and **Exit**. Enter a displayed number and press Enter; Enter
selects the first option and `q` goes back. Long selection lists support paging,
search and `d NUMBER` for details. Confirmation defaults to No. See the
[interactive guide](live_demo.md) for prompt selection, exact-input preview,
token/context display and the separate storage of confirmed interactive runs.

Without a TTY on both stdin and stdout, bare `rac` prints help and exits 0;
it never waits for input. `--json` also prevents entering the menu. Selection
and browsing do not dispatch inference; a confirmed response check does.

Database, preflight, evaluation, inspection and other explicit commands remain
available through `rac` with local defaults. Scientific execution guards remain
authoritative; the launcher does not manufacture runtime evidence. The original
`experiment run/resume/reconcile` path remains restricted to fabricated demos.
JSON direct-command stdout contains JSON only; `--plain` suppresses color and
animation. `rac web --json` is rejected because it is a long-running server.

## Database and web lifecycle

Start checks an **existing** container with the exact configured name, matching
Compose project and `sqlserver` service labels, and matching SQL port bound to
127.0.0.1. It captures the container ID and only starts that ID if stopped. It never
creates a container or starts Docker Desktop. Docker must already be available.

SQL readiness has a 60-second retry budget; the existing driver's final in-flight
connection/query can take up to 10 seconds each. Docker calls have their own bounded
15/30-second timeouts. Rejected credentials and missing ODBC driver fail immediately.
Startup checks visibility of the existing application database, then delegates to
`db status` for authoritative migration version/checksum validation. Missing database,
unavailable SQL, rejected credentials and schema mismatch have distinct diagnostics.
Missing database visibility can also indicate insufficient login permissions.

There is **no implicit db init, migration, DEV import or prompt import** in start,
web or normal menu navigation. Missing databases receive explicit administrative
command guidance. Only an explicitly confirmed fabricated demo may create/migrate/
populate its own marked disposable test database, as the original command does.

Stop verifies the same container identity and runs only `docker stop --time 30` on
its ID. It checks the resulting stopped state. It never removes containers, volumes
or databases, and never runs down/prune. As with ordinary Docker stop, Docker may
terminate the engine after the grace period; the prior local graceful-stop limitation
remains unchanged. Stop is reversible with start.

Web reserves the local port, checks/starts SQL, then serves the existing `create_app()`
through Uvicorn. Address-in-use is reported before SQL startup. `--open` opens the
browser only after Uvicorn reports startup; temporary web environment overrides are
restored on shutdown. Stopping the web process leaves SQL running. The UI remains
read-only; current browsing behavior is described in the [Web UI guide](web_ui.md).

## Verification

```sh
uv run --locked pytest -q tests/test_operator.py tests/test_interactive_app.py tests/test_root_live_wizard.py
```

Unit tests mock container mutations, browser launch and inference. SQL tests use
only an explicitly configured disposable test environment; see the
[persistence test procedure](persistence.md#verification-command-and-stage-boundary).
The [README](../README.md#tests) lists the complete suite's external prerequisites.

## Application/admin credential separation (2026-09-26)

Use `env_file` in `~/.config/rest-api-checker/config.toml` for a private
application credential file (mode 0600, dedicated application login) and
`admin_env_file` for separate administrative credentials. Neither file belongs
in Git. Keep both files in durable private storage; the administrative file is
used only for explicit administration.

Normal `rac` inspection, preflight, experiment/evaluation reads and web use the
application file. Only explicit `db init`, `migrate`, `create-test`,
`destroy-test`, `backup`, `restore-test`, and the disposable `experiment demo`
route to `admin_env_file`. Docker lifecycle commands keep their existing behavior.
Normal operations never fall back to admin credentials after a permission error.
The web remains SELECT-only by implementation; the shared application principal
also has the runtime writes granted by migration 002. No extra web principal was
introduced.

For each configuration key the precedence is explicit launcher option, `RAC_*`
environment (including existing web aliases), local TOML, then default. Credential
routing is applied after this resolution: the admin binding is selected only for
the listed commands. An explicit `--env-file` overrides routing for that command.
`RAC_ENV_FILE` selects the normal application binding; `RAC_ADMIN_ENV_FILE` selects
the administrative binding. Legacy configs without an admin binding keep their
previous single-file behavior. The original `rest-api-checker --env-file ...`
commands are unchanged and remain fully explicit.

The original `experiment run/resume/reconcile` commands retain their
fabricated-only guards. The separate, acceptance-gated comparison adapter is
documented in the [technical closure report](gate_b_closure_2026-09-26/report.md).
Current interactive runs follow the [live-check policy](live_demo.md#runtime-policy-and-separate-storage).
Opening the Web UI never schedules an experiment.
