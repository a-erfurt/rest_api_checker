# Live-demo CLI audit and implementation review

Date: 2026-10-07. Repository: `/Users/aerfurt/University/Bachelor/rest_api_checker`.
Working branch: `chore/unify-rq-figures` (retained; no branch switch, commit or push).

## Outcome and scope

**Current live execution is blocked:** metadata-only `/api/version` returned
Ollama `0.40.0`, but the existing selected Evaluation-v2 binding requires
`0.35.1`. The existing runtime verifier rejects this version drift before native
measurement, generation or new demo experiment creation. The three real-database
offline dry-runs passed. No runtime was restarted/replaced and no binding was
rewritten to bypass the mismatch. A separately reviewed qualified-runtime setup
or explicit new qualification is required before the supervisor's real run.

The new `rac demo run` / `rest-api-checker demo run` provides a small interactive
service → operation → development case → model → repetitions → confirmation
flow. It creates a separate `LIVE-DEMO <uuid>` experiment and calls the existing
request/runner/parser/persistence components. A non-interactive form and a
read-only offline `--dry-run` use the same selection and planning logic.

This task implements and tests the execution path; it does not perform a real
LLM demonstration. Frozen Dataset 3, Experiment 10003, final responses/results,
P2, scientific verdict semantics and both thesis repositories remain protected.
No migration, new dependency or scientific metric was introduced.

See [the operator guide](docs/live_demo.md) for the actual demonstration steps.

## Audit evidence: CLI before this change

The audit read `AGENTS.md`, the two mandated implementation/protocol skills,
implementation state, README, CLI/evaluation/operator/web docs, entrypoints,
query and execution code, scripts and existing tests. The user explicitly
prohibited branch changes and commits; that overrides the local skill's normal
commit/feature-branch instructions.

The application uses **argparse**, not Typer or Click. Verified console scripts:

| Entrypoint | Existing behavior |
|---|---|
| `rac` | Configured launcher, interactive operator menu and forwarding to the authoritative CLI |
| `rest-api-checker` / `python -m rest_api_checker` | Authoritative CLI |
| `rest-api-checker-web` | Read-only FastAPI/Uvicorn browser UI |
| `python -m rest_api_checker.persistence` | Retained administrative compatibility entrypoint |

All root/group/leaf help was actually executed with Python bytecode writing
disabled. [The full successful pre-change captures](docs/live_demo_cli_help_before.md)
contain 76 invocations, including module/script help. Two additional initial
probes used invalid Main-v2 names; the verified replacements were
`import-dataset` and `plan-template`. No unverified name appears in the demo guide.
Help calls performed no SQL or runtime work.

Compact complete core command tree **before** the addition:

```text
rest-api-checker
  db status | version | init | create-test | destroy-test
  db migrate --expected-current N
  db backup --server-path PATH | restore-test --server-path PATH
  db import-dev --staging PATH --release PATH | import-prompts
  dataset list | cases DATASET_ID | inventory
  experiment list | show ID | schedule ID | progress ID
  experiment run ID --spool PATH [--fabricated]
  experiment resume ID --spool PATH [--fabricated]
  experiment reconcile --spool-file PATH [--fabricated]
  experiment demo [--keep] [--delay SECONDS] [--export NEW_DIRECTORY]
  experiment run-batch ID --dataset-id ID [--spool PATH] [--resume] [--dry-run | --yes]
  experiment batch-status ID --dataset-id ID
  experiment demo-batch [--delay SECONDS]
  evaluate comparison EXPERIMENT_ID | list | show REPORT_ID
  evaluate export REPORT_ID --output NEW_FILE
  inspect run RUN_ID | attempts RUN_ID
  preflight [--experiment-id ID]
  service capture --base-url URL --execution-origin ORIGIN --target-id ID
      --contract-id ID --path PATH --input PATH --case-id ID [--filename NAME]
```

Common root/leaf options: `--env-file`, `--database`, `--root`, `--research`,
`--json`, `--plain`, `--verbose`. `rac` additionally provides `configure`,
`db start`, `db stop`, `web [--open]` and configured local defaults. Its existing
menu could inspect data, experiments and reports; its experiment menu predates
real batch dispatch and exposes only status plus the fabricated demo.

Additional verified module surfaces:

- `accepted_comparison` and `sensitivity_execution`: artifact-gated `prepare`,
  `run`, `reconcile` actions, not a general single-case wizard.
- `interface_pilot_v2` and `interface_pilot_v2_live`: the bounded two-DEV-case
  interface preparation/pilot, with explicit input/runtime/context artifacts.
- `main_v2`: `integrity`, `freeze-template`, `freeze`, `prepare`, `import-dataset`,
  `plan-template`, `materialize`, `execution-template`, `authorize-execution`.
- `main_v2_context`: explicitly confirmed native render/tokenize preparation.
- `development_dataset`: separate development artifact materialization.
- `tools/runtime_qualification/capture.py`, final-evaluation bases/candidates
  preparation and SQL environment probe: argparse help captured.

No top-level `scripts/` directory exists. `tools/main_v2/launch.sh` is a real Main
launcher with status/preflight then dispatch. It is not a demo setup command.
Historical fixed-stage Gate-B and sensitivity scripts lacking an argument parser
were inspected only: passing `--help` to them could execute their work.

## What already worked, and the actual gaps

| Area | Audit finding and implementation decision |
|---|---|
| Single run | No general live single-case CLI existed. `experiment run/resume` use fabricated providers and reject real execution. Add a separate demo flow. |
| Scheduling | `experiment schedule` reads an existing schedule. New plans must use `Repository.plan_experiment`; do not pretend the command creates runs. |
| Real batch | Main-v2 `run-batch` requires an exact authorized persisted setup; it is unsuitable for rewriting the final schedule into a subset. Reuse its request preparation and common attempt executor underneath a separate demo setup. |
| Data selection | Generic API/contract/operation/case/membership/reference entities already exist. Join these records dynamically; no fixed EDX/Resistance menu. |
| Model/prompt/config | `dataset inventory` already reads models/prompts/configurations. Reuse existing supported model records, exact P2 bytes and compatible stored D07 configurations. |
| Result inspection | Existing inspect projection already compares prediction with the bound reference. Human output omitted explicit vector correctness and persistent attempt/raw IDs. Extend presentation only. |
| Raw evidence | Old verbose inspect rebuilt a v1 request. Add a read-only stored-evidence wrapper so v2 inspection does not depend on reconstruction. |
| Evaluation | `evaluate comparison` implements the full historical 324-slot comparison design, not arbitrary demo subsets. Keep operational summaries and existing report reads. |
| Simulation | `experiment demo-batch` has no SQL/model access; `experiment demo` owns disposable SQL but fabricates outputs. Keep these clearly distinct from live execution. |
| Web | Existing `/runs/{id}` detail links are sufficient; no web modification is needed. |

README and earlier CLI/operator docs contain implementation-era statements such
as “real runs have not started”. They are historical descriptions, not evidence
of the current database. This change adds a current guide without rewriting
historical qualification documents.

## Implementation and boundaries

The catalogue only offers fully referenced development datasets and excludes
Dataset 3, all evaluation datasets and cases also present in an evaluation
dataset. Services and operations are discovered through existing relationships.
The current observed service named `htts` owns the Resistance multipart endpoint;
its stored service identity is retained rather than silently renamed.

A dry-run builds and validates requests from existing data and local runtime
binding files without contacting Ollama or writing an experiment, attempt,
prediction or spool. Runtime/model readiness is checked only after execution
confirmation. Non-interactive/JSON selection requires `--case-id` and at least
one `--model-id`; non-interactive execution additionally requires `--yes`.
`--yes` never selects an arbitrary first case/model. Multiple runtime bindings
require an explicit choice; a sole discovered binding is shown in the summary.

The runner preserves P2, D07, `format_json`, the 512-token output budget and
repetition seeds 101/202/303. It measures the exact native template/token context
before creating a new experiment, rechecks source identity and then uses the
existing sequential runner, one-attempt executor, Ollama transport, strict parser,
spool and repository. Reference labels and case/fault metadata are not injected
into model input. Native context measurement can load a model; it begins only
after confirmation.

Every setup identifies `live_demo=true`, `scientific_evaluation=false` and a
unique `LIVE-DEMO` name. The existing schema stores it with kind `comparison`;
the explicit setup marker/name/notes distinguish its non-scientific purpose.
No new schema discriminator or evaluation rule is introduced. The command accepts
no existing experiment/run target. Dataset 3 and Experiment 10003 are also
explicitly guarded.

Parser failures remain final failures and have no semantic verdict. Technical
or ambiguous outcomes are preserved and require inspection; no automatic retry,
request repair, format fallback or resume mechanism is added. Cancellation before
execution produces no run. After materialization, recovery output retains the new
experiment/run IDs and spool location even when execution cannot finish.

The result reader is additive because `persistence/inspection.py` contributes to
the evaluator artifact hash. That original file remains byte-identical. The
wrapper reuses its non-raw projection and reads the exact archived request and
lossless provider envelopes for verbose output. Human presentation now adds
parser state, yes/no/N/A exact-vector correctness, Attempt-ID and raw provider
file ID, while retaining per-category correctness/reasons/duration.

## Files changed for this task

| File | Purpose |
|---|---|
| `src/rest_api_checker/cli.py` | Register `demo run`, dispatch/presentation and stored-evidence inspection wrapper |
| `src/rest_api_checker/live_demo.py` | Dynamic eligibility, existing-input plan, separate setup and shared runner integration |
| `src/rest_api_checker/live_demo_cli.py` | Interactive/non-interactive selection, confirmation, plan and result links |
| `src/rest_api_checker/live_demo_inspection.py` | Read archived requests/provider envelopes without reconstruction |
| `src/rest_api_checker/terminal.py` | Explicit parser/vector/attempt/raw identity display |
| `tests/test_live_demo.py` | Offline runner/eligibility/evidence/safety regression coverage |
| `tests/test_live_demo_cli.py` | Wizard choices, confirmation, non-TTY/JSON and dry-run coverage |
| `tests/test_live_demo_inspection.py` | Stored bytes, unattempted states, IDs and verdict presentation |
| `tests/persistence/test_live_demo.py` | Opt-in disposable SQL round trips with fabricated provider/native receipts |
| `docs/live_demo.md` | Operator guide, exact commands, recovery and short demonstration |
| `docs/live_demo_cli_help_before.md` | Actual successful pre-change help captures |
| `docs/live_demo_verification.json` | Final test, read-only smoke and preservation evidence |
| `docs/implementation_state.md` | Bounded demo capability and current runtime blocker |
| `LIVE_DEMO_CLI_REVIEW.md` | This audit/implementation report |

Existing changes in `pyproject.toml`, `uv.lock` and figure/analysis files predate
this work and are not part of the demo implementation. No user file was restored
or reset. No thesis, research-source, prompt, parser, renderer, scientific
request-builder, repository schema or frozen-evaluation artifact edit is intended.

## Current data observed read-only

A read-only scientific-database inspection on 2026-10-07 found:

| Item | Observed value |
|---|---|
| Eligible development memberships | 12, in Dataset 1 |
| Service `edx` | Memberships 1–6; `/edx/validation/body` |
| Service `htts` (Resistance endpoint) | Memberships 7–12; `/resistance/validation/file` |
| Model 1 | `qwen3.6:27b` |
| Model 2 | `gemma3:27b` |
| Model 3 | `mistral-small3.2:24b` |
| Prompt P2 | ID 2 |
| Compatible D07 configs | ID 1 for Qwen; ID 2 for Gemma/Mistral |
| Protected Dataset 3 | 82 memberships |
| Protected Experiment 10003 | 738 runs, 738 attempts, 734 predictions |

These are observed IDs, not hard-coded application assumptions. The pre-change scientific-state record includes table counts and
protected row/archive identity hashes for the final preservation comparison. Live generation and native context measurement were not performed by
this task. The metadata-only runtime check explicitly returned a version-drift blocker:
active `0.40.0`, qualified `0.35.1`. The binding file SHA-256 used by all three
successful dry-runs was
`5b8b09919e8c66c0ed4ce903ab7d7c21295807ec65559d2dbcca97f38ab2da41`.

The actual dry-run receipts reported `status=DRY RUN`, `model_calls=0`, `writes=0`
and `runtime_contacted=false`:

| Existing member/case | Model IDs | Repetitions | Planned runs |
|---|---|---|---|
| 2 / DEV-02 / PASS-PASS-PASS | 1 | 1 | 1 |
| 7 / DEV-07 / PASS-PASS-PASS | 3 | 1 | 1 |
| 3 / DEV-03 / FAIL-NOT_APPLICABLE-NOT_APPLICABLE | 1, 2, 3 | 3 | 9 |

These checks exercised current SQL catalogue and request preparation only.
They do not establish native context measurement or live provider readiness.

## Verification and known limits

- The original sandbox baseline had 1014 passed, 103 skipped and 8 failed.
  Three wrapper tests subsequently passed with their required process permission;
  five existing failures remain. They are:
  `test_cli::test_json_preflight_truthful`,
  `test_gate_b_closure::test_closure_evidence_drift_never_passes`,
  `test_operator::test_preflight_actual_backend_stays_blocked`,
  `test_runtime_evidence::test_captured_readiness_preserves_limitations_and_author_gate`,
  `test_sensitivity_execution::test_final_offline_verification_and_historical_separation`.
  Historical source qualification, including pre-existing `pyproject.toml` drift,
  is not silently repaired by changing frozen evidence or weakening tests.
- The result-display change alone passes all 8 new offline tests. Its combined
  CLI/operator/terminal/web run passed 178 tests and reproduced two existing
  preflight expectations: tests expect BLOCKED while source-bound historical
  preflight reports FAIL for existing `experiment/batch.py`/`pyproject.toml` drift.
- Final full suite: **1098 passed, 105 skipped, 5 failed** in 42.02 seconds.
  The five failures are exactly the baseline failures listed above; zero new
  failures and zero test errors. No historical hashes or test expectations changed.
- New offline coverage: **81 passing tests** (42 runner, 31 wizard/error handling,
  8 stored-result tests). Tests cover confirmation, protected data, exact request
  identities, parser/runtime/config drift, missing predictions, no hidden retries,
  and retaining recovery IDs after uncertain commits or failed setup reads.
  Fabricated collaborators and the global HTTP guard prevent real inference.
- The two new SQL round-trip tests are opt-in and were intentionally skipped:
  dedicated credentials for the separate disposable SQL test instance were not
  available, and the user explicitly authorized omitting those optional tests.
  No disposable SQL integration acceptance is claimed. Read-only checks on the
  scientific database are a different verification layer.
- No successful real model demo is claimed. The active runtime version mismatch
  remains a verified operational blocker.
- The supported model roster and fixed configuration remain bounded by the
  current scientific request builder. Dynamic service discovery is not automatic
  scientific qualification of every possible API/model/runtime.
- The existing `rac` top-level menu is retained. The direct live-demo entrypoint is
  `rac demo run`; the historical Experiments submenu still offers the fabricated
  presentation flow.
- An interrupted demo has no automatic resume command. Preserve IDs/spool and
  inspect first. A deliberate fresh demo is a new experiment.
- Demo runs have no newly created comparison report; the web Evaluation page may
  state that no persisted report is available while run details remain usable.

## Final preservation and read-only checks

[Machine-readable verification](docs/live_demo_verification.json) records the final
results, runtime blocker, actual dry-runs and current source hashes. Three explicit
SQL-backed previews and a real interactive terminal preview passed with zero
writes/runtime calls. Existing `db status`, inventory, experiment progress,
run inspection and verbose attempts commands returned exit 0. The read-only web
routes `/runs/10433`, `/runs/10433?tab=raw` and `?tab=attempts` returned HTTP 200
through the actual app and database; no server lifecycle action was needed.

All 13,905 pre-existing repository files were hash-compared. Only the intended
CLI, terminal presentation and implementation-state files changed. Existing dirty
analysis/dependency files and all frozen source/evidence files are unchanged.
All 137 German thesis files and all 406 English thesis files are byte-identical.
The branch and HEAD are unchanged; no commit or push occurred.

Protected Dataset 3, its 82 memberships, Experiment 10003, its 738 runs,
738 attempts and 734 predictions have identical before/after row fingerprints.
All scientific table counts and all 10,259 archive identities are unchanged.
A read-only SHA-256 check of every stored archive blob found **zero integrity
mismatches**. No real generation or native measurement was performed.

Reproduction of the offline test suite uses the existing environment:

```sh
PYTHONDONTWRITEBYTECODE=1 env -u RAC_SQL_TEST_ENV -u RAC_SQL_APPLICATION_ENV \
  -u RAC_SQL_APP_TEST_ENV -u RAC_SQL_TEST_BACKUP_DIR \
  .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Verified command card and 5–10-minute script

```sh
cd /Users/aerfurt/University/Bachelor/rest_api_checker
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/openssl@3/lib
.venv/bin/rac db status
.venv/bin/rac demo run --dry-run
.venv/bin/rac demo run
.venv/bin/rac inspect run RUN_ID
.venv/bin/rac inspect attempts RUN_ID --verbose --json
.venv/bin/rac experiment progress EXPERIMENT_ID
.venv/bin/rac experiment schedule EXPERIMENT_ID
.venv/bin/rac web --open
```

Before the meeting, confirm available SQL/runtime/model and rehearse the selection
without generation. Show a stored development case and reference (1 minute), the
dry-run summary (1–2 minutes), then authorize one real run (runtime-dependent).
Compare parser status and the three categories (1–2 minutes), open the printed
`http://127.0.0.1:8000/runs/RUN_ID` link and raw/attempt evidence (1–2 minutes).
Finish with `experiment progress` to show the separate demo's completed/pending
counts. Model cold-start can exceed this timing; no latency promise is made.

**DO NOT RUN** a Main dispatch/resume/materialization command or
`tools/main_v2/launch.sh` against Experiment 10003 for this demonstration. Do not
modify Dataset 3, final outcomes or parser failures. `evaluate comparison` is not
a demo-subset aggregation command. Existing reports remain available through
`evaluate list`, `evaluate show REPORT_ID` and non-overwriting `evaluate export`.
