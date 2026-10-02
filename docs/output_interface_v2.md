# Evaluation-v2 output interface

This additive generation interface was executed in a bounded development pilot
on 2026-10-02. The author selected `format_json` for Main v2. Historical v1
used P2's JSON instruction without Ollama `format`.
Its request bytes, freezes, parser, archived outputs and official results remain
unchanged. There is no retroactive output repair and no final v2 evaluation has
been run. The pilot measured format compliance; it does not establish final
semantic performance or semantic superiority of an interface.

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
The completed pilot on qualified Ollama 0.35.0 observed parser-valid output
for both structured modes in all six model/case positions per mode; this bounded
observation is not a general enforcement guarantee.
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
Live dispatch requires current context/runtime evidence for the exact requests;
old prompt-only context proofs cannot be assumed valid for changed requests.

No migration is needed for this interface preparation: existing `run_configs`
represent generation settings, while setup files/request sidecars carry interface
bindings. If a later authorized pilot uses SQL, store each mode in a separate
experiment setup: the existing per-experiment run uniqueness excludes mode.
Such SQL planning/execution is outside this preparation command.

## Live development pilot dispatch

`interface_pilot_v2_live` reuses the unchanged offline preparer and existing
Ollama `/api/chat` transport. It reads the prepared request bytes and sidecars,
verifies byte equality against preparation from the approved DEV release, and
sends those loaded bytes. It accepts exactly two explicitly selected released
DEV IDs, all three existing Ollama models, all three modes and repetition 1:
**18 planned calls**, at the unchanged **512** output-token limit and seed 101.
No dataset path or Main execution option is exposed. LM Studio is out of scope.

After the author selects the two DEV cases, prepares the package and supplies
verified runtime/context evidence:

```sh
uv run python -m rest_api_checker.interface_pilot_v2_live run \
  --prepared /path/to/prepared-pilot \
  --cases "$DEV_CASE_A" "$DEV_CASE_B" \
  --model-digests /path/to/verified-model-digests.json \
  --runtime-binding /path/to/pilot-runtime-binding.json \
  --context-proofs /path/to/pilot-context-proofs.json \
  --output /path/to/new-pilot-execution \
  --confirm-development-interface-pilot
```

The runtime binding has exactly `runtime` and `models`, using the existing
`freeze.verify_live` format: `runtime` is the qualified `host.json` object and
`models` is the ordered three-model `identities.json` list. The referenced native
`show` files are read from `docs/runtime_qualification_2026-09-26/`; these existing
snapshots are never rewritten. Supplied digests must match the prepared requests.
The existing verifier checks current Ollama version, full model digests, native
metadata/templates/defaults, runtime binaries and host identity before the pilot
and immediately before each call. Missing evidence or drift blocks dispatch;
an older qualification snapshot alone is not a current identity check.
Native metadata bytes are copied and hash-bound in the execution directory;
changes to those source snapshots during execution also stop the pilot.

Context proofs are a JSON object keyed by all 18 exact request SHA-256 values.
Each value uses the existing `ContextProof` fields: `request_sha256`,
`model_digest`, `template_sha256`, `measurement_sha256`, `input_tokens`.
The measurement must cover the exact interface request and native template;
the runner checks binding and `input_tokens + 512 <= 32768`, without estimating
tokens or generating qualification output. Gathering/reviewing missing native
measurements remains separate; no v1 proof is silently reused for changed bytes.

Each planned call has one provider attempt. Parser failures are retained and
execution proceeds to the next planned item; there is no retry, repair, best-of,
vote or interface fallback. A technical failure or unusable provider envelope
is preserved and stops the pilot. Interruption or persistence failure requires
manual review, with any available bytes and dispatch markers retained. The
prepared package is claimed by an exclusive `live-dispatch.json` marker before
the first call; it cannot be resumed or dispatched again to another directory.
Do not remove this marker to retry an ambiguous or failed execution.

A new execution directory retains the prepared package, runtime/context inputs,
execution identity, durable per-call reservations/start markers, full raw
provider bytes (including partial/empty responses), transport diagnostics,
exact `message.content` in UTF-8 (surrogatepass for unpaired JSON surrogates),
separate thinking text when available, done reason
and unchanged strict-parser result/diagnostic. Missing response bytes remain
distinct from an explicitly empty response. Raw bytes are fsynced before parsing.
The receipt-to-file crash window remains; an unsettled call cannot be inferred
to have failed or to be eligible for redispatch.

`summary.json` reports attempted calls, provider success/failure, parser-valid
and parser-failure counts, unsettled calls and stop/length reasons per model/mode.
It performs no semantic evaluation or model ranking and selects no interface
winner; parsed predictions remain available for a separate author decision.
There is no SQL, reference assessment or dataset mutation in the runner. The
bounded live pilot was subsequently executed as recorded below; final
**Main-v2 has not been executed**.


## Completed pilot and Main-v2 decision (2026-10-02)

FACT: DEV-02 and DEV-10 × three models × three modes × repetition 1 produced
18/18 completed provider calls, exactly one attempt per position, seed 101.
There were 14 parser-valid outputs, four preserved Markdown-fence failures,
zero technical failures and zero length stops.

| Model | prompt_only | format_json | json_schema |
| --- | ---: | ---: | ---: |
| qwen3.6:27b | 2/2 | 2/2 | 2/2 |
| gemma3:27b | 0/2 | 2/2 | 2/2 |
| mistral-small3.2:24b | 0/2 | 2/2 | 2/2 |
| Total parser-valid outputs | 2/6 | 6/6 | 6/6 |

`prompt_only` reproduced the Gemma/Mistral fence problem. Both `format_json`
and `json_schema` achieved 6/6 parser-valid outputs. DESIGN DECISION: the author
selected Ollama `format="json"` / `format_json` for Main v2 because it resolved
the observed machine-readable output problem while being less structurally
restrictive than `json_schema`. This does not demonstrate semantic superiority
or universal optimality. The unchanged strict parser remains the validation
boundary; P2, generation settings and the **512-token** budget remain unchanged.
LM Studio is not part of Main v2 at this stage.

The qualified v2 pilot runtime is Ollama **0.35.0** on macOS **27.0.1**.
Historical v1 used Ollama 0.34.4 on macOS 27.0. The three model digests and native
template hashes match their historical qualified identities; runtime binaries
and native metadata are separately bound. No cross-version byte-identical
inference behavior is claimed. All 18 exact context proofs passed; the maximum
requirement was 1326 + 512 = 1838 tokens against num_ctx=32768. Future execution
still requires current identity checks and its own exact-request context proofs.

LIMITATION: two exposed DEV cases and one execution per position do not estimate
final model performance. Format compliance, semantic vector correctness, binary
decision correctness and reason correctness remain separate. No final Main-v2
evaluation has been run.

The research archive is
`../bachelor_rest_api_checker/08_evaluation_v2/output_interface_pilot_v2/`:
[decision record](../../bachelor_rest_api_checker/08_evaluation_v2/output_interface_pilot_v2/interface_selection.md),
[original report](../../bachelor_rest_api_checker/08_evaluation_v2/output_interface_pilot_v2/report.md),
[operational summary](../../bachelor_rest_api_checker/08_evaluation_v2/output_interface_pilot_v2/execution/summary.json),
and [archive manifest](../../bachelor_rest_api_checker/08_evaluation_v2/output_interface_pilot_v2/archive_manifest.json).
Pilot-tested implementation commit: `dc17b6d3a8c72ed3bcd8b375f8d2f02fc3c092d8`.
Generated v2 native metadata is retained in the research archive's
`runtime_namespace/`; the archived binding's relative lookup namespace can be
restored byte-identically for future offline checks. Historical technical
qualification snapshots remain unchanged.
