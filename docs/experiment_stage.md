# Renderer, parser, provider and orchestration stage

Authority is the approved research `prompt_development_protocol_v1.md` D01–D11
and `database_design_v1.md` §§5–7, at research commit
`050af6b214e167c737f09ee4c9a4d8dc3862981d`. The technical starting point was
`40eaf9fdd7f074f9f1c350c1ec4cef32de3ceb88`. No scientific policy, prompt, dataset,
reference vector, database schema or evaluation formula changes in this stage.

**No real model inference or study execution occurred.** Integration outcomes,
model digests, runtime approvals and token counts are explicitly fabricated test
fixtures, in disposable SQL Server databases. The committed comparison schedule
is a non-dispatched dry-run artifact. Gate B is incomplete.

## Evidence and prompt layout

`experiment.renderer.Evidence` is a frozen, slotted allowlist DTO with only
contract bytes, method, OpenAPI path, observed HTTP status, observed Content-Type
and raw body bytes. The repository explicitly projects these fields; it never
serializes a case/domain record. `render()` refuses dictionaries and subclasses.

The `operation-evidence-v1` user message is one JSON object:

```json
{
  "operation": {"method": "<method>", "path": "<OpenAPI path>"},
  "openapi": {
    "openapi": "<source version>",
    "paths": {"<OpenAPI path>": {"<method>": {"responses": "<complete Responses Object>"}}},
    "components": "<required referenced subtrees, when present>"
  },
  "observed_response": {
    "status": 200,
    "content_type": "<exact observed header, or JSON null for absence>",
    "body": "<losslessly escaped original UTF-8 body text>"
  }
}
```

This is shape notation, not a model example or an added prompt. Other local
reference target kinds stay at their original document pointers when needed.
The JSON document under `openapi` is the resolution root. The complete Responses
Object is retained; every branch contributes to closure regardless of observed
status/media/body. References remain unchanged. Targets are deduplicated by
pointer; the implementation checks retained source values and closure equality.
Unrelated operations, components and root metadata are absent.

Serialization is sorted Unicode-code-point object keys, compact comma/colon
separators, ASCII JSON escaping (`ensure_ascii=True`), no BOM, and one terminal
LF. ASCII bytes are also valid UTF-8. Arrays retain order. Contract decimal
numbers use exact Decimal parsing rather than binary-float rounding. The body
is strictly UTF-8 decoded only for outer transport; it is never JSON parsed,
normalized, repaired or truncated. Decoding the outer body string and encoding
UTF-8 must reproduce its original bytes, including BOM, whitespace, malformed
JSON and line endings. Missing Content-Type is distinct from an empty string.

The renderer is bounded to the qualified 3.0.4 and 3.1.0 study profile. It reuses
the existing schema admission guard on every response/media branch, without
measuring the body or producing a reference result. Unresolved/external/anchor
references, cycles, reference siblings, dialect changes, unsupported assertions,
missing schemas and ambiguous reference contexts raise a hold. Array-index
reference contexts that require inventing sparse members or including unrelated
array members are held. Nothing is silently inlined, weakened or fetched remotely.
All twelve released DEV cases render successfully.

Provenance is a separate immutable sidecar: renderer version/artifact hash,
contract/body identities and byte hashes, Responses Object pointer, sorted closure
paths, evidence hash, prompt hash, model digest, repetition/seed, timeout and
serialized request hash. No sidecar field is inserted into either message.
Contract annotations and raw body text remain evidence even if they contain
words resembling labels or runner metadata; there is no content scrubbing.

The complete approved P1/P2/P3 artifact is the single system message, byte for
byte after UTF-8 round trip. The single user message is the rendered evidence.
The request constructor checks the three approved SHA-256 values against the
existing importer constants. No shared blocks are concatenated a second time.
No history, previous thinking, predictions, examples or reference labels enter
messages. Exact prompt hash mismatch blocks request construction.

## Parser

`strict-output-v1` parses only designated `message.content`. It accepts exactly
c1/c2/c3 with exactly verdict/reason, exact legal verdicts and nonblank string
reasons. It accepts JSON whitespace and arbitrary key order. It rejects duplicate
keys at any depth before mapping, NaN/Infinity, fences, prose, extra or missing
members, coercion and blank reasons. No extraction, stripping, repair or partial
salvage occurs. Diagnostics contain deterministic status/code/member pointer.

All 27 legal verdict vectors parse, including FAIL/PASS/PASS. Scientific
correctness and applicability are future evaluator concerns. Reasons are retained
unchanged, with no numerical length cap. Empty final content and malformed or
incomplete limit-stopped content are PARSER_FAILURE. A complete compliant object
at the output limit remains VALID_OUTPUT. Separate thinking is retained in the
raw envelope and diagnostics but never parsed or scored. Thinking tags inside
final content remain part of that content and cannot be removed for acceptance.

`output_schema_v1.json` specifies the structural contract. Duplicate detection is
an additional parser responsibility that JSON Schema alone cannot express.
The parser artifact digest binds parser.py, encoding.py and the schema, with
filename/NUL/bytes/NUL framing. The renderer digest similarly binds renderer.py,
encoding.py and its existing schema/pointer dependencies. Setup hashes must match
before dispatch. Changes need an artifact/version review before a comparison freeze.

## Request and provider boundary

POST `/api/chat` sends these exact top-level fields: `model`, `messages`,
`options`, `stream:false`; Qwen additionally has `think:false`. Gemma and Mistral
omit `think` entirely. `format`, tools, images and all extra messages are absent.
`options` includes temperature 0.2, top_p 0.9, top_k 40, min_p 0.0,
repeat_penalty 1.0, repeat_last_n 64, draft_num_predict 0, num_ctx 32768,
num_predict 512 and the repetition seed (1→101, 2→202, 3→303).
Timeout is 300 seconds per physical attempt. Request bytes are revalidated at the
HTTP boundary. No SDK defaults or automatic retries are used; each call creates
one connection and one POST. Redirects are not followed. Socket deadlines plus a
watchdog prevent a trickling response from repeatedly renewing the read budget.

The transport preserves raw response entity bytes without decoding, HTTP status,
headers, elapsed duration, observed timestamps and partial delivery/error evidence.
The envelope preserves final content, thinking, stop reason, reported counts and
all provider timing fields. A missing count stays absent; no count is guessed.
The documented API field layout was checked against
[Ollama's chat API reference](https://docs.ollama.com/api/chat); that documentation
is interface evidence, not proof of the installed models' effective behavior.

The boundary classifies:

| Evidence | Action |
|---|---|
| Completed usable envelope, valid final object | VALID_OUTPUT; one prediction |
| Completed usable envelope, malformed/empty final answer | PARSER_FAILURE; no prediction or retry |
| Interrupted transport, timeout, explicit HTTP 5xx server failure | Technical candidate; isolated/systematic attribution required |
| Missing/nonstring final field, invalid envelope without clear runtime attribution, 4xx/configuration error, unexpected provider mode | Preserve evidence and pause |
| Systematic or ambiguous failure | Preserve evidence and pause, leaving terminal result unresolved |

The external failure-review callback can confirm only isolated technical
attribution; it cannot override parser outcomes. The default review is ambiguous
and grants no retry. Explicit 200/error envelopes are held for runtime attribution
rather than inferring OOM/crash from arbitrary text. One isolated technical failure
settles attempt 1 only. Attempt 2 is explicitly requested through the same API,
with byte-identical request and timeout and reverified model/template identity.
Its valid/malformed/technical result settles the run. No attempt 3 exists.

## Context and runtime gates

`ContextProof` binds exact request hash, model digest, native-template hash,
measurement-artifact hash and a measured token count including BOTH messages,
native template and applicable defaults. The proof must equal its entry in the
frozen setup. Input plus 512 output tokens must fit 32768, otherwise dispatch
blocks. No heuristic token estimate or evidence truncation is provided.

A required runtime-verification callback must establish the same frozen model
manifest/template and effective runtime configuration before every attempt.
There is no default callback that claims success. Real `OllamaClient` dispatch
also requires a non-fabricated, Gate-B-complete setup. These are integration
boundaries; this task does not produce actual tokenization/runtime proofs or
claim installed option support. No inference CLI or batch study command exists.

## Schedule

`comparison-schedule-v1` uses the model block order qwen3.6:27b, gemma3:27b,
mistral-small3.2:24b. Each block starts with DEV-01…DEV-12 × P1/P2/P3 × 1/2/3,
in that loop order. Fisher–Yates runs from index 107 down to 1.
Its independent per-model counter stream hashes the ASCII bytes
`comparison-schedule-v1\n20260925\n<model>\n<counter>\n`, counter starting at 0.
Interpret each SHA-256 as an unsigned big-endian 256-bit integer. For bound i+1,
reject integers at or above `2**256 - 2**256 % bound`, then take modulo bound.
This avoids modulo bias and dependence on a particular Python random version.

The dry-run artifact has exactly 324 identities, 108 per prompt and model,
36 per model/prompt, all repetitions/seeds, and unique consecutive global
run_order 1…324. SQL binding verifies membership codes, prompt hashes, model names
and D07 configurations through repository methods, then atomically persists the
schedule/setup. Only disposable databases were used here. Schedule materialization
creates no attempts or predictions. Sensitivity scheduling is absent; its future
budget remains 108 variant runs.

## Persistence and recovery

The orchestration API performs read/projection → render/hash → context/runtime
checks → archive sidecar → reserve exact request → observe dispatch boundary →
provider call → durable spool → strict classification/parser → atomic finalization.
It uses repositories throughout; schema and migration files are unchanged.
A session-owned SQL application lock admits one orchestrator per database. This
claim is independent of SQL transactions. The provider window switches ODBC to
autocommit after the committed start record and restores manual transaction mode
before persistence. Integration tests observe zero active user transactions from
a separate server connection during fabricated calls.

A reserved slot cannot be taken over or sent again. Missing reservation or
finalization acknowledgement requires reconciliation, not another model call.
`reconcile_attempt` never dispatches. It imports the spool as evidence first,
reclassifies/parses under the bound parser, and uses atomic finalization. Identical
replays are idempotent. Late/conflicting results remain diagnostic successors;
they cannot replace a failed attempt or a later terminal result. The spool helper
now recognizes an already-finalized spool hash without appending redundant
successors. Request immutability, composite consistency, retry eligibility and
one-prediction constraints remain repository-enforced.

Database/storage/fsync failures pause. `Paused` retains available receipt bytes,
attempt ID and any durable spool path; temporary spool bytes remain recoverable
when fsync fails. These failures do not become provider failures or retry rights.
The receipt-to-fsync crash window remains; exactly-once external execution is not
claimed. Spools are retained after reconciliation.

## Remaining Gate-B and later work

Required before any study dispatch: actual full model manifests and Q4_K_M
metadata; runtime/client/hardware and native-template/default evidence; effective
support for every approved option (including draft_num_predict and false/omitted
thinking); tokenizer/template-aware context measurements; isolated versus
systematic runtime-failure evidence; artifact acceptance and complete setup/source
closure; deployment credentials with the application role; full Gate-B acceptance.
Code support alone establishes none of these capabilities.

Evaluator/ranking/formulas, sensitivity variant/schedule, final dataset, dashboard
and Main Experiment remain outside this stage. The SQL Server deployment keeps
the previously accepted local emulation limitation. See the verification report
for measured test results, acceptance coverage and retained dry-run evidence.
