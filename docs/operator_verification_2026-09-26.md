# Operator convenience verification — 2026-09-26

Baseline: `485f6696cb36086b1c9bfdf39b5a27a61fdd92fa` on main.
Feature branch: `feature/operator-convenience`.

## Automated checks

- Focused operator suite: **58 passed**.
- Earlier focused operator + existing CLI/web suite: **150 passed**; subsequent
  small fixes and added checks are included in the final full-suite result below.
- Final full suite: **637 passed**, no failures/errors/skips, **133.30 seconds**:

  ```sh
  RAC_SQL_TEST_ENV=/private/tmp/rac-sqlserver-environment-20260926/credentials.env \
  RAC_SQL_TEST_BACKUP_DIR=/private/tmp/rac-operator-backup-verification \
  .venv/bin/python -m pytest -q tests tools/sqlserver_environment/test_probe.py
  ```

  Includes the existing CLI/evaluator/web suites, Q01–Q26, disposable SQL integration,
  backup/restore and four probe converter tests. SQL fixtures use marked disposable
  databases. Existing test-wide guards forbid real HTTP/inference connections.
- `uv sync --offline` installed the new entry point without adding dependencies.
- Installed `uv run rac --help`, `uv run rest-api-checker --help` and
  `uv run rest-api-checker-web --help` passed. Original script mappings unchanged.
- `git diff --check` passed.

Operator tests cover config precedence and aliases; exact 0600 permission checks;
missing/invalid credentials and redaction; existing/stopped containers; known identity
and port checks; readiness timeout; missing DB/schema diagnostics; stop preservation;
non-TTY help; numeric/arrow key decoding; Ctrl-C; plain menu visibility; original Gate-B
guards; demo labels/confirmation; existing-report-only menu actions; SELECT projection
reuse/rollback; existing web factory, browser opening after startup, environment
restoration, occupied port diagnostics and returning from Advanced CLI help.

## Live and terminal checks

- Saved non-secret defaults at `~/.config/rest-api-checker/config.toml`, referring
  to the existing private 0600 credentials file. No password was read into output,
  copied, or written to config. No existing credentials file was rewritten.
- Docker inspect projected only non-secret identity/state fields: configured
  `rac-sql-env-20260926-sqlserver-1` running, expected project/service labels.
- `uv run rac db start`: existing SQL running, application DB `rest_api_checker`,
  authoritative schema version **2**, **READY**. No init/migration/import call.
- `uv run rac preflight --plain`: **6 PASS, 5 BLOCKED, 0 FAIL**; overall **BLOCKED**.
  Missing model/runtime/template/options/context/attribution/acceptance evidence was
  displayed; none was fabricated or inferred from mocks.
- Actual PTY sessions exercised up/down + Enter, Database submenu, numeric Back,
  numeric Exit, Gate-B display, Advanced CLI return and Ctrl-C. Both ANSI and plain/no-color paths were
  observed. Initial plain transient-menu suppression was fixed and regression-tested.
- `uv run rac web --port 8017 --plain`: existing app started, local URL/readiness
  banner printed, HTTP GET `/` returned **200**. Ctrl-C stopped the web process.
- Final SELECT-only application DB check: schema **2**, dataset cases **12**,
  reference results **12**, prompts **3**, experiments **0**, runs **0**,
  predictions **0**, evaluation reports **0**. Connection rolled back and closed.

## Scope and final self-review

| Question | Verified result |
|---|---|
| Automatic application `db init`? | No |
| Automatic application migration? | No |
| Automatic DEV/prompt import? | No |
| Gate B weakened or bypassed? | No; existing guard unchanged, menu has no real execution action |
| Duplicated evaluator or web application? | No; existing dispatch/projections/factory reused |
| Credentials printed or copied? | No; safe diagnostics tested with secret sentinels |
| Bare `rac` waits in CI/non-TTY? | No; help and exit 0 before loading config/input |
| Stop removes data/resources? | No; only verified container ID stop, no removal/down/prune |
| Original CLI usable? | Yes; unchanged source and entry points, regression suites pass |
| Real Ollama inference or study schedule executed? | No |
| Frozen scientific files changed? | No; source diff is launcher/tests/docs/entry-point only; preflight hashes pass |

No parser, scheduler, evaluator, persistence implementation, migration, prompt,
DEV artifact, Oracle or web app file changed. Research remained read-only; its
pre-existing literature changes were left untouched. Fabricated executions in
the existing tests remain isolated test data, never study evidence.

## Limits and retained state

- Start-from-stopped and stop are mock-verified; the live SQL container was already
  running and was deliberately left running. No claim of new graceful-stop
  qualification is made for this previously qualified emulated environment.
- `--open` browser launch is mock-tested, not manually opened during verification.
- Menu keys require POSIX. Docker Desktop/engine must be available; no automatic
  installation, container creation or daemon start is attempted.
- Credentials remain at their existing temporary external location. The config
  remembers that path; durable relocation is an explicit operator operation.
- Existing backup/restore tests retain their disposable backup evidence under
  `/private/tmp/rac-operator-backup-verification`. No study backup/data was altered.
