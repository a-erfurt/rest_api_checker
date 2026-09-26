# Persistence verification — 2026-09-26

**Result: PASS for this schema/persistence stage.** Full technical verification:
**300 passed in 23.21 seconds**, zero failures/skips. This includes 34 actual SQL
Server integration tests, 9 local persistence boundary tests, the existing 253
scientific regression tests (Q01–Q26 remain green), and 4 environment-probe
converter tests. [JUnit evidence](persistence_evidence/full_suite.xml) contains
individual tests and observed timestamps. The task date follows the supplied
Europe/Berlin project date; machine-recorded times in evidence remain unchanged.

No Ollama communication, metadata inspection, model loading/inference, provider
call, scored comparison/sensitivity run, Main Experiment or final evaluation
occurred. Lifecycle tests use explicitly fabricated requests, responses, model
metadata and parsed verdicts. DEV import tests forbid calls to the Oracle,
construction and materializer via failure sentinels. The existing scientific
regression suite runs independently and does not remeasure or alter released
staging through the importer.

The public CLI was also exercised independently: create disposable database,
empty migration, safe second apply, version inspection, DEV import/re-import,
prompt import/re-import, zero experiment/run/output inventory, then guarded
cleanup. [CLI evidence](persistence_evidence/cli_import.json) records the exact
ordered relational DEV projection and prompt hashes. A wheel build succeeded
and includes both numbered SQL files and all persistence modules.
The [final inventory](persistence_evidence/final_inventory.json) confirms all
disposable databases were removed, the two original probe databases remain,
the DEV manifest is unchanged, and no private credential appears in staged files.

## Actual engine and database checks

Reused the qualified SQL Server 2022 Developer CU27 container/digest on Docker
Desktop, localhost-only port 14339, named persistent volume and native
Python 3.12.14/pyodbc 5.3.0/ODBC Driver 18. No Docker/emulation configuration changed.
All integration databases use unique `rac_test_<uuid>` names and a disposable
extended-property marker. Their cleanup leaves the historical qualification
probe databases intact. No persistent study database was created or populated.

Migration 001 creates all 18 domain tables, the 34 explicit NO ACTION FKs, reviewed
unique/index keys, checks and immutable-file trigger. Migration 002 creates the
restricted application role. The ledger is the only additional table. Empty
migration and identical second application pass; wrong version, modified
checksum, concurrent application, lock contention and injected partial migration
failure behave as specified. An injected THROW after DDL leaves neither the
partial table nor an advanced ledger. Runtime connection checks never migrate.

The application backup was copied to the host, independently copied back under a
new server filename, checksum verified and restored without REPLACE to a separate
marked database. All 19 tables matched exactly, including binary content, large
Unicode reasons, offset/100-ns timestamps, foreign-key values and migration
ledger. [Backup/restore evidence](persistence_evidence/backup_restore.json) records
the database names, retained host/server paths, hashes and byte count. The backup
contains 12 DEV cases, 3 approved prompts and **one explicitly fabricated
persistence run**, zero study runs. Both application test databases were dropped
only after successful comparison. The external backup is retained privately.

The known Apple-Silicon unsupported-emulation and earlier exit-137 stop limitation
remain documented in the [qualification report](sqlserver_environment_check_2026-09-26.md).
The author accepted this local implementation environment. This task observed no
new instability, persistence corruption or restore failure. The reused container
is left running; the prior graceful-stop limitation is not silently marked fixed.

The original qualified environment's four fixture rows were read again after
schema work: all byte/Unicode/Decimal/timestamp/relationship checks still pass.
See [post-schema environment evidence](persistence_evidence/qualified_environment_after_schema.json).

## Released source verification

- Manifest SHA-256:
  `8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974`.
- Exactly DEV-01–DEV-12, original ordering, 6 EDX / 6 HTTS, families EDX-P02,
  HTTS-H01 and HTTS-H05, origins 3 natural / 2 synthetic conformant / 7 synthetic
  inconsistent. Stored source labels remain 4 consistent / 8 inconsistent;
  this is projection verification, not a new Oracle measurement.
- Complete case and Oracle source objects round-trip through the original
  manifest/pointers. Branch/media/schema/ordered diagnostics, nulls, empty strings,
  versions, original pending-review flags and separate current approval survive.
- Parent relationships and byte splices match archived parent/child evidence.
  DEV-02 retains its nonconformant context parent and NULL transformation family;
  body-file, response.json-file and response-v1 envelope digests remain distinct.
- Identical second import returns identical IDs/receipt and adds no rows. Changed
  bytes/native identity, missing closure dependencies and wrong pointers fail.
  Source timestamps preserve natural request/acquisition UTC seconds; generated
  rows have NULL observed_at and date-only approval stays in original bytes.
- P1/P2/P3 byte lengths and hashes match the existing approved artifacts:

| Prompt | Bytes | SHA-256 |
|---|---:|---|
| P1 | 4325 | `f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6` |
| P2 | 4996 | `50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f` |
| P3 | 5835 | `5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb` |

## Discovered implementation defects and correction

1. Initial disposable cleanup encountered an in-use database because ODBC pooling
   retained the supposedly closed connection. Disabling pooling made explicit
   connection lifetime and safe, non-forced cleanup work. This was a client
   lifetime defect, not server instability. Credential-setting repr is redacted
   so a future test traceback cannot print private values.
2. A direct prediction INSERT accepted padded `NOT_APPLICABLE ` in VARCHAR(14):
   SQL Server discarded excess trailing blanks before the exact-length CHECK.
   The six verdict fields now use VARCHAR(15), preserving rejection headroom.
   Exact token lengths and the legal reference/prediction vectors are unchanged.
   Tests now isolate this boundary using predictions and verify padded tokens
   fail. This is the sole research-design engineering correction, recorded in
   `database_design_v1.md` §14. No scientific decision was changed.

Final tests have no unresolved failures. Controlled negative tests are expected
rejections, not failed acceptance or evidence of an unstable server.

## Acceptance matrix

PASS here is bounded to persistence behavior exercised with fabricated fixtures
or exact released source import. Where the design scenario includes another
stage, its remaining portion is explicitly DEFERRED. A persistence PASS does not
certify a future parser, renderer, orchestrator, evaluator or Gate B.

| ID | Persistence result | Deferred scope / evidence |
|---|---|---|
| DB01 | PASS | 18 tables, 34 FKs, PK/index/ledger inspection; empty DB apply. |
| DB02 | PASS | Reapply at expected version 2 is a no-op. |
| DB03 | PASS | Identical real source import creates no duplicate rows. |
| DB04 | PASS | Changed source bytes/native identity rejected. |
| DB05 | PASS | Invalid JSON/UTF-8, empty bytes and literal null preserved. |
| DB06 | PASS | Missing/empty Content-Type; absent versus empty provider/body evidence. |
| DB07 | PASS | Approved exact P1/P2/P3 hashes and lengths after retrieval. |
| DB08 | PASS | Reference/case composite FK rejects wrong pair. |
| DB09 | PASS | Both run/dataset composite relationships. |
| DB10 | PASS | Family/API agreement in case import and schedule projection validation. |
| DB11 | DEFERRED | Final lineage/renaming admission preflight; evaluation planning is currently blocked. |
| DB12 | PASS | Incomplete Oracle record rejected; missing membership reference blocks scheduling. |
| DB13 | PASS; parser DEFERRED | SQL/application exact token admission; strict model-output parser absent. |
| DB14 | PASS; scoring DEFERRED | All 27 legal prediction vectors admitted, including incoherent ones. |
| DB15 | DEFERRED | Strict parsing of duplicate keys, fences, missing fields; storage failure path tested separately. |
| DB16 | PASS | Duplicate run tuple/order rejected; whole invalid schedule rolls back. |
| DB17 | PASS | No retry after parser failure or valid output. |
| DB18 | PASS | Attempt 3 rejected by SQL and service. |
| DB19 | PASS | Technical failure then valid: two attempts, one prediction on attempt 2. |
| DB20 | PASS; classification DEFERRED | Supplied parser_failure on retry persists; parser itself absent. |
| DB21 | PASS; denominator DEFERRED | Two technical failures settle one run, no prediction; evaluator absent. |
| DB22 | PASS; rendering DEFERRED | Request file equality and write-once binding; semantic request renderer absent. |
| DB23 | PASS | Prediction/attempt/run composite FK rejects wrong run. |
| DB24 | PASS | Injected finalization failure rolls back files/result/prediction together. |
| DB25 | DEFERRED | Actual dispatch/outage orchestration; persistence spool/replay tested without provider. |
| DB26 | PASS; reporting DEFERRED | Completion blocked for pending schedule; full report-stage logic absent. |
| DB27–DB31 | DEFERRED | Evaluator denominator, stability, ranking and sensitivity pairing. |
| DB32 | PASS for persistence | New reference/report rows preserve original membership and old reports. |
| DB33 | PASS for application restore | Host-copy independent restore matches all tables; restart qualification is historical, no new restart claim. |
| DB34 | PASS | Path/method case, max-width key, UTF-16 bounds and INT overflow. |
| DB35–DB36 | DEFERRED | Renderer allowlist and HTML/UI escaping. |
| DB37 | PASS | Equal bytes retain distinct observation/case IDs; changed native case rejected. |
| DB38 | PASS | Three digests, DEV-02 provenance and parent distinction retained. |
| DB39 | PASS | Complete Oracle/source/release history round-trip. |
| DB40 | PASS | NULL draft reference admitted, scheduling blocked; used binding immutable through API. |
| DB41 | DEFERRED | Reference-only rescore engine/authority checks; append-only storage is present. |
| DB42 | DEFERRED | Full report-input bidirectional identity reconciliation; schedule completion check is present. |
| DB43 | PASS for persistence | Competing reservations/finalizations and exact lost-acknowledgement replay; provider ownership later. |
| DB44 | PASS | Late spool evidence advances diagnostics only; outcome/response stays unchanged. |
| DB45 | PASS | Native times/null/date-only preservation and explicit observed start. |
| DB46 | PASS; transport DEFERRED | Exact D07 storage/profile checks, false/NULL think, excess scale rejection; provider serialization absent. |
| DB47 | PASS; export preflight DEFERRED | Source hash/pointer/closure import and explicit closure export; full experiment export later. |
| DB48–DB49 | DEFERRED | Final-family admission and model-content/transport attribution. |
| DB50 | PASS | Checksum/version/partial rollback/exclusive/concurrent migration tests. |
| DB51 | DEFERRED | Sensitivity and undefined diagnostic metrics. |
| DB52 | PASS | Direct SQL token/NULL/numeric/composite/attempt constraints and all 27 predictions. |
| DB53 | DEFERRED | Full final-release/runtime/effective-config execution preflight. |
| DB54 | PASS for persistence | Binary/large Unicode/Decimal/time round-trip, exact export and host-copy restore. |
| DB55 | PASS for local persistence; dispatch DEFERRED | Fabricated fsync failure preserves unresolved state/available bytes; no retry inference. |

## Remaining boundary

No persistence blocker remains after the physical verdict-width correction.
Renderer and strict parser must still be implemented and source-bound. Later
orchestration needs full model/template/effective-option/context evidence, complete
Gate B setup validation and dispatch ownership. Evaluation needs exact analysis
input reconciliation, formulas, sensitivity pairing and reference-correction
validation. Final dataset admission, prompt freeze and study execution remain
separate authorized stages. Persistence tests do not approve any of them.
