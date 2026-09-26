# Gate-B runtime qualification — 2026-09-26

Status: **runtime evidence captured; Gate B remains BLOCKED; no author acceptance**.
All timestamps in artifacts are offset-qualified (Europe/Berlin, CEST, UTC+02:00).
Capture began at **12:11:24 CEST**. Implementation baseline:
`5079bc26bffd3541c8256d3411012d9e233835aa`; research HEAD:
`050af6b214e167c737f09ee4c9a4d8dc3862981d`.
The implementation revision is the commit containing this report, on
`chore/gate-b-runtime-qualification`.

## Authority and exact acceptance boundaries

Inspected the existing preflight, provider/request/renderer/parser/schedule,
model/configuration registration, orchestration, migration 002, technical stage,
persistence/operator/web documentation, and research protocol §§5, 7, 10 and
`database_design_v1.md` setup closure. The four runtime checks were unconditional
BLOCKED placeholders. Their existing evidence obligations are retained:

| Check | Required evidence | Result |
|---|---|---|
| Full model identities | Full manifests/digests, actual Q4_K_M, metadata, runtime/hardware | PASS for captured snapshot |
| Template and effective options | Native template/defaults, exact request boundary, measured D07/thinking | PASS for captured snapshot |
| Context fit | Every complete scheduled request, native tokenizer/template, 512 output allowance | PASS |
| Failure attribution | Runtime-specific isolated/systematic failure evidence, conservative attribution and retry policy | BLOCKED; partial verification below |
| Gate-B artifact acceptance | Complete setup/source closure, application-role deployment, author acceptance | BLOCKED; deliberately not performed |

**Before: 6 PASS / 5 BLOCKED / 0 FAIL. After: 9 PASS / 2 BLOCKED / 0 FAIL.**
See `database_before.json` and `database_after.json`. Offline preflight without SQL
has 8 PASS / 3 BLOCKED. Preflight itself performs no inference or network calls.
These PASS checks validate a source-bound historical capture. They do not certify
the currently running host or replace the mandatory per-attempt live identity
callback, complete setup freeze, or author acceptance. No runtime dispatch adapter
or acceptance bypass was added.

## Model and host identity

Each exact local manifest was hashed and compared with `/api/tags`; **every config
and layer blob** was independently SHA-256 hashed and size-checked against its
manifest, including projector/template/parameter/system layers where present.
`identities.json`, the three manifests and full `/api/show` responses retain the
identities and native metadata. No model was pulled, replaced, retagged or updated.

| Tag | Full manifest SHA-256 |
|---|---|
| qwen3.6:27b | `9d5803d493a991af27b9441c098aa56f2ed7bbd260877f075ec09b575c049bc3` |
| gemma3:27b | `a418f5838eaf7fe2cfe0a3046c8384b68ba43a4435542c942f9db00a5f342203` |
| mistral-small3.2:24b | `5a408ab55df5c1b5cf46533c368813b30bf9e4d8fc39263bf2a3338cfa3b895b` |

| Tag | Architecture | Actual parameters | Native context capability | Actual quantization |
|---|---|---:|---:|---|
| qwen3.6:27b | qwen35 | 27,320,697,856 | 262144 | Q4_K_M |
| gemma3:27b | gemma3 | 27,432,062,576 | 131072 | Q4_K_M |
| mistral-small3.2:24b | mistral3 | 24,011,361,280 | 131072 | Q4_K_M |

Quantization is corroborated by `/api/show` (`Q4_K_M`, GGUF file type 15),
hash-bound config blobs and loaded runner `/props` (`Q4_K - Medium`). Stored config
`architecture=amd64, os=linux` describes model packaging metadata, not this host.

Host: **Apple M5 Pro, arm64, 64 GiB RAM, 20-core Apple GPU, Metal 4**;
macOS **27.0 (26A428)**. Runtime log reports Metal iGPU, 51.8 GiB available at
startup. CPU core counts and exact build output are in `runtime_build.json`.
Ollama server/client: **0.34.4**; native runner: **0.4.1-dev, build 1,
commit 161755f29**, built with AppleClang 21.0.0.21000099 for Darwin arm64.
Python client: **3.12.14**, standard-library `http.client`.
`host.json` hashes both runtime binaries. `/api/ps` was initially empty; per-model
loaded context/model/VRAM snapshots and runner command lines are retained.
The protocol's earlier author-reported 0.34.3 is historical; no update occurred
in this task.

## Native templates, D07 and thinking

Nine fabricated, non-study `/api/chat` completions were made: one per model/seed.
Their output text was **discarded, never displayed, semantically judged, parsed as
study predictions or persisted in SQL**. Only transport/envelope metadata,
content length/hash and thinking-presence/length remain. The diagnostic harness
locally replaces only the approved-prompt validation seam so fabricated text can
exercise the real `OllamaClient.send`; production validation is unchanged.
Separately, all 324 exact production requests were built and validated offline
with their approved P1/P2/P3 and rendered DEV evidence.

Boundary verified: POST `/api/chat`, `stream=false`, precisely one system and one
user message, no history/tools/images/format constraint, application timeout 300 s.
Native template bytes and hashes are retained. Actual fabricated rendered strings
show:

- Qwen uses its configured **qwen3.5 renderer/parser**. `/api/show`'s
  `{{ .Prompt }}` placeholder alone is not its effective native message framing.
  `think=false` produces the native closed, empty think prefix; no separate
  thinking content was returned. Its stored defaults had thinking enabled and
  `draft_num_predict=3`; explicit D07 overrides were therefore material.
- Gemma maps both supplied system/user messages to native user turns, then the
  model prefix. The experimental system text remains present. `think` is omitted.
- Mistral uses `[SYSTEM_PROMPT]` and `[INST]` framing. The explicit experimental
  system message replaces its stored default system text. `think` is omitted.

No template, default or native parser was edited. The runtime's Go-rendered path
uses a fallback chatml runner template with `--no-jinja`; `/props`' fallback is
not substituted for the actual render-only result.

| D07 setting | Observed effective evidence |
|---|---|
| temperature 0.2 | runner slot `0.20000000298023224` (exact float32 conversion) |
| top_p 0.9 | runner slot `0.8999999761581421` (exact float32 conversion) |
| top_k 40, min_p 0.0 | runner slots 40, 0 |
| repeat_penalty 1.0, repeat_last_n 64 | runner slots 1, 64 |
| draft_num_predict 0 | explicit request; loaded slots `speculative=false`, `speculative.types=none`; runner has no speculative-draft flag |
| num_ctx 32768 | `/api/ps`, runner command and slot `n_ctx=32768` |
| num_predict 512 | slot `n_predict=max_tokens=512` |
| seeds 101 / 202 / 303 | each seed directly observed for every model |
| stream=false | complete non-streamed outer response; runner internally uses stream=true and Ollama aggregates it |
| timeout 300 seconds | real application deadline; also observed in the initial loopback timeout probe |

The runner does not echo an integer `draft_num_predict`; the observed equivalent
is **speculation disabled**, not an invented echoed value. No D07 option was
rejected or found ignored. An intentionally invalid `top_k` type yielded HTTP 500
before generation. Source inspection shows unknown option names may be ignored,
which is why HTTP acceptance alone was not used as effectiveness evidence.
Exact native-default parameter text is retained in each show response; additional
runner defaults (sampler chain, penalties, keep/cache/shift settings) are preserved
in props/slots and command records. No low-level numerical/cache equivalence
across model families is claimed.

## Exact context measurement without study generation

The installed stack supplies a safe two-step mechanism:

1. Ollama `/api/chat` with `_debug_render_only=true, truncate=false` renders the
   original complete messages and returns before completion. This was reviewed
   in version-matched source and verified first on fabricated content.
2. The **same loaded model's** native llama-server `/tokenize` counts that rendered
   text with `add_special=true, parse_special=true`. No completion endpoint is
   called on study content. Model blob/port identity is checked before counting.

Synthetic parity with actual `prompt_eval_count`: Qwen **54**, Gemma **51**,
Mistral **46**, for all three seeds. Omitting automatic special tokens would
undercount Gemma and Mistral by one; those BOS tokens are included. The installed
runner, not a substitute tokenizer or estimate, performs all measurements.
The exact native runner source was unavailable at the attempted public URL;
version-matched Ollama source, runtime binary hashes, actual runner observations
and synthetic count parity support the method.

**108 complete native render/tokenize measurements cover 324 request identities**.
Rendering is seed-independent in the inspected path and in all nine fabricated
renders. Counts are mapped to all three exact seeded request hashes. Each input
contains the frozen candidate, complete operation-scoped OpenAPI/reference
closure and exact response representation. `request_inventory.json` binds every
request; `context.json` retains counts, native-render/token-list hashes, model and
template identities, worst cases and arithmetic. No character/byte estimates,
normalization, truncation or repaired evidence were used.

| Model | Maximum input | +512 output | Remaining margin | Worst pair |
|---|---:|---:|---:|---|
| Qwen | 1426 | 1938 | 30830 | P3 / DEV-01 |
| Gemma | 1461 | 1973 | 30795 | P3 / DEV-01 |
| Mistral | 1481 | 1993 | 30775 | P3 / DEV-01 |

All fit 32768. **No context blocker remains and no context-related author decision
is required.** Study text reached only native rendering/tokenization, never
semantic inference. Render-only responses contained no generated answer or
output-token count. No study output existed to discard.

## Failure attribution and retry evidence

`failures.json` records real closed-loopback connection refusal, a 50 ms isolated
HTTP deadline, synthetic HTTP 500, completed malformed final content, and a valid
fabricated parser fixture. `outcome_for` distinguishes transport/timeout/provider
failures from parser failure and valid output. Synthetic terminal content was
fabricated by the harness, not judged from model output.

The first attempt at an unreachable endpoint used a bound but non-listening
socket; this host timed out after the **real 300 s** application deadline instead
of immediately refusing. It is preserved honestly as timeout evidence in
`failures_initial.json`. A closed port subsequently supplied actual connection
refusal. No listener/system/network configuration or unrelated process was changed.

| Class | Evidence and limitation |
|---|---|
| Transport | Actual loopback connection refusal through production transport; not an Ollama outage |
| Timeout | Actual 300 s deadline and shortened 50 ms isolated HTTP test; not an Ollama hang |
| Provider/runtime | Synthetic HTTP 500 classification; actual Ollama invalid-option HTTP 500 (known systematic configuration defect) |
| Parser failure | Completed synthetic HTTP 200 with malformed final content; no technical retry |
| Successful valid output | Completed synthetic HTTP 200 with valid parser fixture; actual Ollama calls verify completed envelopes only, without quality inspection |
| Crash/OOM isolation | **Unverified**; none induced or observed |

Pure diagnostics verify attempt 1 technical retry eligibility, no attempt 2 retry,
no parser retry, and blocking of systematic/ambiguous attribution. Established
SQL tests additionally verify byte-identical requests, two physical attempts in
one logical run, no attempt 3, terminal technical failure retained in planned-run
denominators, and no prediction on parser/terminal technical failure.

**Failure attribution remains BLOCKED.** The actual invalid-option response is
not relabeled an isolated runtime crash. No permissive live failure-review
callback was introduced. The remaining work is to qualify and bind conservative
runtime-specific crash/interrupted-envelope attribution using safely obtainable
runtime evidence; ambiguous or systematic failures must continue to pause. An
author may authorize a bounded additional diagnostic design, but this report
neither weakens the criterion nor supplies author acceptance.

## Application-role/setup closure

Read-only SQL inspection found schema 2, `rac_application` present with **zero
members**, no non-system SQL/application database users, and current `dbo` /
`sysadmin=1`. Migration 002 and `docs/persistence.md` require separate externally
provisioned application credentials; administrative credentials must not run
experiments. This **is an execution blocker** inside artifact/setup acceptance.

The exact principal name/credential storage decision is not specified, so no
login/user/database/role membership or schema change was made. The minimal next
DBA action, after an application principal is chosen and its secret provisioned
outside both repositories, is:

```sql
-- Placeholders: choose the externally provisioned application identity first.
USE [master];
CREATE LOGIN [<approved_application_login>] WITH PASSWORD = '<private_secret>';
USE [rest_api_checker];
CREATE USER [<approved_application_user>] FOR LOGIN [<approved_application_login>];
ALTER ROLE [rac_application] ADD MEMBER [<approved_application_user>];
```

Use existing principals if subsequently provisioned; do not create duplicates.
Point a private mode-0600 application env file at that login (`RAC_SQL_USER`),
verify non-sysadmin/non-db_owner effective privileges, and test allowed repository
operations and denied mutation/schema/ledger actions in the established disposable
integration environment. Migration credentials remain separate. No actual secret
or connection string is included here. Study model/config registrations and the
complete immutable setup record are also still absent by design.

## Reproduction, integrity and handoff

Use the configured Python 3.12 environment. Capture tools under
`tools/runtime_qualification/` separate read-only metadata/SQL (`capture.py`),
fabricated calls (`probe.py MODEL [SEED]`), fabricated token parity
(`token_probe.py SHORT[_seedNNN]`), study **render/tokenize-only** measurement
(`context.py`), isolated faults (`failures.py`), and hash binding (`seal.py`).
These are explicit qualification tools, not a study runner. Repeating the live
capture overwrites this dated snapshot; preserve the committed evidence and use
a separately reviewed new capture location for future qualification.

`bundle.json` binds evidence and scientific/implementation sources by SHA-256;
its `author_acceptance=false` is mandatory. Missing evidence stays BLOCKED;
changed bytes, options, source bindings, missing coverage or overflow yield FAIL.
The checker performs no inference and never sets Gate B complete. Frozen renderer,
parser, request, schedule, Oracle and persistence semantics are unchanged.
Official source URLs/hashes and reviewed behaviors are in `source_review.json`:
[Ollama routes](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/server/routes.go),
[native runner adapter](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/llm/llama_server.go),
[option types](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/api/types.go).

Final verification: **205 focused tests passed**; **650 full SQL-enabled tests
passed in 137.80 seconds**, zero failures/errors/skips, including Q01–Q26 and
backup/restore. The full suite was rerun after final validator tightening.
`test_results.json` preserves counts/timings/class coverage and original JUnit
hashes; verbose XML test names containing synthetic credential fixtures are not
retained. `git diff --check` passed.

```sh
RAC_SQL_TEST_ENV=/private/tmp/rac-sqlserver-environment-20260926/credentials.env \
RAC_SQL_TEST_BACKUP_DIR=/private/tmp/rac-operator-backup-verification \
.venv/bin/python -m pytest -q tests tools/sqlserver_environment/test_probe.py
```

Final preservation comparison: **222 protected files byte-identical**, including
all tracked and initially untracked research files, complete DEV artifacts,
release/reference/OpenAPI evidence, candidate bytes and frozen schedule. Existing
research working-tree changes (`literature.bib`, `thesis_citation_plan.md`) were
present before this task and remain untouched. Model tag snapshots are identical.

The application database before/after counts are identical: 12 cases, 12
references, 3 prompts; **0 models, configurations, experiments, logical runs,
physical attempts, predictions and evaluation reports**. Test records exist only
in established disposable test databases, which the suite removes.

Changes: `runtime_evidence.py`, the minimal preflight integration, focused
validation tests and two updated CLI/operator snapshot expectations;
`docs/implementation_state.md`; this report/evidence folder; explicit capture
scripts under `tools/runtime_qualification/`. No dependencies were added. All
production request, renderer/parser, orchestration, schedule, migrations and
scientific-source bytes were preserved.

**Explicit exclusions:** no 324-run comparison, no sensitivity experiment, no main
evaluation, no study prediction, no prompt winner, no scientific-protocol or
reference-label change, and no final Gate-B author acceptance.

Remaining author/operator actions: review this evidence without treating review
as acceptance; decide/provision the application principal and durable private
credentials; qualify remaining runtime-specific failure attribution; bind the
complete setup/source closure and live identity checks; then perform the separate
exact-artifact Gate-B acceptance. None is silently performed by this pass.
