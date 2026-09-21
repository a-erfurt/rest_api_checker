# Implementation State

Last updated: 2026-09-21

## Current milestone

Development-case parent/control construction and approved fault families complete.
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

## Verified

- 217 tests pass: 141 existing tests and 76 focused construction tests.
- Targeted construction tests passed before the complete suite.
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

- Development dataset generation.
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

Review the construction milestone, then define and authorize a bounded development
case inventory and manual-audit workflow. No dataset membership, split, quota,
final evaluation case or release is established by this implementation.

## Scope and methodology notes

Implementation authority: the explicitly requested milestone and research
`03_research_design/fault_model_v1.md`, SHA-256
`c02b2185db370394d913b0cf1831c0791cd05b67f42246a75da0e8daff62bdc9`
(also recorded in the existing provenance manifest).

No unresolved methodological decision was required. The fault model retains
historical proposal/sign-off caveats; the implementation instruction authorizes
this development capability, not a dataset release or additional human audit.
The Q/S-derived control templates and automated tests are implementation probes,
not scored evaluation cases or additional human-reviewed qualification records.

Construction is a small in-memory Python API in `construction.py`; no generic
mutation framework, persistence or runner was added. See the README for API,
variants, hash format and rejection-evidence handling.

## Methodology guard

Do not change Reference Oracle semantics, qualification expectations, fault
meaning, dataset rules, prompt context, metrics, or experiment policy without
an explicit research-methodology decision.

Research repository:

`/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker`
