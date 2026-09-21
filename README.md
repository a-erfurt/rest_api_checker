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

## Development case construction

`rest_api_checker.construction` implements the bounded F01–F09 and K01–K03
families in the research repository's
[`fault_model_v1.md`](../bachelor_rest_api_checker/03_research_design/fault_model_v1.md).
The construction layer accepts only the two byte-identical qualified snapshots.
It leaves the Oracle implementation and interface unchanged.

```python
from pathlib import Path
from rest_api_checker.construction import (
    ContractSnapshot, Response, construct_parent, construct_control, mutate,
)

contract = ContractSnapshot("edx", Path("tests/contracts/edx_openapi_3.0.4.json").read_bytes())
parent = construct_parent(
    "dev-parent", contract, Response(200, "application/json", b'{"code":0}'),
    construction="Explicit synthetic development parent",
)
child = mutate("dev-child", parent, "F03", variant="null")
control = construct_control("dev-control", contract, "K01", "nullable")
assert child.before.vector == ("PASS", "PASS", "PASS")
assert child.result.vector == ("PASS", "PASS", "FAIL")
assert child.parent is parent
```

`construct_parent` measures caller-supplied synthetic bytes and requires all PASS.
`observe` measures an archived natural response as-is, including inconsistencies;
it requires `Observation(source, request, response)` with original archive bytes.
The caller supplies the corresponding status, Content-Type and body; this module
does not acquire responses or parse wire archives. Origins remain distinct.

`mutate` remeasures its parent before applying one approved transformation, then
passes only contract, operation, status, Content-Type and body to the Oracle again.
It checks the measured vector against family expectations after measurement.
Schema failures and F09 representation failures remain distinct. Fault parents use
exact `application/json`; the separately admitted charset control is K01 only.

| Family | Variant names |
| --- | --- |
| F01 | `status_500` |
| F02 | `undeclared_media` |
| F03 | `string`, `boolean`, `null` |
| F04 | `root`, `nested` |
| F05 | `integer_key` |
| F06 | `remove_msg` |
| F07 | `string_loc` |
| F08 | `null`, `integer` |
| F09 | `broken_json` |
| K01 | `omitted`, `integer_code`, `nullable`, `nested_strings`, `nested_optional_nullable`, `charset` |
| K02 | `null`, `array`, `object` |
| K03 | `omitted`, `empty_detail`, `string_locations`, `integer_location_extras` |

Fault variants default to the first listed variant. Nested operations accept an
`item_index` (default 0); other operators reject it. Controls require an explicit
variant and construct literal Q/S boundary templates. These templates are probes,
not new independent evaluation instances. Explicit parents retain their supplied
construction description without claiming an additional control family.

Cases and their evidence records are frozen dataclasses. Each derivative retains
the complete parent, contract snapshot bytes/hash, family/variant, transformation
parameters, exact byte splice (for body changes), and before/after Oracle results.
`parent_sha256` and `response.sha256` bind original and resulting artifacts.
Response SHA-256 hashes UTF-8 JSON encoded with `separators=(',', ':')` over
`["response-v1", status, content_type, body.hex()]`; it covers all three response
layers, while contract identity is bound separately. Byte edits preserve existing
formatting and unrelated values; they never serialize or repair the whole body.

`ConstructionRejected` reports invalid preconditions, nonconformant parents,
no-op/ineffective mutations and unexpected outcomes. Its `candidate` retains the
actual artifact and measured result when produced; mutation rejections also retain
`parent` and `before` when measured. A conformant unsuccessful mutation retains
its control outcome and original fault intent. Rejected construction candidates
are not admitted cases, even when their construction intent was a control.
`OracleNotReady` and execution failures propagate without fabricated labels.
Evidence is retained in memory; no persistence layer is introduced.

No dataset membership, final evaluation cases, Ollama, prompts, database, UI,
service source-code analysis, or experiment execution is included. Dataset
construction/release and manual audit require their own later step.
