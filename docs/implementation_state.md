# Implementation State

Last updated: 2026-09-21

## Current milestone

Reference Oracle and validator qualification complete.

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

## Verified

- 141 tests pass.
- Q01-Q26 all pass.
- EDX qualification contract hash verified:
  `4fb9c2bf81b401463dcd66f463c214a3019b75b48f0a88db1cf541a770ea4fbc`
- HTTS qualification contract hash verified:
  `084b2d72929226f0984cda1ce7758c8e7d9fb1aa7e1001e308160da440828e42`
- `openapi-schema-validator 0.9.0`
- `jsonschema 4.26.0`

See `docs/validator_spike.md` for validator qualification details.

## Not implemented

- Fault generator.
- Parent/conformant-control construction.
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

Implement provenance-preserving construction of conformant parent/control cases
and the small approved fault-family generator defined by the research
repository's `fault_model_v1.md`.

Required rule:

A single-fault parent must first be Reference-Oracle conformant.
Mutation intent does not define the reference label.
The mutated artifact is evaluated independently by the Reference Oracle.

## Methodology guard

Do not change Reference Oracle semantics, qualification expectations, fault
meaning, dataset rules, prompt context, metrics, or experiment policy without
an explicit research-methodology decision.

Research repository:

`/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker`
