# RestApiChecker live demo

**Execution currently blocked (2026-10-07):** the metadata-only runtime check
found Ollama **0.40.0**; the available qualified binding requires **0.35.1**.
Three real-database offline dry-runs passed. Real execution rejects this mismatch
before native measurement, generation or new experiment creation. A separately
reviewed setup of the qualified runtime, or a new explicit qualification, is
required. Do not edit frozen versions/hashes or bypass the guard. This task did
not restart Ollama or perform a real LLM run.

The demo selects a stored development case and creates a new `LIVE-DEMO <uuid>`
experiment after confirmation. Its input is the existing contract and observed
API response; it does not call EDX/Resistance again. The default is **one case ×
one model × one repetition**, outside the frozen scientific evaluation.

## 1. Prerequisites and environment

```sh
cd /Users/aerfurt/University/Bachelor/rest_api_checker
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/openssl@3/lib
.venv/bin/rac db status
```

Use the existing installed environment, SQL Server database/current schema,
ODBC Driver 18 and a configured mode-0600 application credentials file outside
the repository. `rac` normally reads `~/.config/rest-api-checker/config.toml`.
If configuration is absent, register an **existing** private file:

```sh
.venv/bin/rac configure --env-file /absolute/path/to/application-credentials.env
```

`configure` refuses to rewrite an existing configuration. `rac db start` can
start/check the existing identity-verified container; no demo command creates a
container, initializes SQL or migrates its schema.

SQL must contain referenced development memberships, unchanged P2, supported
model records and compatible stored D07 configurations. For execution, the
qualified local Ollama runtime at `http://127.0.0.1:11434`, model digests/native
templates and render/tokenize support must match the selected runtime binding.
An offline dry-run requires SQL/local files, but does not establish runtime readiness.

## 2. Interactive single run

```sh
.venv/bin/rac demo run --dry-run
.venv/bin/rac demo run
```

The first command rehearses selection without writes or runtime contact. The
second selects service → operation → case → model → repetitions, shows the full
plan and asks `Execute real LLM run(s)? [y/N]`. Enter keeps the default **No**.
Choose one model and press Enter for one repetition. Services, operations and
case labels come from existing database records.

The summary shows P2, stored configuration IDs, `format_json`, fixed options,
seeds, qualified runtime and recovery directory. Native context measurement and
live model checks begin only after confirmation. The new experiment is created
only after those checks pass. The existing attempt runner, transport, strict
parser and persistence retain the result.

## 3. Concrete non-interactive commands and multiple runs

Read IDs and options with:

```sh
.venv/bin/rac dataset list
.venv/bin/rac dataset cases 1
.venv/bin/rac dataset inventory
.venv/bin/rac demo run --help
```

`--case-id` means **dataset membership ID**, not `test_cases.id`. This current
EDX combination passed its read-only dry-run:

```sh
.venv/bin/rac demo run --case-id 2 --model-id 1 --repetitions 1 \
  --runtime-binding docs/runtime_qualification_2026-09-26/evaluation_v2_main_runtime_ollama_0.35.1_20261003/runtime-binding.json \
  --dry-run
```

After resolving the runtime mismatch and reviewing the plan, replace `--dry-run`
with `--yes` to execute that explicit selection. Non-interactive/JSON mode requires
case and model IDs; execution also requires `--yes`. Multiple runtime bindings
require an explicit choice. A sole discovered binding is displayed automatically.

Repeat `--model-id` for several models; `--repetitions` accepts 1, 2 or 3 with
unchanged seeds 101/202/303. The nine-run preview uses `--case-id 3 --model-id 1
--model-id 2 --model-id 3 --repetitions 3 --dry-run` and the same binding.
`--dataset-id` optionally narrows case selection.

Without `--spool`, recovery files use a unique directory under
`~/.local/state/rest-api-checker/live-demo/`. An explicit `--spool` selects a
recovery directory. A dry-run creates neither spool nor experiment.
The authoritative command also accepts explicit credentials:

```sh
.venv/bin/rest-api-checker --env-file /absolute/path/to/application-credentials.env \
  --database rest_api_checker demo run
```

## 4. Read the result and raw evidence

Replace `RUN_ID` with the new ID printed during execution:

```sh
.venv/bin/rac inspect run RUN_ID
.venv/bin/rac inspect attempts RUN_ID
.venv/bin/rac inspect attempts RUN_ID --verbose --json
```

The result shows parser status, C1/C2/C3 prediction/reference, vector correctness,
category differences, reasons, Attempt-ID, raw provider response file ID and
duration. The immediate live result also shows the observed API response ID.
A parser failure or unfinished run has **no semantic verdict** and correctness
is **N/A**. Parser validity does not imply a correct prediction.

Verbose inspection reads the exact persisted request/user evidence and lossless
base64 provider envelopes. It does not reconstruct a request or call a model.
Both inspect commands use the same existing result projection.

## 5. Open the existing web UI

In another terminal:

```sh
.venv/bin/rac web --open
```

Default: **http://127.0.0.1:8000**. Open the printed `/runs/RUN_ID` link for reasons,
original response, OpenAPI/request context, raw output and attempts. Select the
`LIVE-DEMO` experiment or use `/runs?experiment=EXPERIMENT_ID` to find its runs.
For another port, keep links consistent:

```sh
.venv/bin/rac web --port 8001 --open
.venv/bin/rac demo run --ui-url http://127.0.0.1:8001
```

`--ui-url` changes the suggested link only. The original launcher remains:

```sh
.venv/bin/rest-api-checker-web --env-file /absolute/path/to/application-credentials.env \
  --database rest_api_checker --host 127.0.0.1 --port 8000
```

The UI is read-only and never creates reports or executes models. `rac web` may
start/check the configured SQL container; the original web launcher does not.
Stopping web leaves SQL running.

## 6. Summary and existing evaluation reports

```sh
.venv/bin/rac experiment show EXPERIMENT_ID
.venv/bin/rac experiment progress EXPERIMENT_ID
.venv/bin/rac experiment schedule EXPERIMENT_ID
.venv/bin/rac evaluate list
.venv/bin/rac evaluate show REPORT_ID
.venv/bin/rac evaluate export REPORT_ID --output /absolute/path/to/new-report.json
```

Experiment commands read the schedule and completed/pending/outcome counts.
Report commands read/export **existing** reports; export refuses overwriting.
**Do not use `evaluate comparison` for the demo subset:** it creates a report for
the separately approved full historical comparison design. Demo output adds no
scientific ranking or thesis metrics. Its run pages work without a report.

## 7. Current safe cases and models

Observed read-only on 2026-10-07: Dataset 1 has 12 eligible memberships. Stored
service `edx` covers members 1–6; **`htts`** covers members 7–12 and the Resistance
operation `POST /resistance/validation/file`. Select `htts` for that endpoint;
the wizard preserves the stored name.

| Membership | Case/reference | Dry-run model selection |
|---|---|---|
| 2 | DEV-02 — PASS/PASS/PASS | ID 1: `qwen3.6:27b` |
| 7 | DEV-07 — PASS/PASS/PASS | ID 3: `mistral-small3.2:24b` |
| 3 | DEV-03 — FAIL/NOT_APPLICABLE/NOT_APPLICABLE | IDs 1/2/3, three repetitions |

Model ID 2 is `gemma3:27b`. These three selections passed offline planning; they
are demonstration choices, not evidence of model superiority. Start with one
model and one repetition; loading time depends on the machine. The wizard keeps
P2, compatible D07, `format_json` and the 512-token output budget unchanged.

Recheck IDs if inventory changes. Only referenced development cases absent from
all evaluation datasets are offered. A service appears only if it has eligible
memberships; its presence in final data is insufficient. Dynamic discovery does
not silently qualify new contracts, models or runtimes.

## 8. Recovery

- **No eligible cases:** inspect dataset/Data views. Do not copy, import or relabel
  final cases to populate the demo.
- **SQL error:** check `rac db status`, application credentials, ODBC and OpenSSL.
  No automatic migration or administrator fallback occurs.
- **Runtime/context mismatch:** preserve the diagnostic and check the selected
  qualification. Do not edit frozen bindings or bypass checks.
- **Parser failure:** inspect raw output; retain the failure. No repair, recoding,
  fallback format or automatic retry occurs.
- **Technical error/interruption:** preserve printed experiment/run IDs and spool;
  use `experiment progress` and `inspect attempts --verbose`. Ambiguous/reserved
  attempts are never automatically reissued. Do not use historical fabricated
  resume or Main `run-batch` for a demo. A later deliberate new demo creates a
  separate experiment and does not resolve or overwrite the previous attempt.
- **Port occupied:** use a free loopback port and matching `--ui-url`, or open
  the existing UI. Do not stop an unrelated process.

## 9. Suggested 5–10-minute demonstration

Resolve runtime readiness before the meeting; cold model loading is additional.
Show the stored development case and reference (1 minute), rehearse
`rac demo run --dry-run` (1–2 minutes), then run `rac demo run` with the same
selection and confirm one attempt. Compare parser validity and C1/C2/C3 with
`rac inspect run RUN_ID` (1–2 minutes), open the printed run link and raw evidence
(1–2 minutes), then show `rac experiment progress EXPERIMENT_ID`.

```sh
cd /Users/aerfurt/University/Bachelor/rest_api_checker
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/openssl@3/lib
.venv/bin/rac db status
.venv/bin/rac demo run --dry-run
.venv/bin/rac demo run
.venv/bin/rac inspect run RUN_ID
.venv/bin/rac experiment progress EXPERIMENT_ID
.venv/bin/rac web --open
```

## 10. DO NOT RUN against final results

**Experiment 10003 and Dataset 3 are protected.** Never dispatch, resume, overwrite,
delete or repair their runs, responses, results or memberships for this demo.
The new command accepts no existing experiment ID and excludes final cases.
Historical `experiment run-batch`, `main_v2` authorization/materialization and
`tools/main_v2/launch.sh` are **not demo setup commands**.

This task verified SQL reads and offline planning; the runtime check exposed the
version mismatch stated above. No real generation or successful end-to-end live
execution is claimed. See [the audit report](../LIVE_DEMO_CLI_REVIEW.md) for tests,
pre-existing failures and verification limits.
