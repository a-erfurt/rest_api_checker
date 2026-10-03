# Evaluation-v2 batch operation

`rest-api-checker experiment run-batch` is an operational adapter over the
existing sequential attempt executor. It does not select or materialize a
dataset, produce references, qualify a runtime, grant scientific authorization,
or calculate metrics. No v1 freeze, request, parser, SQL schema or retry rule is
changed. `rac` and the historical experiment commands remain available.

## Commands

```sh
rest-api-checker --env-file /private/path/credentials.env --database rest_api_checker \
  experiment run-batch <EXPERIMENT_ID> --dataset-id <FINAL_DATASET_ID> --dry-run

rest-api-checker --env-file /private/path/credentials.env --database rest_api_checker \
  experiment run-batch <EXPERIMENT_ID> --dataset-id <FINAL_DATASET_ID> \
  --spool /private/path/main-v2-spool --yes

rest-api-checker --env-file /private/path/credentials.env --database rest_api_checker \
  experiment run-batch <EXPERIMENT_ID> --dataset-id <FINAL_DATASET_ID> \
  --spool /private/path/main-v2-spool --resume --yes

rest-api-checker --env-file /private/path/credentials.env --database rest_api_checker \
  experiment batch-status <EXPERIMENT_ID> --dataset-id <FINAL_DATASET_ID>

rest-api-checker experiment demo-batch
```

Global options also work after the leaf command: `--plain`, `--json`, `--root`,
`--env-file`, `--database`. The database ID resolves its exact stored name/version;
there is no latest-dataset selection. The experiment ID selects the canonical
persisted schedule and complete configuration. No model, seed, token or output
mode override is offered. Main's selected `format_json` mode must be supplied
by the separate materialization; the adapter displays the actual explicit mode
and never substitutes it. All three existing v2 modes retain their semantics.

`--dry-run` performs the complete real SQL/request/context/runtime preflight,
prints the plan and stops with zero model calls and zero prediction writes.
It does not create spool directories. Metadata-only Ollama version/tags/show
checks are required, including in dry-run. There is no model download/load probe.

Execution asks one default-no confirmation on an interactive input. Scripts and
JSON execution require `--yes`; `--yes` and `--dry-run` are mutually exclusive.
After confirmation, preflight is repeated under the existing SQL session dispatch
lock, and changes to the confirmed plan block execution. Recovery storage is
tested before any model call. No migration or database initialization occurs.

## Materialization contract and current integration limit

**Dataset membership alone is insufficient.** This repository's existing Main
materializer is v1-only. This task intentionally does not generalize that frozen
scientific release adapter. Before real Main-v2 use, the separate release step
must materialize the dataset, final reference bindings, one evaluation experiment,
its runs, and an immutable SQL setup satisfying the following technical contract:

- `format: main-evaluation-setup-v2`, explicit `dataset_id`, `schedule_seed`,
  `schedule`, `files` source closure, and existing `inspection.bindings` projection.
- Existing release/runtime gate fields `execution_authorized: true` and
  `gate_b_complete: true`, set only by the separate authorized release step.
  This CLI neither sets these flags nor reuses v1 author acceptance.
- `output_interface`: constructor fields for `OutputInterfaceV2`, with explicit
  `mode` (and optional existing `version`); no new generation configuration.
- Existing `parser_sha256`, `renderer_sha256`, and v2 `request_builder_sha256`.
- `runtime` and ordered `models` in the existing `freeze.verify_live` format,
  including qualified native metadata paths and template hashes. Restoring the
  pilot's archived native metadata namespace, if needed, belongs to preparation.
- `context_proofs` keyed by string `run_order`, using existing `ContextProof`.
- `request_inventory` in frozen run order: each item has `run_order`, exact wire
  `sha256`, and the builder's v2 `request_identity_sha256`. These are metadata
  bindings, not extra model inputs.

The plan must contain every member × configured model × configured repetition
exactly once, with one P2 identity and one generation configuration per model.
Model roster, D07, seeds, token budget and prompt hash come from the existing
authorities. The CLI follows persisted `run_order` (contiguous 1..N), irrespective
of database row order; it does not choose a new scientific schedule. Arbitrary
eligible dataset sizes are supported. No final dataset name, size, API ratio or
reference distribution is embedded here.

Preflight verifies schema through `Repository`, dataset/reference/case relations,
source closure, frozen relational bindings, P2, D07, complete schedule, every
v2 request identity, exact context proof, template binding, and current runtime
and model identities through the existing verifier. It does not recompute a
reference. Missing evidence blocks before the first attempt.

## Continuation, failure and interruption

The canonical identity is an existing experiment/run bound to its immutable
setup, membership, model, prompt, configuration, repetition and seed. A restart
must use the same experiment ID. By default any completed runs require explicit
`--resume`. Resume skips both valid and parser-failure terminal runs and preserves
their bytes. Terminal attempt/request/prediction consistency is checked first.

Any pending run with an attempt or reserved request blocks the entire
continuation, including an old retry-eligible attempt. The plan lists problematic
run IDs, remaining runs and missing unattempted runs. When problems exist, zero
runs can execute now. Multiple experiments on the selected dataset also block:
the adapter refuses to infer equivalence across experiments or create duplicates.
There is no force/overwrite option or response-equality heuristic.

Parser failure is the canonical strict parser result, is persisted normally, and
does not abort. Technical/provider ambiguity is passed through the existing
receipt/spool path with conservative `ambiguous` attribution, stopping the batch.
No automatic retry or parser repair is added. An unsettled technical problem is
reported separately from persisted terminal `technical_failure`; it is never
turned into a parser failure or a fabricated terminal database result.

Use `inspect attempts <RUN_ID>` and the durable spool to investigate. Evidence-only
reconciliation remains the existing Python API; the historical CLI reconciliation
command is fabricated-only. This adapter intentionally does not add a technical
failure attribution/authorization policy. Some failures therefore need separately
reviewed recovery before any continuation is safe.

The existing cooperative SIGINT behavior lets the active bounded attempt settle
where possible, then stops scheduling and exits 130. A hard kill or lost database
connection can leave ambiguous reserved work; exactly-once external generation
is not claimed. Errors that prevent a final SQL read yield unknown counts, not
invented completion. Exit 0 means operational completion (parser failures allowed),
3 means blocked/technical failure, and argparse usage errors return 2.

## Progress, summary and JSON receipt

One restrained Rich display shows completion/percentage, case/API/model,
repetition/seed, elapsed/current time, estimated ETA and canonical counters.
TTY refresh is 2 Hz; plain/redirected/NO_COLOR output emits current-run and
completion lines without cursor animation. Full prompts/responses are not printed.
ETA and average elapsed time include orchestration overhead and are estimates.

The final summary includes dataset, counts, previously complete, executions now,
outcome deltas, unsettled technical problems, timing, mode, runtime and prompt/setup
identity. `executed_now` counts persisted dispatch-start boundaries observed for
this invocation; it is not a claim that every dispatched generation completed.
`scheduled_now` and `settled_now` distinguish scheduling from safe settlement.
Human-readable SHA-256 fields show labelled 16-character prefixes; the JSON
receipt retains the complete hashes and model identities.

`--json` emits one operational receipt on stdout with the same data plus start/end
timestamps, repository commit and interruption state. Redirect it to an external
new file if desired; the database and spool remain canonical. JSON mode has no
progress output. Preflight failures emit a structured blocked error. Status is
read-only, does not contact Ollama, and reports model/repetition breakdowns without
accuracy or other scientific metrics.

## Presentation-only simulation

`experiment demo-batch [--delay 0.5] [--plain|--json]` runs 27 deterministic
synthetic steps in approximately 13.5 seconds by default. It shares the plan
structure, display and summary with the real adapter. Delay is 0–2 seconds per
step. No database settings are needed; no database connection, executor, parser,
runtime or scientific writer is used. Execution options such as `--yes`,
`--resume`, `--spool` and `--dry-run` are rejected on this command.

The header and final summary label simulation, zero model calls and zero prediction
writes. Simulated parser counters are operational presentation events, never
experimental evidence, reference labels or model performance. This differs from
the older `experiment demo`, which creates disposable SQL resources.

## Verification (2026-10-03)

The unchanged baseline passed 883 tests with 97 SQL-related skips. The final
ordinary suite passed **928 tests, 99 skipped, zero failures**. New coverage is
45 non-SQL tests plus two opt-in SQL tests exercising real attempt/spool/persistence
with fabricated transport. No `RAC_SQL_TEST_ENV` was configured, so the two new
SQL tests were not executed. Existing golden v1 request hashes, P2 bytes, strict
parser tests, all three v2 output modes, settings/seeds, and Q01–Q26 remain green.
All 134 protected source/qualification/contract hashes recorded before editing
are unchanged; scientific execution, transport and persistence source files have
no diff.

Manual verification used the actual CLI demo in plain and live TTY modes and a
dry-run invocation with isolated fabricated repository/runtime boundaries. The
dry-run returned 0, resolved nine planned executions, and left all fixture rows
and files identical. These checks establish CLI behavior, not real SQL/runtime
readiness. No live model, final Main run or scientific database write occurred.
