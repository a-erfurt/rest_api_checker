# Main-v2 technical handoff

This is an operator procedure, **not an execution or scientific approval**.
No real dataset, experiment or native Main context measurement was created during
implementation. Human decisions are inputs. The current candidate remains pending.
Research, v1 evidence, service sources and the Thesis are read only.

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
and `truncate=false`, never a completion. No such live step was run in this task.
Runtime drift requires separate qualification; do not edit historical bindings.

`materialize` consumes the final release, deterministic requests, complete measured
context package and a separate human plan authorization. The authorization binds
the database, dataset ID, release root, request plan and context manifest. Only
then are the existing setup gates set true. This authorizes the persisted plan;
launch still requires the separate deliberate Main command. No approval is inferred
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

### B. Exact requests, native context, authorized experiment

Offline request preparation:

```sh
"$RAC_PY" -m rest_api_checker.main_v2 prepare \
  --release "$HANDOFF/final-dataset" --output "$HANDOFF/prepared"
```

The following is a later live **native render/tokenize-only** action, after
authorization for that preparation. It does not dispatch Main or generate answers.
It verifies the currently installed runtime against the archived v2 qualification.
It can load models for native rendering and may take time. Keep its new output
directory on durable storage; a failed measurement retains raw evidence and never
silently retries. Do not run it while the prohibition on real model access remains.

```sh
"$RAC_PY" -m rest_api_checker.main_v2_context \
  --release "$HANDOFF/final-dataset" --prepared "$HANDOFF/prepared" \
  --output "$HANDOFF/context" --root "$T" --confirm-native-render-tokenize-only
"$RAC_PY" -m rest_api_checker.main_v2 plan-template \
  --release "$HANDOFF/final-dataset" --prepared "$HANDOFF/prepared" \
  --context "$HANDOFF/context" --dataset-id "$DATASET_ID" --database "$RAC_DB" \
  --output "$HANDOFF/plan-authorization.json"
```

The named author must inspect the bound plan/context/runtime, supply `author` and
offset-qualified `accepted_at`, and change the pending decision to
`AUTHORIZE_MAIN_V2_PLAN`. This is distinct from approving case references. Then:

```sh
"$RAC_PY" -m rest_api_checker.main_v2 materialize \
  --release "$HANDOFF/final-dataset" --prepared "$HANDOFF/prepared" \
  --context "$HANDOFF/context" --authorization "$HANDOFF/plan-authorization.json" \
  --dataset-id "$DATASET_ID" --env-file "$RAC_ENV" --database "$RAC_DB" \
  --output "$HANDOFF/experiment.json"
EXPERIMENT_ID=$("$RAC_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["experiment_id"])' "$HANDOFF/experiment.json")
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
The JSON form retains complete hashes: replace `--plain` with `--json` and redirect
to a new receipt file. The wrapper below checks these fields explicitly.

### D. Main launch — only after explicit Main authorization

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
