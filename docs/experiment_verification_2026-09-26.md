# Experiment infrastructure verification — 2026-09-26

This report covers renderer, parser, provider boundary, deterministic schedule and
bounded orchestration only. Research policies D01–D11 remain unchanged. No research
edits were made by this stage; research HEAD is `050af6b214e167c737f09ee4c9a4d8dc3862981d`;
the technical baseline was `40eaf9fdd7f074f9f1c350c1ec4cef32de3ceb88`.

## Execution boundary

No Ollama endpoint was contacted, no model metadata was probed, no model was loaded,
and no real inference or study output was created. All provider replies, model
metadata, runtime attestations and context counts in integration tests are
explicitly FABRICATED. An autouse test fixture rejects real HTTP connections;
provider transport tests inject fabricated connection objects. The real-client
Gate-B test stops before reserving an attempt or opening a connection.

No persistent study database was created/populated. Full schedules and attempts
were exercised only in uniquely named, marked disposable SQL Server databases.
The committed schedule is explicitly `non_dispatched:true`. It is not a comparison
freeze or permission to execute. Sensitivity remains a future 108-run variant
budget. Evaluator, ranking, final dataset, UI and Main Experiment were not added.

## Artifacts and identity checks

- [Dry-run schedule](experiment_evidence/comparison_schedule_v1.json): exactly
  324 unique logical identities; 108 per prompt and model; 36 per model/prompt;
  each case/prompt/model has repetitions 1/2/3 with seeds 101/202/303; unique
  consecutive global order and the approved per-model blocks.
- Schedule SHA-256:
  `a2c797b3d92a1e167515ce3fd1c559a79d2efe0849e0968c0127e499b424c145`.
  Exact regeneration is checked against the committed bytes and this digest.
- [Artifact/source verification](experiment_evidence/artifact_verification.json)
  retains renderer/parser artifact hashes and each of the twelve source/input
  bindings, full transitive pointer closure and deterministic evidence hashes.
  The tests rederive and compare every record.
- DEV manifest remains
  `8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974`.
  The released importer rechecks all bound files/release records without running
  the Oracle or regenerating the dataset.
- Exact P1/P2/P3 hashes remain respectively
  `f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6`,
  `50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f`,
  `5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb`.
- SQL schema and both migration files, including
  `002_application_permissions.sql`, are unchanged. No research clarification or
  scientific decision was needed.

See [stage design](experiment_stage.md) for the exact renderer/transport format,
request fields, shuffle algorithm and failure/recovery contracts.

## Tests and acceptance coverage

**PASS: 443 tests in 54.59 seconds; zero failures, errors or skips.** This includes
124 new unit/boundary tests, 19 new SQL Server orchestration tests, and all 300
baseline tests. There are 53 SQL Server integration tests in total; Q01–Q26 remain
green. An offline wheel build passed and includes the new package and JSON schema.

The full-suite JUnit record is [full_suite.xml](experiment_evidence/full_suite.xml).
It includes the existing Oracle Q01–Q26 and construction/materialization tests,
all persistence tests and environment converter tests. SQL checks use the actual
qualified SQL Server 2022 CU27 container and ODBC Driver 18, with disposable
cleanup and the existing backup/independent restore check enabled. The previously
accepted emulation limitation remains; this is not new vendor-support evidence.
Machine timestamps in JUnit are retained as observed; the report date is the
supplied project date.

| Scenarios | Verified implementation behavior |
|---|---|
| DB15, DB17 | Malformed/duplicate/fenced/empty answers retained, parser_failure, no prediction or retry |
| DB19, DB20, DB21 | Isolated technical attempt 1 then valid/malformed/technical attempt 2; exact final run outcome |
| DB22 | Changed retry request bytes rejected; changed runtime identity blocks before dispatch |
| DB25 | Injected database/finalization outage pauses; durable spool reconciliation does not dispatch |
| DB35 | Explicit allowlist rejects domain dictionaries/extra fields; all twelve inputs exclude runner metadata |
| DB43 | Single orchestrator session claim; duplicate reservation blocked; lost reservation acknowledgement sends nothing; lost finalization acknowledgement replays idempotently |
| DB44 | Late answer retained as immutable evidence; original failed attempt and subsequent terminal result remain unchanged |
| DB46 | All 27 prompt/model/repetition request combinations have exact D07 values; Qwen false versus Gemma/Mistral omitted; baseline SQL precision tests remain |
| DB49 | Empty/thinking-only final content is parser_failure; missing field/unattributed envelope error pauses; transport failure remains distinct |
| DB55 | Injected fsync/storage failure retains available bytes and unresolved state; no invented provider retry |

Additional checks cover all 27 legal prediction vectors (including dependency-
incoherent ones), output schema, strict JSON grammar, key-order/whitespace behavior,
raw UTF-8/body round trips, missing Content-Type, transitive response and schema
references, all response branches, immutable prompt hashes, deterministic schedule,
context overflow, runtime identity drift, no automatic HTTP retries, partial HTTP
bytes and forbidden request extras. A separate SQL connection verifies zero active
user transactions during fabricated provider calls.

The first test pass exposed an ODBC transaction boundary that repository nesting
alone could not establish. The implementation now explicitly switches to
autocommit for provider I/O after recording start, then restores manual transactions.
A separate-server-session observation verifies the final behavior. Recovery testing
also verifies that a finalized spool replay does not append duplicate diagnostics.

## Deferred evidence

All listed scenarios pass at their implementation/mock boundary. Actual model-
option behavior, native templates/defaults, full installed manifest identities,
Q4_K_M evidence, real token/context measurements, runtime-specific crash/OOM
attribution and complete Gate-B acceptance remain deferred. The callback contracts
fail closed when that evidence is unavailable; fabricated test evidence cannot
admit real-client dispatch. No capability is inferred from accepting an option in
code. Storage-outage tests inject failures; physical power loss and the unavoidable
receipt-to-fsync loss window are not claimed solved. Evaluator/UI work and final
study authorization remain subsequent bounded stages.

## Final repository review

Both repositories matched the supplied clean baselines at the start. At final
verification an unrelated working-tree modification to research
`01_sources/literature/literature.bib` had appeared. This stage did not edit it and
left it untouched. Research HEAD and the approved methodology/prompt artifacts
remain unchanged. This is reported separately from this stage's technical diff.
The final [inventory](experiment_evidence/final_inventory.json) records database
cleanup, test totals, source hashes and the observed research working-tree status.
