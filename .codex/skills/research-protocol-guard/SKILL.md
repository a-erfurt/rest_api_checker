# Research Protocol Guard

This skill prevents implementation decisions from silently changing the
scientific experiment.

## STOP and request an explicit research decision when a change affects

- the definition of a Validation Response Contract Inconsistency,
- C1 / C2 / C3 meaning,
- PASS / FAIL / NOT_APPLICABLE semantics,
- C1 -> C2 -> C3 applicability or branch-selection rules,
- media-type matching semantics,
- schema-validation semantics,
- Reference Oracle labeling behavior,
- approved Q01-Q26 expectations,
- API-specific contract authority,
- the use of source code or external prose as additional authority,
- a new fault family,
- the scientific meaning of an existing fault family,
- using fault IDs or mutation intent to determine labels,
- natural versus synthetic case semantics,
- dataset development/test split,
- final dataset membership or freeze,
- class/fault-family balance after it has been fixed,
- prompt information budget,
- OpenAPI context supplied to the LLM,
- model selection or repetition policy after freeze,
- metric definitions or aggregation,
- treatment of N/A, invalid outputs, retries, or technical failures,
- prompt/data changes motivated by final test-set results.

## Normally safe without a new methodology decision

Provided behavior and labels are unchanged:

- refactoring,
- improving test coverage,
- typing and code cleanup,
- deterministic performance improvements,
- packaging/build changes,
- provenance capture,
- logging,
- clearer diagnostics or error messages,
- internal restructuring,
- fixing implementation bugs so behavior matches the already approved protocol.

## When stopping

Report only:

1. the exact unresolved methodological question,
2. the affected research artifact and section,
3. the implementation consequence,
4. realistic options and trade-offs,
5. which code change was intentionally NOT made.

Do not choose the scientific option yourself.
Do not change tests to encode a new methodological interpretation before the
research decision is approved.
