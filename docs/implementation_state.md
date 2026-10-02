## 2026-10-02: bounded evaluation v2 interface pilot dispatch

The separate file-based `interface_pilot_v2_live` command dispatches the exact
18-request preparation for two explicit, released DEV cases, three Ollama models
and three interface modes, once each. It reuses the Ollama transport, strict
parser, live runtime binding verifier and exact-request context proof checks.
It retains raw responses and operational counts without SQL or semantic scoring.
Single-use preparation claims prevent redispatch; provider failures stop the
pilot and parser failures do not trigger retries or interface fallback.

No live pilot, Main-v2 execution, service capture, scientific selection or
historical evidence change is part of this implementation. Author-selected DEV
cases and verified runtime/context evidence remain required. See
[output-interface v2](output_interface_v2.md).

Verification: 41 new pilot tests and 347 relevant request/provider/parser/runtime
and Oracle tests passed. The ordinary suite passed 883 tests, with 97 SQL
integration tests skipped because `RAC_SQL_TEST_ENV` was not configured; zero
final failures/errors. All 854 local historical artifact files and 1,468
snapshotted research files remained byte-identical. No live model call occurred.

## 2026-10-01: evaluation v2 output-interface candidate

A separate v2 request DTO, builder and boundary validator support explicit
`prompt_only`, `format_json` and `json_schema` modes with the unchanged P2,
generation settings and strict parser. The dedicated transport schema permits
all 27 verdict vectors and supplies no semantic dependency or expected answer.
Version/mode, exact request bytes and hashes are bound in separate sidecars.
No database migration or historical v1 implementation/evidence change is needed.

An offline command prepares 18 requests for two explicitly selected released
DEV cases, three models and three modes, at 512 output tokens. No model call,
SQL planning, final v2 evaluation or interface selection has been executed by
this step. Live pilot execution remains separate. See
[output-interface v2](output_interface_v2.md).

Verification: 258 focused request/parser/interface tests passed; the ordinary
suite passed 842 tests with 97 SQL integration tests skipped because
`RAC_SQL_TEST_ENV` was not configured. No final test failure or model call occurred.

## 2026-10-01: evaluation v2 service response capture

One explicit-target CLI command now archives an input, the sent HTTP request
body and metadata, received response bytes and headers, and creates an
unlabelled response case bound to an existing OpenAPI contract operation.
EDX raw-body and Resistance raw-body/multipart validation paths are supported.
The existing `files`, `responses`, and `test_cases` tables suffice; there is no
schema migration or v1 experiment change. See [service capture](service_capture_v2.md).

The SQL round trip and two CLI captures were verified using a separate disposable
SQL Server instance on port 14341; the scientific database was not targeted,
and temporary databases, container and credentials were removed. EDX reproduced
EDX-PO-0001 locally with HTTP 200, `application/json; charset=utf-8`, and 118
body bytes identical to the archive. A Resistance temporary copy whose 15 tracked
files matched the source returned HTTP 200, `application/json`, and 80 body bytes
through multipart capture. Both captures passed 17 evidence checks; both
original service clones remained unchanged. Local results do not establish
current remote/deployment parity.

Execution alone inserted no SQL rows; materialization created two unlabelled
cases in the disposable database, without reference results, dataset membership,
predictions or evaluation reports. Reference assessment remains separate, with
OpenAPI as the only API-specific contract authority. Capture is at application
level, not raw network/wire level; target and execution origin are explicit.

Final verification: 781 passed, 24 skipped, zero failures/errors. The 23 separately
configured application-login checks and one backup/export check remain outside
the executed scope. Focused diff review and `git diff --check` passed; 1,026
checked historical evidence files remained byte-identical. No `edx_fail` or
`resistance_fail` variant, v2 LLM output-interface or Thickness work is implemented
in this branch.

## 2026-09-27: Main evaluation freeze preparation

The exact final evaluation release has a dedicated transactional SQL adapter in
`main_freeze.py`: immutable raw source archival, lossless metadata projection,
seven unscored ancestry records, fourteen accepted references and membership
positions, and idempotent planning of 126 logical runs. No schema migration,
parser, renderer, prompt, provider or retry semantics changed.

`main_execution.py` requires a separate author decision bound to the complete
Main freeze root and experiment ID. Frozen SQL retains the closed provider gate;
only the accepted execution path can enable an in-memory dispatch view. The Main
metrics specification (Option B, vector correctness /14 per model/repetition)
lives in the research freeze; no Main report/evaluator is run during preparation.

Validation: **795 passed, zero failures/skips**, including disposable SQL,
application-principal and backup/restore tests. See
[verification](main_evaluation_verification_2026-09-27.json).

See [Main freeze adapter](main_evaluation_freeze.md). Research source files and
existing comparison/sensitivity outcomes remain immutable. The historical
Sensitivity test fixture now binds its synthetic current research commit, and a
wrong-commit rejection remains tested; accepted historical artifacts are unchanged.

## 2026-09-27: pre-reference final candidate materializer

Added a standalone, offline adapter for the exact 14 author-confirmed candidate
recipes and seven accepted base bindings. It performs byte-preserving edits,
source/exclusion/group checks and emits no reference labels or dataset membership.
48 focused mechanical tests pass; Oracle-containing suites were not executed.
See [final_evaluation_candidates.md](final_evaluation_candidates.md). Actual
candidate artifact verification belongs to the separate research release record.
No Oracle, runtime, prompt, model, persistence or scientific recipe changed.

# Implementation State

Last updated: 2026-09-27

## Current milestone

Base-only serialization for the author-confirmed final construction plan is
available in `tools/final_evaluation_bases/prepare.py`. It pins the plan pair,
serializes only its six contract-derived bases, preserves explicit dependencies,
and emits no final candidates or reference fields. Research inputs are read-only;
output is prepared in a new staging directory for separately authorized research
artifact publication. See [base preparation](final_evaluation_bases.md).

Only the focused mechanical tests are executed in this step. The user's explicit
Oracle/network prohibition takes precedence over the usual full-suite rule;
Q01–Q26 and the full suite are not rerun. Existing Oracle/construction code and
scientific semantics are unchanged. No final case, reference review, dataset
freeze, experiment, database operation or push is authorized here.

### Previous sensitivity execution support milestone (historical)

P2 sensitivity execution support and the separate Section 9/D11 diagnostic
evaluator are implemented. See [the technical mapping and operator boundary](sensitivity_execution_d11.md).
The final candidate is generated after the implementation commit under
`artifacts/sensitivity_freeze_candidate_v2/`, retaining v1 unchanged. It requires
a separate exact-hash author acceptance before any real SQL experiment or
provider dispatch. No sensitivity experiment, prediction, acceptance, real
generation or main evaluation is created by this implementation step.

Full verification: **740 passed, zero failures/errors/skips**, including
disposable SQL, application-principal, backup/restore and Q01–Q26 checks.
See `sensitivity_verification_2026-09-26.json`. All real domain-table snapshots
and 782 protected file hashes match the recorded before-state.

The accepted comparison remains historical evidence. Historical source closure
is verified at its original bound Git commit; current execution still requires
exact current implementation/source/runtime bindings. SQL construction tests
use disposable application-principal databases, preserving completed Experiment 1.
Renderer, parser, prompt bytes, D07, seeds and the preliminary 108-slot schedule
remain unchanged. Native context measurements can be reused only after exact
request-byte and live runtime identity verification.

### Previous sensitivity preparation milestone (historical)

Candidate-only sensitivity preparation is available in `tools/sensitivity_freeze/prepare.py`.
It reconstructs 108 approved P2_SENSITIVITY_V1 requests against the accepted
comparison, measures native render/tokenizer context without completion calls,
and hashes all database rows before/after SELECT-only inspection. The order is
the P2 projection of the frozen comparison schedule, renumbered 1..108.
The prompt approval is research commit `a54ec11b33d90722a482464dcda9823fdc50cf90`.

The candidate remains NOT YET EXECUTABLE and needs exact-hash review. The existing
execution allowlist and evaluator only support comparison; sensitivity execution
and D11 paired evaluation adapters are unimplemented and explicit blockers.
No evaluation logic or runtime policy is changed. See `sensitivity_freeze.md`.

### Previous Gate-B preparation milestone (historical)

Final technical Gate-B closure is prepared on `chore/gate-b-closure-freeze`;
see the [closure report](gate_b_closure_2026-09-26/report.md). Dedicated application
login/user/role membership and separated local application/admin credentials are
provisioned without schema or scientific changes. Actual permission tests use
disposable databases. Three qualified model/configuration bindings are registered;
the real application database has zero experiments, runs, attempts, predictions
and reports.

Bounded failure attribution now validates protocol-bound measured evidence and
SQL qualification; genuine worker crash/OOM remains unobserved and requires an
explicit author limitation decision. The measured technical SQL preflight is
**10 PASS / 1 BLOCKED / 0 FAIL**; final suite **696 passed**, no failures/skips.
The final candidate verification receipt is beside the generated
candidate. Final Gate-B author acceptance remains blocked. The historical runtime
capture (Ollama 0.34.4, Q4_K_M, exact native-token context for all 324 identities)
is unchanged. No semantic generation was added.

The ignored `artifacts/gate_b_freeze_candidate_v1/candidate.json` is constructed
after committing its code/evidence so it can bind the exact execution commit.
It remains **NOT AUTHOR-ACCEPTED / DO NOT EXECUTE**. Its separate acceptance-gated
adapter validates live identities and pauses technical failures for spool-bound
review. No acceptance record, real schedule, prompt winner, sensitivity or main
evaluation was created. Frozen scientific inputs and research working-tree edits
were preserved.

### Previous runtime qualification milestone (historical)

The runtime evidence pass closed model identity, template/options and exact
context fit: **9 PASS / 2 BLOCKED / 0 FAIL**. Nine fabricated native-model
completions verified the seeds; no study generation. At that milestone the
application role had zero members and the operational credentials were admin.
See the [runtime report](runtime_qualification_2026-09-26/report.md).

### Previous operator-convenience milestone (historical)

The bounded operator-convenience layer is implemented: `rac`, local non-secret
defaults, known-container start/stop, existing web app launch, authoritative
preflight and small POSIX menus. The original CLI/web entry points and scientific
services are unchanged. See [operator guide](operator_convenience.md) and
[verification](operator_verification_2026-09-26.md).

Final suite: **637 passed**, zero failures/skips, including opt-in disposable SQL
integration/backup-restore and SQL probe tests. Live checks found schema 2 ready,
Gate B **6 PASS / 5 BLOCKED / 0 FAIL**, and HTTP 200 from the read-only web app.
PTY checks covered arrows, Enter, numeric shortcuts, Back, Exit and Ctrl-C in
plain and ANSI modes. Container mutations and browser opening were mock-tested.
The prepared application DB retains 12 cases, 12 references, 3 prompts and zero
experiments, runs, predictions or reports. No real inference or study execution;
no frozen artifacts, research files or scientific semantics changed.

### Previous read-only web milestone (historical)

Read-only FastAPI/Jinja2 research UI implemented on the authoritative evaluator
CLI baseline `aa4001de1e311011f1ea264cd68e3213e8889963`. Overview, Evaluation,
SQL-paginated Runs and dedicated evidence/Data detail pages consume persisted
records and reports. No evaluator formula, selection rule, database schema or
experiment protocol changed. See [web guide](web_ui.md) and
[verification](web_ui_verification_2026-09-26.md).

The web query layer issues SELECT statements only, rolls back request-owned
connections and never calls execution, model inference, preflight execution or
report creation. Incomplete experiments expose operational counts only; absent
reports/selection/readiness stay unavailable. Local HTMX polls every 3 seconds;
Chart.js displays stored metric values. Focus Mode, safe evidence viewers,
responsive tables and print styles are included.

Final verification: **579 passed**, including **71 SQL Server integration tests**,
zero failures/errors/skips. The focused web suite also passed (**87 tests**)
after the launcher environment-default review. Offline sdist/wheel packaging
and console help passed. Chrome visual review used fabricated records at 1120,
1440 and 2560-pixel widths, including Focus Mode and print preview.

**No real study inference, comparison, sensitivity or main evaluation was
executed. Frozen scientific inputs and the research repository were untouched.**
The current UI supports the existing comparison report format. Future sensitivity
or final-evaluation report formats require backend-defined presentation support.
Live model/Gate-B readiness cannot be inferred from the current persisted schema.

### Previous evaluation/CLI milestone (historical)

Comparison evaluator, immutable analysis snapshots/reports and the argparse/Rich
thesis CLI are implemented. See [CLI/evaluation design](evaluation_cli.md) and
[verification](evaluation_verification_2026-09-26.md). New experiment setups bind
exact relational source/reference/model/configuration values; old setups are not
rewritten. No database schema, frozen prompt, dataset or scientific policy changed.

The CLI supports database/dataset inventory, experiment/run/attempt inspection,
schedule/progress, comparison reports/JSON export, truthful offline Gate-B checks
and isolated fabricated execution. Cooperative interruption and persisted resume
retain pending/ambiguous runs. Actual runtime verification and attribution still
block real CLI execution. No web UI was added.

**The real 324 comparison runs have NOT started. No study prompt winner exists.
No sensitivity variant exists. Demo data is FABRICATED / TEST DATA.** Research
remains read-only; unrelated literature working-tree files are untouched.

Final verification: **478 passed**, including **61 SQL Server integration tests**,
zero failures/errors/skips; Q01–Q26 and backup/restore remain green. Both plain and
animated fabricated demos completed 324 logical runs with 326 attempts (322 valid,
1 parser failure, 1 terminal technical failure). All disposable resources were
removed. Offline package build and console-entry-point verification passed.
SQL-schema preflight: 6 verified PASS checks, 5 truthful Gate-B BLOCKED checks.

### Previous renderer/parser/orchestration milestone (historical)

Operation-scoped input renderer, strict final-output parser, Ollama client boundary,
deterministic comparison scheduling and persistence orchestration implemented.
See [stage design](experiment_stage.md) and
[verification](experiment_verification_2026-09-26.md). Frozen format versions and
artifact hashes are retained in `docs/experiment_evidence/` together with the
non-dispatched 324-run schedule and released-input round-trip records.

Exact P1/P2/P3 binding, reference-preserving closure, allowlist leakage prevention,
all 27 parser-valid vectors, D07 requests, context/runtime blocking, byte-identical
technical retries, recovery and SQL transaction boundaries are covered by focused
tests. All provider results and runtime/token evidence in tests are FABRICATED.
Final verification: **443 passed**, including **53 SQL Server integration tests**,
zero failures/skips; Q01–Q26 remain green. Wheel packaging also passed.
Only disposable SQL databases are used. No real model inference, study requests,
comparison execution, sensitivity or Main Experiment has occurred.

The approved research policies, prompt bytes, DEV manifest and Oracle semantics
remain unchanged. No persistence schema or migration changes were needed. This
stage made no research edits; research HEAD remains
`050af6b214e167c737f09ee4c9a4d8dc3862981d`. An unrelated working-tree change to
`01_sources/literature/literature.bib` appeared during the task and was left untouched.
Actual runtime/model/template/context evidence, evaluator implementation and Gate-B
acceptance remain outstanding; no study CLI or automatic batch dispatch exists.

### Previous persistence milestone (historical)

SQL Server schema/persistence implemented and verified on 2026-09-26 under the
author's explicit authorization and acceptance of the qualified local emulation
limitation. All 18 domain tables, 34 NO ACTION FKs, numbered checksum migrations,
transactional repositories, released DEV/prompt import, recovery spool and
disposable administration/backup helpers are present. The only physical design
correction is VARCHAR(15) verdict storage with unchanged exact-token checks;
SQL Server otherwise truncates a trailing blank at the old VARCHAR(14) boundary.
Research `database_design_v1.md` §14 records the correction separately.

Full verification: 300 tests passed, including 34 SQL Server integration tests,
9 local persistence boundary tests, the existing 253-test scientific suite
(including Q01–Q26) and 4 qualification converter tests. The released DEV importer
does not execute the Oracle or construction code. DEV-01–DEV-12 and approved
P1/P2/P3 round-trip exactly; re-import is idempotent. An application-schema backup
copied outside the container was independently restored and all 19 tables matched.
Only disposable databases and explicitly fabricated outcome fixtures were used.
No persistent study database, model output or study run was created.

See [`persistence.md`](persistence.md) and
[`persistence_verification_2026-09-26.md`](persistence_verification_2026-09-26.md)
for commands, evidence, passed/deferred acceptance coverage and remaining Gate B
work. No Ollama call, model inference, comparison, sensitivity or final evaluation
occurred. Stop at persistence; renderer/parser/orchestration remain separate work.
The qualified container is running with its named volume and external backups.
The historical exit-137 graceful-stop limitation remains documented; no new
instability, corruption or restore failure was observed.

### Previous environment milestone (historical)

Bounded SQL Server environment qualification and existing prompt-approval record
reconciliation completed; see
[`sqlserver_environment_check_2026-09-26.md`](sqlserver_environment_check_2026-09-26.md).
The seven requested local data/connection/restart/restore checks passed on the
pinned SQL Server 2022 CU27 Developer image with native arm64 Python/ODBC.
An initial timestamp text-conversion probe failure and its verified correction
are retained. Exact Docker emulator settings remain unverified; final container
stop reported exit 137 (not OOM), so graceful shutdown remains unqualified.
This is limited compatibility evidence, not acceptance of the unsupported
emulated deployment for study execution. The container is stopped; dedicated
volume and external backup remain. No domain schema or persistence layer exists.

Research O01 is resolved by recording the author's existing exact P1/P2/P3
approval after matching all supplied byte lengths/hashes. Original approval time
is unknown; the reconciliation recording date is 2026-09-26. Historical records,
prompt bytes and D01–D11 remain unchanged. Gate B/final prompt freeze are incomplete.
No study data import, Oracle/model execution or experiment occurred in this step.
Only the four focused probe converter tests and the documented SQL fixture checks
were run; the full Oracle-containing suite was intentionally not rerun.

Development dataset v1 materialization complete: exactly DEV-01–DEV-12.
Author approval recorded on 2026-09-22: DEV-01–DEV-12 manually reviewed (12/12)
and approved for prompt development. Current release status is
`AUTHOR_APPROVED_FOR_PROMPT_DEVELOPMENT`, recorded in
`docs/development_dataset_v1_release.json` and generated staging `release.json`.
The approved content manifest remains byte-identical:
`8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974`.
Its pending-review fields preserve the historical materialization state;
the separate hash-bound author-approval record supplies current release status.
Reference Oracle and validator qualification remain unchanged.

Baseline implementation commit:

`357941e60059400915cb79d34465bf9808489687`

## Implemented

- Minimal deterministic OpenAPI-based Reference Oracle.
- C1 documented response-status coverage.
- C2 response media-type matching for the qualified profile.
- C3 response schema validation.
- OpenAPI 3.0.x schema validation using `OAS30Validator`.
- OpenAPI 3.1 schema validation using `OAS31Validator`.
- Deterministic PASS / FAIL / NOT_APPLICABLE results.
- Exact/range/default response selection.
- Qualified handling of malformed JSON and supported media-type cases.
- Frozen contract fixtures with provenance.
- Immutable development responses/cases bound to the exact qualified contracts.
- Explicit synthetic conformant parent construction and archived natural-observation
  intake with separate origin and raw request/response provenance.
- F01–F09, including all bounded variants in `fault_model_v1.md` §§2–3.
- K01–K03 concrete control templates from §4 (13 variants).
- Parent revalidation before mutation; independent artifact-only Oracle measurement
  after mutation; family expectations used only for subsequent admission checks.
- Separate parent/child artifacts, response and contract hashes, transformation
  parameters/byte splices, and actual before/after Oracle results.
- Rejection of inapplicable/nonconformant parents, no-op/ineffective mutations,
  unexpected vectors and schema/representation diagnostic mismatches, retaining
  measured candidate evidence where available.
- Bounded development materializer and machine-readable inventory pinned to
  `development_dataset_v1.md` at research commit
  `1cbe68ceae2bb2d146870379d72394edc083b256`.
- Exactly EDX-P02, HTTS-H01 and HTTS-H05; original pilot bytes and companion
  provenance are read without modifying research inputs.
- Optional control-parent provenance in the construction API, retaining explicit
  full-body replacement and before results for DEV-02 and DEV-08.
- Ignored generated staging at `artifacts/development_dataset_v1/`, with separate
  raw bodies/envelopes, transformations, source copies, deterministic manifest and
  SHA-256 sidecar. Code/dependency/protocol/qualification provenance is recorded.
- Per-case checks of measured vectors/labels, exact body hashes, origins and
  lineage; failures retain available evidence without publishing a manifest.
- No automatic release: materialization records 0/12 at creation; the subsequent
  explicit author-approval event records 12/12 in separate release metadata.

## Verified

- Release finalization on 2026-09-22: all 253 tests passed, including Q01–Q26.
  Exact DEV-01–DEV-12 membership and artifact-only Oracle remeasurement were
  checked; every recorded Oracle output and every original staging file hash
  remained unchanged. Only the separate `release.json` was added to staging.
  Its 12/12 approval coverage matches the tracked release record; executing the
  README reproduction command twice produced identical bytes.
- 253 tests pass: 141 Oracle/validator tests, 80 construction tests and 32
  dataset materialization/provenance tests.
- All 112 targeted construction/materialization tests passed before the full suite.
- Real archive materialization matched all twelve specified bodies, vectors and
  overall labels: 6 EDX + 6 HTTS; origins 3 natural, 2 synthetic conformant,
  7 synthetic inconsistent; overall 4 consistent and 8 inconsistent.
- No specified-versus-measured reference mismatch.
- Repeated materialization is tested for byte identity of every output file,
  including the manifest; raw source inputs remain unchanged.
- Held-out F05/F07/F08 and all held-out variants/controls are absent from the
  generated development inventory; no unselected pilot siblings are imported.
- Q01-Q26 all pass.
- Oracle implementation, interface, schema/media semantics and qualification
  expectations are unchanged. Regression tests verify metadata never enters
  Oracle calls and cannot determine the measured labels.
- EDX qualification contract hash verified:
  `4fb9c2bf81b401463dcd66f463c214a3019b75b48f0a88db1cf541a770ea4fbc`
- HTTS qualification contract hash verified:
  `084b2d72929226f0984cda1ce7758c8e7d9fb1aa7e1001e308160da440828e42`
- `openapi-schema-validator 0.9.0`
- `jsonschema 4.26.0`

See `docs/validator_spike.md` for validator qualification details.

## Not implemented

- Final evaluation dataset generation/freeze.
- Remaining Gate-B runtime-failure attribution, application-role/setup closure,
  per-attempt live verification integration and final author acceptance.
- Actual Gate-B-approved prompt-development execution and sensitivity workflow.
- Main experiment runner.
- Reference-correction and sensitivity report workflows.
- Presentation of future sensitivity/final-evaluation report formats.

These are intentionally absent until required.

## Release boundary

Author manual review/reference checking is complete for all twelve cases.
The references are released for prompt development only and remain excluded from
final evaluation and final headline metrics. No next implementation milestone or
Ollama prompt trial is started by this documentation/release-status step.

## Scope and methodology notes

Implementation authority: the explicitly requested milestone and research
`development_dataset_v1.md`, `fault_model_v1.md` and
`reference_oracle_protocol_v1.md`. Exact research source hashes and inventory
verification targets are recorded in
`src/rest_api_checker/development_dataset_v1.json`.

No unresolved methodological decision was needed. Approved DEV membership is
implemented without changing Oracle semantics, fault meaning or final dataset
rules. The source documents and content manifest retain historical preparation
states; the separate release record transcribes the author's explicit approval.
Expected vectors are checked only after
artifact-only Oracle measurement and are preserved separately from actual results.

The materializer is a bounded local Python command, not an experiment runner or
persistence service. Generated development data is ignored and is not committed
or copied into the research repository. See README for reproduction, provenance
format and rejection handling.

## Methodology guard

Do not change Reference Oracle semantics, qualification expectations, fault
meaning, dataset rules, prompt context, metrics, or experiment policy without
an explicit research-methodology decision.

Research repository:

`/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker`
