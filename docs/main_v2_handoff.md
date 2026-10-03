# Main-v2 technical handoff

This is an operator procedure, **not an execution or scientific approval**.
Human decisions are inputs. The final 2.0 dataset is already frozen: SQL dataset 3,
82 ordered cases, three models and three repetitions, 738 planned logical runs.
Research, v1 evidence, service sources and the Thesis are read only.

The additive runtime/authorization patch leaves the frozen dataset and original
prepared package intact. `prepare --runtime-qualification PATH` selects an exact
qualification directory with mandatory `--runtime-manifest-sha256` and
`--runtime-receipt-sha256`; it never discovers a latest runtime. Omitting selection
retains the historical frozen runtime. Subsequent commands use the explicit
selection recorded in the new prepared manifest and verify it again.

The status `PASS_FOR_BOUNDED_INTERFACE_PILOT` is retained literally. The existing
Main preparation already consumed that status. The archived
`output_interface_pilot_v2/interface_selection.md`, "FACT: runtime boundary",
requires new exact-request contexts and current identity checks for later use.
The new loader checks the complete qualification manifest, receipt, runtime,
model digests, templates, expected blob identities and recorded blob verification,
native parity and 18 qualified DEV proofs. Those DEV proofs do not satisfy Main
coverage. No qualification status is promoted and no inference consent is inferred.
The existing `freeze.verify_live` still checks actual version, binaries, host and
native model metadata before Main context measurement and batch preflight.

## Architecture and release gates

`main_v2_release` validates the versioned candidate manifest and complete external
review files, invokes that archive's offline `scripts/verify_candidate.py`, and
binds its successful receipt to the exact manifest, reviewer files and IDs. The
freeze requires a separate named, dated human decision over those hashes, coverage
summary and dynamically calculated denominators. Exclusions, replacements and
different labels block that candidate version. Prepare a new, reviewed candidate
version as required by its `FREEZE_PROCEDURE.md`; this utility never chooses
membership, approves a row, repairs a label or reuses approval for a revised case.
The archived checker is version-specific; a revised candidate must carry its own
valid checker. The new materializer has no fixed observation or run count.

The final package is a new directory outside R. It contains the untouched candidate
closure, exact human review and freeze decision bytes, integrity receipt, explicit
ordered final dataset and hash manifest. It can later be archived through the
separately authorized research workflow. Candidate IDs remain unchanged.
Final membership records transcribe the supplied human review and reference status;
the original candidate's pending status remains preserved in the untouched archive.

`main_v2 import-dataset` uses the existing `Repository` file/case/reference/dataset
relationships and an atomic import. References are the human-confirmed archived
proposals, never labels inferred from a service state or source code. The SQL
projection follows `service_capture.materialize`: captured responses have the
storage origin `natural_observation`, including controlled service executions.
The complete original `natural_vs_controlled`, execution origin, dependency and
exposure metadata are retained; that storage mapping makes no independence claim
or scientific reclassification. It invents no synthetic parent response.

`prepare` uses the candidate's authority paths and hashes, frozen P2, the existing
v2 request builder, `request.MODELS`, `request.SEEDS`, `request.OPTIONS`, and the
qualified pilot runtime/model/native-template identities. It reconstructs every
reviewed model context and creates exact wire bytes and sidecars. Ordering is final
dataset-list position, then existing model order, then existing repetition order.
The schedule has `N × len(MODELS) × len(SEEDS) = N × 9` distinct logical slots even
when response bytes or contexts repeat. `schedule_seed=0` is a required SQL field
sentinel; this schedule uses no random shuffle. Generation seeds are unchanged.

Native template/tokenizer evidence cannot be guessed offline or inherited from
different pilot requests. `main_v2_context` is a **separate, explicitly invoked**
render/tokenize-only step using the qualified v2 procedure. It restores only the
archived v2 metadata namespace without overwriting existing bytes, verifies current
runtime identity with `freeze.verify_live`, and retains exact render/tokenizer
requests, replies and per-run measurements. It requests `_debug_render_only=true`
and `truncate=false`, never a completion. Native evidence is stored separately
from the immutable qualification; see the current verification record.
Runtime drift requires separate qualification; do not edit historical bindings.

`materialize` consumes the final release, deterministic requests, complete measured
context package and a separate human plan authorization. The authorization binds
the database, dataset ID, release root, request plan and context manifest. Only
then is `plan_authorized` set true and `execution_authorized` set **false**.
This authorizes persistence only. Status and a real dry-run work in this state;
dispatch and even direct attempt reservation refuse it. No approval is inferred
from a successful technical check. The command archives all evidence, binds P2,
D07, output interface, runtime/models, context proofs and source closure, then
persists one experiment and the complete schedule. It checks reconstructed SQL
requests through the existing batch adapter before commit. It makes **zero model
calls, zero attempts, zero predictions and zero retries**. No migration, alternate
executor, parser or generation configuration was added.

Importing the identical dataset is idempotent. Experiment materialization is
explicitly duplicate-protected under the same dataset lock. A repeat is rejected;
inspect the existing experiment instead. An interrupted receipt write does not
justify another experiment. Use `inspect experiments` to recover the persisted ID.
Existing model rows with the same digest are verified and reused; separate v2
native metadata remain bound in the immutable setup rather than replacing v1 rows.

## Exact post-review commands

Run from a reviewed, tested checkout containing both the CLI and materializer.
For the already frozen dataset, skip section A; never refreeze or reimport to
change membership. Use the existing `dataset-import.json` (dataset ID 3).
Use the existing application credentials for the later authorized scientific
import and run. The test credentials used in implementation are disposable and
are not an operator credential. The database must already have the verified schema.
The commands below do not initialize/migrate a database.

Set explicit paths once. If review produced a new candidate version, change `C`
to that version before any command. `REVIEW` contains the three completed **human**
working copies. Nothing copies `APPROVED` into them.

```sh
T=/Users/aerfurt/University/Bachelor/rest_api_checker
R=/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker
C="$R/08_evaluation_v2/final_dataset_candidate_c_v1"
REVIEW="$HOME/.local/share/rest-api-checker/reviews/final-dataset-v2"
HANDOFF="$HOME/.local/state/rest-api-checker/main-v2"
RAC_PY="$T/.venv/bin/python"
RAC_ENV="$HOME/.config/rest-api-checker/application-credentials.env"
RAC_DB=rest_api_checker
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/openssl@3/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
mkdir -p "$HANDOFF"
cd "$T"
```

### A. Integrity, human freeze decision, final dataset

After all case/family/dataset reviews are complete:

```sh
"$RAC_PY" -m rest_api_checker.main_v2 integrity \
  --archive "$C" --review-dir "$REVIEW" --output "$HANDOFF/integrity.json"
"$RAC_PY" -m rest_api_checker.main_v2 freeze-template \
  --archive "$C" --review-dir "$REVIEW" --integrity "$HANDOFF/integrity.json" \
  --version 2.0 --output "$HANDOFF/freeze-authorization.json"
```

The template is `PENDING`. The author must inspect its hashes, ordered IDs,
denominators and coverage decision, then supply `author`, offset-qualified
`accepted_at`, and the explicit decision `FREEZE_FINAL_EVALUATION_DATASET_V2`.
That decision is human input; no command in this handoff grants it.

```sh
"$RAC_PY" -m rest_api_checker.main_v2 freeze \
  --archive "$C" --review-dir "$REVIEW" --integrity "$HANDOFF/integrity.json" \
  --approval "$HANDOFF/freeze-authorization.json" --version 2.0 \
  --output "$HANDOFF/final-dataset"
"$RAC_PY" -m rest_api_checker.main_v2 import-dataset \
  --release "$HANDOFF/final-dataset" --env-file "$RAC_ENV" --database "$RAC_DB" \
  --output "$HANDOFF/dataset-import.json"
DATASET_ID=$("$RAC_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["dataset_id"])' "$HANDOFF/dataset-import.json")
```

### B. Exact requests, native context, plan-only authorization

Offline request preparation:

```sh
PREP="$HANDOFF/technical-preparation-ollama-0.35.1-20261003"
QUAL="$HANDOFF/evaluation_v2_main_runtime_ollama_0.35.1_20261003"
DATASET_ID=3
mkdir -p "$PREP"
"$RAC_PY" -m rest_api_checker.main_v2 prepare \
  --release "$HANDOFF/final-dataset" --output "$PREP/prepared" \
  --runtime-qualification "$QUAL" \
  --runtime-manifest-sha256 a3431bc7ac6cfdf54e04458dc0354469490ca70f9e7bb60955e7080d074b6ee8 \
  --runtime-receipt-sha256 3bd209477cc26a3b7a30f8881ca4fc2155ab5f3adfb696a0997470cb026f6074
```

The following is a later live **native render/tokenize-only** action, after
authorization for that preparation. It does not dispatch Main or generate answers.
It verifies the currently installed runtime against the archived v2 qualification.
It can load models for native rendering and may take time. Keep its new output
directory on durable storage; a failed measurement retains raw evidence and never
silently retries. Do not run it while the prohibition on real model access remains.

```sh
"$RAC_PY" -m rest_api_checker.main_v2_context \
  --release "$HANDOFF/final-dataset" --prepared "$PREP/prepared" \
  --output "$PREP/context" --root "$T" --confirm-native-render-tokenize-only
"$RAC_PY" -m rest_api_checker.main_v2 plan-template \
  --release "$HANDOFF/final-dataset" --prepared "$PREP/prepared" \
  --context "$PREP/context" --dataset-id "$DATASET_ID" --database "$RAC_DB" \
  --output "$PREP/plan-authorization.json"
```

The named author must inspect the bound plan/context/runtime, supply `author` and
offset-qualified `accepted_at`, and change the pending decision to
`AUTHORIZE_MAIN_V2_PLAN`. Leave every binding and the explicit zero-inference
scope unchanged. This decision authorizes zero attempts and predictions.
Do not run these preparation commands again if their immutable outputs already
exist; inspect the retained receipts. After the human supplies plan approval:

```sh
"$RAC_PY" -m rest_api_checker.main_v2 materialize \
  --release "$HANDOFF/final-dataset" --prepared "$PREP/prepared" \
  --context "$PREP/context" --authorization "$PREP/plan-authorization.json" \
  --dataset-id "$DATASET_ID" --env-file "$RAC_ENV" --database "$RAC_DB" \
  --output "$PREP/experiment.json"
EXPERIMENT_ID=$("$RAC_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["experiment_id"])' "$PREP/experiment.json")
```

### C. Status and real dry-run

```sh
"$T/.venv/bin/rest-api-checker" --root "$T" --env-file "$RAC_ENV" --database "$RAC_DB" \
  experiment batch-status "$EXPERIMENT_ID" --dataset-id "$DATASET_ID" --plain
"$T/.venv/bin/rest-api-checker" --root "$T" --env-file "$RAC_ENV" --database "$RAC_DB" \
  experiment run-batch "$EXPERIMENT_ID" --dataset-id "$DATASET_ID" --dry-run --plain
```

Require the **real persisted** dataset/experiment IDs, final case count, three
model identities, three repetitions/seeds 101/202/303, `N × 9` planned runs, frozen
P2 hash, `format_json`, `num_predict=512`, qualified Ollama v2 runtime/setup and
**zero problematic runs**. A dry-run performs SQL and Ollama metadata checks,
not generation; it writes zero predictions. It does not itself approve execution.
Expect `Execution authorization: NOT GRANTED`. The JSON form retains complete
hashes: replace `--plain` with `--json` and redirect
to a new receipt file. The wrapper below checks these fields explicitly.

### D. Separate execution authorization — later human decision only

After reviewing the real dry-run, generate a pending decision over its exact
persisted setup. The command runs full metadata-only preflight and writes no SQL:

```sh
"$RAC_PY" -m rest_api_checker.main_v2 execution-template \
  --env-file "$RAC_ENV" --database "$RAC_DB" --dataset-id "$DATASET_ID" \
  --experiment-id "$EXPERIMENT_ID" --root "$T" \
  --output "$PREP/execution-authorization.json"
```

The human compares `plan_setup_sha256` with the inspected dry-run's
`plan.setup_sha256`, verifies the database, dataset and experiment IDs, and then
supplies `author`, offset-qualified `accepted_at`, and
`decision=AUTHORIZE_MAIN_V2_EXECUTION`. No command fills those fields. Only later:

The existing application role intentionally cannot update `setup_file_id`.
This one metadata administration command therefore requires a separately supplied
database-owner credential file (`RAC_AUTH_ENV` below), with permission to archive
files and update that column. Use the normal application credential for all
other commands. No permission grant or schema migration is performed by the patch;
no owner credential is created or inferred. The command checks this permission
before proceeding and never requests model output.

```sh
"$RAC_PY" -m rest_api_checker.main_v2 authorize-execution \
  --env-file "$RAC_AUTH_ENV" --database "$RAC_DB" --dataset-id "$DATASET_ID" \
  --experiment-id "$EXPERIMENT_ID" --root "$T" \
  --authorization "$PREP/execution-authorization.json" \
  --output "$PREP/execution-authorization-receipt.json"
```

This archives the exact human decision and creates a new setup referencing the
original plan bytes; it changes only the execution gate. No schema migration is
needed. The experiment points to the derived setup. Dispatch verifies that all
other setup content equals the approved original, checks relational bindings and
run ordering, and rechecks before each attempt. Pending decisions, bare booleans,
changed plans and approval for another database/experiment fail closed. The
original plan remains archived. Authorization itself makes zero model calls.

### E. Main launch — only after section D is explicitly completed

Direct foreground command (do not also start the wrapper):

```sh
"$T/.venv/bin/rest-api-checker" --root "$T" --env-file "$RAC_ENV" --database "$RAC_DB" \
  experiment run-batch "$EXPERIMENT_ID" --dataset-id "$DATASET_ID" \
  --spool "$HANDOFF/run/spool" --yes --plain
```

Recommended unattended macOS form, on AC power with the lid open:

```sh
mkdir -p "$HANDOFF/run"
nohup /bin/bash "$T/tools/main_v2/launch.sh" "$RAC_ENV" "$RAC_DB" \
  "$DATASET_ID" "$EXPERIMENT_ID" "$HANDOFF/run" \
  >> "$HANDOFF/run/launcher.log" 2>&1 < /dev/null &
```

The wrapper checks durable storage and a default **5 GiB operational reserve**
(`MAIN_V2_MIN_FREE_KIB` can explicitly increase it), SQL/status and real metadata
preflight. This is a minimum reserve, not a worst-case output-size guarantee.
It records the resolved plan before dispatch and uses `caffeinate -i -s` only for
the lifetime of the single Main command. It never changes macOS power settings.
The process receipt, stderr logs, before/after status and exit code live under
`$HANDOFF/run/launch-<UTC>-<PID>/`; canonical recovery spools live in
`$HANDOFF/run/spool`. An empty final receipt after a crash is not evidence of zero
dispatches: inspect SQL attempts and the spool. No retry loop exists.

When returning from the gym (re-establish variables/IDs from receipts if needed):

```sh
"$T/.venv/bin/rest-api-checker" --root "$T" --env-file "$RAC_ENV" --database "$RAC_DB" \
  experiment batch-status "$EXPERIMENT_ID" --dataset-id "$DATASET_ID" --plain
```

Only after reviewing an interruption, an explicit `--resume` may be appended to
the wrapper. It preserves terminal runs and refuses ambiguous reserved work.
Do not restart with another experiment, remove a spool, or authorize retries to
make a blocked run continue.

## Local branch integration

No merge or push is performed by this handoff. Both technical branches are kept.
From a clean working tree, review the local graph and these diffs before integrating:

```sh
git status --short --branch
git log --oneline --graph --decorate main..feat/main-v2-materializer
git diff --check main...feat/main-v2-materializer
git switch main
git merge --no-ff --no-commit feat/evaluation-v2-cli-runner
git diff --cached --check
git diff --cached --stat
# Inspect staged diff, then:
git commit -m "Merge Evaluation-v2 batch CLI"
git merge --no-ff --no-commit feat/main-v2-materializer
git diff --cached --check
git diff --cached --stat
# Inspect staged diff, then:
git commit -m "Merge Main-v2 technical handoff"
```

If the tree or graph differs, inspect it first; do not reset, squash or rebase.
No command here pushes or merges remotely.
