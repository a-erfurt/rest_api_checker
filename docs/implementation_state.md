# Implementation State

Last updated: 2026-09-22

## Current milestone

Development dataset v1 materialization complete: exactly DEV-01–DEV-12.
Generated artifacts are candidates pending author review of all twelve cases.
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
- No automatic release: manual review remains 0/12.

## Verified

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
- Database or web UI.

These are intentionally absent until required.

## Next planned implementation step

Author manual review/reference checking of all twelve generated candidate artifacts
and Oracle labels, resolving discrepancies before development-reference release.
No next implementation milestone is started; Ollama prompt trials remain deferred.

## Scope and methodology notes

Implementation authority: the explicitly requested milestone and research
`development_dataset_v1.md`, `fault_model_v1.md` and
`reference_oracle_protocol_v1.md`. Exact research source hashes and inventory
verification targets are recorded in
`src/rest_api_checker/development_dataset_v1.json`.

No unresolved methodological decision was needed. Approved DEV membership is
implemented without changing Oracle semantics, fault meaning or final dataset
rules. The source documents retain historical proposal/sign-off text; generated
records do not claim new human review. Expected vectors are checked only after
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
