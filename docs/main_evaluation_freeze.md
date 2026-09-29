# Main evaluation freeze adapter

Research authority: `04_case_studies/main_experiment_freeze_v1/authorization.json`,
`metrics_policy.md`, the exact final dataset root, and the approved prompt/runtime
freeze. Preparation is not execution authorization.

`main_freeze.Release` verifies the frozen source inventory and accepted reference
pointers without invoking the Reference Oracle. Historical tracked technical
sources are read from the dataset-bound commit; ignored artifact bytes retain
strict hash verification. All 553 root/payload/source descriptors are archived as
original bytes. The projection keeps each complete release case, manual decision,
reference rationale and ancestry metadata. The SQL schema maps provenance tokens
mechanically. Six contract-derived bases and one source observation are unscored
ancestor records, never additional dataset members or inferred reference results.
SQL reference revision 1 identifies the adapter revision; original revision/source
pointers remain preserved. No acquisition timestamp is invented.

`import_release` is transactional and idempotent for the same release. Changed
bytes under its identity fail. `plan_main` only accepts the approved evaluation
identity, P2, D07, seed/order rules and complete source-bound reference set. It
creates 126 logical slots with no attempts or timestamps and rejects conflicting
Main experiments. The existing development planner stays unchanged.

`main_execution.run_accepted` is a separately gated future entrypoint over the
qualified sequential runner. It requires decision `AUTHOR_AUTHORIZED_126_MAIN_RUNS`,
exact `freeze_root`, matching `experiment_id`, named `author`, and an explicit
`authorized_at` timestamp. It verifies every package file, current clean technical
commit/source closure, persisted setup and live model/runtime identities. It
compares each regenerated request byte for byte. No such acceptance is created
by preparation. The default historical CLI paths do not acquire this authorization.

Ambiguous/systematic failures block; technical reconciliation uses the existing
spool-bound review mechanism. Only an explicitly attributed isolated failure can
qualify for the one identical retry. Parser failures remain terminal. No automatic
HTTP retry, repaired output, retuning or evaluator invocation is added.

Validation uses disposable SQL databases and fabricated provider outcomes only.
The final research freeze contains concrete source hashes, DB row/byte readback,
request/context verification and test receipts. Its runbook is the operator entry.
