# Implementation State

Last updated: 2026-09-26

## Current milestone

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
- Ollama runner.
- Prompt rendering / structured LLM result parsing.
- Prompt-development workflow.
- Main experiment runner.
- Evaluation metrics/report generation.
- Result visualizations.
- Web UI.

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
