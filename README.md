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
checkout, or network after installation. Materialization reads the separate pinned
research checkout; its tests use temporary archives with test-only acquisition
metadata. Both contract hashes are verified at
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

## Development dataset v1

DEV-01–DEV-12 were approved by the author on 2026-09-22 (12/12 manually
reviewed) for prompt development. The current release record is
[`docs/development_dataset_v1_release.json`](docs/development_dataset_v1_release.json).
All cases remain excluded from final evaluation and final headline metrics.

### Historical candidate materialization

Materialize the exact DEV-01–DEV-12 inventory from a research checkout at
`1cbe68ceae2bb2d146870379d72394edc083b256`:

```sh
uv run --locked python -m rest_api_checker.development_dataset \
  --research-repository /path/to/research-checkout-at-1cbe68c
```

The default output is `artifacts/development_dataset_v1/`, ignored by Git.
Use `--output artifacts/development_dataset_v1_repeat` for a second materialization.
Output must be a fresh or empty directory inside this technical checkout; an
existing candidate is never overwritten. No research files are written.
The current research document includes the later approval and therefore no longer
matches the pinned input hash. Use the historical checkout for materialization;
do not repin the inventory or replace the approved artifacts. Full manifest byte
reproduction also requires the recorded implementation commit and environment.

`development_dataset_v1.json` is the bounded machine-readable transcription of
the approved inventory, with byte hashes for the authority documents, contracts,
and explicit pilot provenance files. These are verification targets and input
bindings, not executed labels. The materializer refuses changed or missing sources,
uses the existing construction API, and checks each measured response against
its specified status, media, exact body hash, vector, overall label and lineage.
No pilot directory discovery or fault sampling occurs.

`construct_parent` and `construct_control` accept an optional `parent` to preserve
control context. Explicit control construction may start from a nonconformant
observation, as DEV-02 requires. It records the before result, full-body byte
replacement and explicit status/media selection; the resulting control must pass.
Fault construction still revalidates its conformant immediate parent.

The deterministic `manifest.json` references separate response envelopes, raw
bodies, replacement bytes, and byte-exact copies of all selected research evidence.
References are relative to the staging directory and carry SHA-256 and byte count.
Per-case records preserve origin, root family, immediate parent, before/after
Oracle decisions and diagnostics, parent hashes and transformation parameters.
Shared provenance records source commits, protocol/qualification evidence hashes,
actual dependency versions, Oracle commit, implementation commit, working-tree
status and source hashes. `manifest.sha256` hashes the exact manifest bytes.
Repeated runs with the same source bytes, implementation and environment produce
identical files; a different code commit or dependency version changes provenance.

Admission failure writes `rejection.json` and any available candidate/parent
artifacts without publishing a manifest. Resolve discrepancies explicitly; do not
change expected outcomes to force admission. Missing inputs or Oracle exceptions
never become scientific labels.

Every successful output is `CANDIDATE_PENDING_MANUAL_REVIEW`, with zero of twelve
cases marked reviewed. The author must independently reference-check all twelve
exact artifacts and resolve discrepancies under the research protocol before
release. This command cannot release references or run prompt trials.

### Author-approved release metadata

The content manifest SHA-256 remains
`8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974`.
Its `CANDIDATE_PENDING_MANUAL_REVIEW`, 0/12 and per-case false review fields
are immutable historical evidence. The separate dated release record supersedes
those review fields for this exact manifest, recording
`AUTHOR_APPROVED_FOR_PROMPT_DEVELOPMENT` and 12/12 approved cases.
It does not alter measured results, construction provenance or source bindings.

The ignored staging `release.json` is a deterministic serialization of the tracked
release record, outside the content manifest. Reproduce it from the repository root
using the existing materializer helpers (no case regeneration):

```sh
uv run --locked python - <<'PY'
import json
from pathlib import Path
from rest_api_checker.development_dataset import _json, _sha, _write

output = Path('artifacts/development_dataset_v1')
release = json.loads(Path('docs/development_dataset_v1_release.json').read_bytes())
raw = (output / 'manifest.json').read_bytes()
if _sha(raw) != release['approved_manifest_sha256']:
    raise ValueError('Approved manifest hash mismatch')
manifest = json.loads(raw)
ids = [f'DEV-{i:02}' for i in range(1, 13)]
if ([c['case_id'] for c in manifest['cases']] != ids
        or [c['case_id'] for c in release['cases']] != ids
        or release['manual_review'] != {'required': 12, 'completed': 12}
        or not all(c['manually_reviewed'] and c['approved'] for c in release['cases'])):
    raise ValueError('Review coverage mismatch')

def verify_references(value):
    if isinstance(value, dict):
        if {'path', 'sha256', 'size_bytes'} <= value.keys():
            data = (output / value['path']).read_bytes()
            if _sha(data) != value['sha256'] or len(data) != value['size_bytes']:
                raise ValueError(f"Artifact mismatch: {value['path']}")
        for child in value.values():
            verify_references(child)
    elif isinstance(value, list):
        for child in value:
            verify_references(child)

verify_references(manifest)
_write(output, 'release.json', _json(release))
PY
```

No final evaluation data, Ollama, prompts, database, UI, service source-code
analysis, metrics or experiment execution is included.
