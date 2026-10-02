# Evaluation-v2 output interface

This is an additive generation-interface candidate for a small development
pilot. Historical v1 used P2's JSON instruction without Ollama `format`.
Its request bytes, freezes, parser, archived outputs and official results remain
unchanged. There is no retroactive output repair and no final v2 evaluation has
been run. Interface reliability and semantic accuracy have not yet been measured.

`experiment.request_v2.build_request_v2` requires an explicit `OutputInterfaceV2`
configuration and returns a separate `RequestV2`. It uses the exact approved P2
and the existing evidence allowlist. It never routes through v1 freeze identity.

| Mode | Ollama request |
| --- | --- |
| `prompt_only` | No `format`; P2 asks for JSON, providing the v2 comparison baseline. |
| `format_json` | Exactly `"format": "json"`. |
| `json_schema` | `format` contains the dedicated `output_transport_schema_v2.json`. |

Ollama documents both forms of `format` in its [chat API](https://docs.ollama.com/api/chat)
and [structured-output guide](https://docs.ollama.com/capabilities/structured-outputs).
Actual support and enforcement on the installed runtime/models remain pilot questions.
Prompt messages, thinking policy, seeds, timeout and all generation options are
identical across modes; only `format` differs. Options remain temperature 0.2,
top_p 0.9, top_k 40, min_p 0.0, repeat_penalty 1.0, repeat_last_n 64,
draft_num_predict 0, num_ctx 32768 and num_predict **512**. Testing 1024 output
tokens is a separate future condition.

The transport schema requires exactly c1/c2/c3, each with exactly verdict/reason,
three independent legal verdict values and string reasons. It has no `$ref`,
pattern, draft metadata or semantic cross-field constraints. All **27** verdict
vectors remain structurally possible, including incoherent vectors. It contains
no expected answers, reference labels, fault IDs, binary classification or
case-specific information. The transport schema is neither a reference schema
nor a semantic correctness rule. OpenAPI remains the only API-specific authority.

The unchanged `strict-output-v1` parser verifies complete `message.content`
after generation, including in structured modes. It still rejects Markdown
fences, duplicate/extra/missing keys, malformed JSON and blank reasons. Transport
allows any string reason; the parser still requires a nonblank reason. There is
no fence stripping, substring extraction, repair or semantic correction.
Format compliance, semantic vector correctness, binary decision correctness and
reason correctness remain separate questions.

The sidecar binds `output-interface-v2`, the selected mode, transport-schema hash
when used, builder hash, exact wire-byte hash and a separate v2 request identity.
Identical prompt-only wire bytes can share their content hash with v1; their
versioned identity remains distinct. Mode/provenance fields are never model input.
Use `OllamaClient(request_validator=validate_request_v2)` explicitly for v2;
the default client still rejects v2 DTOs and altered v1 bytes before HTTP.

## Offline pilot preparation

The command requires **two author-selected, already exposed DEV cases**, the
three full model digests and a new output directory. It prepares exactly
2 cases × 3 models × 3 modes × 1 execution (seed 101), without SQL or HTTP.
For example, after choosing the two cases and verifying the installed digests:

```sh
uv run python -m rest_api_checker.interface_pilot_v2 \
  --cases DEV-01 DEV-02 \
  --model-digests /path/to/verified-model-digests.json \
  --output artifacts/output_interface_v2_pilot_candidate
```

The digest file is a JSON object with exactly the keys `qwen3.6:27b`, `gemma3:27b`
and `mistral-small3.2:24b`, each mapped to its full 64-character lowercase SHA-256
(an optional `sha256:` prefix is accepted). The example cases are not a frozen
pilot selection. Held-out/final identifiers, duplicate cases, changed DEV
release bytes and incomplete model bindings are rejected.

The new directory contains all 18 exact requests and sidecars, selected source
contract/body bytes, P2, transport schema and a deterministic, hash-bound manifest.
Its status is `PREPARED_NOT_EXECUTED`. This command does not authorize or execute
calls, select a winning interface, compute performance or create database rows.
Later dispatch needs explicit authorization and current context/runtime evidence
for the exact requests; old prompt-only context proofs cannot be assumed valid
for changed requests. This branch provides no live pilot runner.

No migration is needed for this interface preparation: existing `run_configs`
represent generation settings, while setup files/request sidecars carry interface
bindings. If a later authorized pilot uses SQL, store each mode in a separate
experiment setup: the existing per-experiment run uniqueness excludes mode.
Such SQL planning/execution is outside this preparation command.
