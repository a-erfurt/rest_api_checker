# RestApiChecker

RestApiChecker is the CLI and read-only web application for the bachelor thesis
**Evaluating LLM-Based Detection of Validation Response Contract Inconsistencies
in REST APIs**. It compares LLM predictions with independently stored reference
judgments for observed API responses and their OpenAPI contracts.

The interactive workflow checks **stored response evidence**; it does not send a
new request to the selected API. Its checks cover documented HTTP status (C1),
response media type (C2), and response body schema (C3). The qualified Reference
Oracle is a measurement instrument, not a competing detector. Results concern the
supported study profile and do not establish correctness for arbitrary APIs.

## Requirements

- Python **3.12** and `uv`; dependency versions are recorded in `uv.lock`.
- Microsoft SQL Server with the application schema and imported case, reference,
  prompt, model and configuration records for interactive checks and result browsing.
- Microsoft ODBC Driver 18 for SQL Server and the platform's ODBC runtime.
- A local Ollama service and an installed supported model for real LLM runs.
  Supported model tags are `qwen3.6:27b`, `gemma3:27b` and `mistral-small3.2:24b`.

Database setup and imports are explicit administration steps. Normal startup does
not create a populated database, import research data, install models or migrate
the schema. See the [SQL Server guide](docs/persistence.md) for setup and commands.

## Start the CLI

From the repository directory:

```sh
uv sync --locked
uv run --locked rac --help

# Register an existing private credential file once.
chmod 600 /absolute/path/to/private/credentials.env
uv run --locked rac configure --env-file /absolute/path/to/private/credentials.env

# Open the interactive application.
uv run --locked rac
```

Credentials must remain outside the application and research repositories. The
file contains `RAC_SQL_PORT`, `RAC_SQL_PASSWORD` and optionally `RAC_SQL_USER`.
Local, non-secret defaults are stored in `~/.config/rest-api-checker/config.toml`;
`configure` does not overwrite an existing configuration. Use an application login
for normal operations. Administrative actions require the appropriate permissions.

To type only `rac` in the current terminal, activate the environment:

```sh
source .venv/bin/activate
rac
```

Personal aliases can point to `.venv/bin/rac`; keep machine-specific paths in
local shell configuration. Bare `rac` prints help without an interactive terminal.

## Interactive checks

The main menu offers **Run API response check**, **Browse previous results**,
**Open Web UI**, and **Exit**. Use the displayed number and Enter; `q` goes back.

1. Choose the stored case set, service, operation and case type.
2. Select an available, hash-verified **P1**, **P2** or **P3** prompt and a case.
3. Choose a model and one to three repetitions.
4. At **Ready to run**, enter `p` to **Preview LLM input**. Only `y` / `yes` at
   the confirmation prompt starts the model run.

The preview uses the exact prepared request. It includes the system prompt,
complete user message, relevant OpenAPI excerpt, HTTP status, Content-Type,
response body and request options. Long sections have page navigation. Stored
reference judgments are kept outside the model input. Recognized secrets are
masked only for display, with an explicit notice.

After a run, the result panel shows reference/prediction agreement, parser status,
duration, input/output/total tokens and the requested context limit. Token counts
come from the stored provider response. The input percentage compares input tokens
with the archived request's context limit; it is not measured peak context
occupancy. Missing values remain **not recorded**. With retries, token counts refer
to the latest attempt and duration includes all attempts.

**View LLM input** reads the archived request without reconstructing it. Details,
raw model output, case files and the selected run's web page are available without another model call.

Interactive runs use a separate execution context and preserve existing scientific
results. Interactive prompt selection does not change the scientific P2 binding.
See the [interactive CLI guide](docs/live_demo.md) for navigation and boundaries.

## Start the web UI

With local operator configuration and the existing database container available:

```sh
uv run --locked rac web --open
```

Alternatively, serve the web application directly against an existing database:

```sh
uv run --locked rest-api-checker-web \
  --env-file /absolute/path/to/private/credentials.env \
  --database rest_api_checker
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The UI shows stored experiments,
reports, runs, cases and evidence. It uses read-only queries and never calls Ollama,
starts an experiment or creates a report. It serves bundled frontend assets without
a separate frontend build. See the [web UI guide](docs/web_ui.md).

## Commands and configuration

```sh
uv run --locked rac db status --plain
uv run --locked rac db start       # Existing, configured container only
uv run --locked rac db stop        # Preserve database and volumes
uv run --locked rac preflight      # Readiness checks; no inference
uv run --locked rest-api-checker --help
```

`rac` also forwards inspection, evaluation and experiment commands to `rest-api-checker`.
Scientific batches retain explicit preparation, qualification and authorization
checks. Configuration precedence is CLI options, environment variables, local
configuration, then defaults. See [operator configuration](docs/operator_convenience.md)
and the [Main-v2 procedure](docs/main_v2_handoff.md).

## Tests

The core qualification tests use the committed contract fixtures:

```sh
uv run --locked pytest -q tests/test_oracle_qualification.py \
  tests/test_oracle_boundaries.py tests/test_validator_spike.py
```

The full development suite is available with `uv run --locked pytest -q`, but it
also depends on the separate research checkout, released archives and pinned Git
history used by the original study. It is not a standalone fresh-clone acceptance
check. Historical integrity/preflight tests can report evidence drift; do not
rewrite frozen evidence to make those checks pass.

SQL integration tests require explicitly configured disposable resources via
`RAC_SQL_TEST_ENV`; application-login and backup tests have additional opt-ins.
Without those settings they are skipped. Tests use fabricated provider responses
and forbid real inference HTTP. See the [persistence guide](docs/persistence.md)
for integration-test setup.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/rest_api_checker/` | CLI, reference checks, input rendering, execution and evaluation |
| `src/rest_api_checker/web/` | Web routes, queries, templates and bundled static assets |
| `src/rest_api_checker/persistence/` | SQL repositories, immutable evidence handling and migrations |
| `tests/` | Unit, qualification, CLI/web and opt-in SQL tests |
| `tools/` | Explicit environment, qualification and experiment administration |
| `docs/` | Operational guides and required qualification/integrity evidence |

Private credentials, model weights and local environments are not part of the
application distribution.
