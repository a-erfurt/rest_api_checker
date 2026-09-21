# REST API Reference Oracle

Minimal technical milestone for **Evaluating LLM-Based Detection of Validation
Response Contract Inconsistencies in REST APIs**. This deterministic component
produces operational reference labels for later LLM evaluation. It is **not a
competing baseline**, an experiment runner, or a general OpenAPI validator.

## Reproduce

Python **3.12.14**, uv **0.12.17** used for the initial qualification. From this
repository, with uv installed:

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked pytest -v tests/test_oracle_qualification.py
```

The lockfile pins all dependencies. Tests need no API service, model, research
checkout, or network after installation. Both contract hashes are verified at
session start, before fixture loading, and at session end. The committed copies
are byte-identical to the research snapshots; tests never write to the research
repository. Do not refresh them from a live service.

## Public API

```python
from pathlib import Path
from rest_api_checker import evaluate_response

result = evaluate_response(
    contract=Path("tests/contracts/edx_openapi_3.0.4.json"),
    operation_path="/edx/validation/body",
    method="post",
    status=200,
    content_type="application/json; charset=utf-8",
    body=b'{"code":0}',
)
assert result.vector == ("PASS", "PASS", "PASS")
assert result.overall == "CONSISTENT"
```

`contract` can also be an already parsed document. Callers must bind external
contract files to verified byte hashes before use; qualification fixtures enforce
this automatically. Only the two frozen operations are scientifically qualified.
Synthetic contract tests exercise selection mechanics without expanding API scope.

Results contain C1/C2/C3, the derived overall label, selected response/media keys,
the selected schema's document pointer, and a deterministic tuple of diagnostics.
`Diagnostic.schema_path` is the library's path relative to the selected schema,
including traversal through references, **not** an absolute document pointer.
Diagnostics and eligibility errors are reference-side information, not future
LLM inputs or extra scientific classes.

- C1 checks documented status coverage, with exact → range → default precedence.
- C2 matches the selected response's declared media. Only the qualified JSON
  charset exception is admitted; arbitrary parameters are not ignored.
- C3 decodes original UTF-8 JSON and checks the selected dialect/schema without
  changing property names, types, missing fields, or extra properties.
- No status match produces `FAIL / NOT_APPLICABLE / NOT_APPLICABLE`.
- A valid unmatched media type produces `PASS / FAIL / NOT_APPLICABLE`.
- Any FAIL means `INCONSISTENT`; an all-PASS vector means `CONSISTENT`.

`OracleNotReady` holds unsupported/ambiguous evidence without a completed vector
or overall label. Its `code` explains why. In particular, declared EDX `text/plain`
and `text/json` match C2 in component checks, but their unresolved decoding prevents
a completed oracle result. `OracleExecutionError` signals a validator failure;
it is never relabeled as C3 FAIL or NOT_APPLICABLE. Unexpected infrastructure errors
also propagate without a label. An empty schema is supported; a missing schema is held.

## Evidence and limits

See [validator spike and qualification](docs/validator_spike.md) for candidate
comparison, measured outcomes, versions, admission limits, and source links.
[Provenance](tests/contracts/provenance.json) pins the research commit and all four
methodology-file hashes as well as the two contract hashes.

The 26 readable expectations in `tests/test_oracle_qualification.py` transcribe
the author's signed review unchanged. Additional tests are implementation probes,
not additional human-reviewed reference cases or scored LLM data. Passing these
examples establishes bounded agreement, not universal oracle correctness.

No Ollama, prompts, mutation/dataset generation, database, UI, service source-code
analysis, or experiment execution is included. The next milestone requires its
own authorization and dataset/reference review; this repository does not release
an experiment dataset.
