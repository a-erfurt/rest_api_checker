# Local operator convenience

`rac` is an optional launcher over the authoritative argparse CLI, database status
validator, offline preflight and existing read-only web application. No scientific
policy, formula, parser, schedule, persistence schema or execution guard changes.
The original `rest-api-checker` and `rest-api-checker-web` commands remain intact.
No new dependency is required: Rich renders menus and POSIX terminal APIs read keys.

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
`credentials.env` beside config.toml. The current machine's setup points to the
already-existing private file under `/private/tmp/rac-sqlserver-environment-20260926/`;
that temporary location is not durable storage. Move it privately to durable storage
and update `env_file` if needed; this launcher never relocates it automatically.

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

The main menu has Database, Web UI, Preflight / Gate B, Experiments, Evaluation,
Inspect data, Advanced CLI and Exit. Up/down wrap, Enter selects, and number keys
select immediately. Ctrl-C exits with code 130 and restores the terminal. There is
no mouse or alternate-screen application. Plain/no-color/dumb terminals display
sequential menus without ANSI updates. Interactive keys require macOS/Linux/POSIX.
Without a TTY on both stdin and stdout, bare `rac` prints help and exits 0; it never
waits for input. `--json` also prevents entering the menu.

- Database: start/check, authoritative status, version, stop, administrative help, back.
- Preflight: actual counts and non-PASS details from the existing checker. Without
  any SQL configuration it preserves the existing offline check; a configured but
  missing credentials file is an error. Gate B is still blocked by runtime evidence.
- Experiments: real prompt comparison is **status only**, sensitivity/main evaluation
  are unavailable. Opening the menu does not dispatch a run. The separately confirmed
  **FABRICATED / TEST DATA** demo invokes the existing isolated disposable demo command.
- Evaluation: list, inspect and export existing reports through `evaluate`; no implicit
  report creation or new metric calculation.
- Inspect data: paginated, SELECT-only existing web projections for datasets, cases,
  references, prompts, models, experiments and runs. Connections roll back and close.
- Advanced CLI: original help and reproducible command examples; no shell executor.

Existing explicit commands also pass through `rac` with local defaults. Real run/
resume guards remain authoritative; the launcher does not supply `--fabricated` or
runtime evidence. JSON direct-command stdout contains JSON only; `--plain` suppresses
color/animation. `rac web --json` is rejected because it is a long-running server.

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
restored on shutdown. Stopping the web process leaves SQL running. The UI is unchanged
and remains read-only.

## Verification

See [verification record](operator_verification_2026-09-26.md). Unit tests mock container
mutations and browser launch. SQL tests use only the existing opt-in disposable test
environment. No real Ollama inference or real experiment schedule is dispatched.

## Application/admin credential separation (2026-09-26)

Local `~/.config/rest-api-checker/config.toml` now binds `env_file` to
`~/.config/rest-api-checker/application-credentials.env` (0600, dedicated
`rac_application_login`). `admin_env_file` retains
`/private/tmp/rac-sqlserver-environment-20260926/credentials.env` unchanged.
Neither file belongs in Git. Keep the retained administrative file available for
explicit administration; its current temporary-directory location is not a
backup policy.

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

The menu and existing run/resume commands retain their fabricated-only guards.
The separate, acceptance-gated comparison adapter is documented in the
[technical closure report](gate_b_closure_2026-09-26/report.md). Preparing the
candidate or opening the web UI never schedules an experiment.
