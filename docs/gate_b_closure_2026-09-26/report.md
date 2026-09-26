# Final technical Gate-B closure — review candidate, not acceptance

**NOT AUTHOR-ACCEPTED — DO NOT EXECUTE.** Captured 2026-09-26, Europe/Berlin
(CEST, UTC+02:00); individual evidence files retain offset-qualified timestamps.
Baseline main HEAD: `09613eb442586bb01e338ceb28d0080173b580f7`, clean at entry.
The prior runtime qualification `080bf81f4fe9762d21dec3bc9580363f83259bbb`
was already merged. Work branch: `chore/gate-b-closure-freeze`.

The exact execution commit is the `implementation_commit` in the generated
candidate, not the historical runtime-capture commit. To avoid a self-referential
Git hash, the candidate is materialized **after** committing its builder and all
qualification evidence. It is an ignored local review artifact, like the generated
DEV dataset; the code and evidence supporting it are versioned. Its SHA-256
sidecar is the explicit author-review identity. Do not edit the candidate to
signify approval. A later merge or different HEAD requires regenerating and
reviewing a new candidate for that execution commit; old acceptance cannot carry
across a changed candidate hash.

## Result and evidence scope

Before: **9 PASS / 2 BLOCKED / 0 FAIL** (`before.json`). Technical closure qualifies
bounded failure attribution; measured SQL preflight is **10 PASS / 1 BLOCKED / 0 FAIL**
(`preflight_technical.json`). Final candidate verification output is retained
next to the candidate in `final_verification.json`. Artifact acceptance stays
BLOCKED until separate author action. No status is supplied by a PASS override:
preflight validates captured file/source hashes, measured outcomes, and successful
SQL qualification receipts. The historical runtime bundle remains byte-identical.

[Failure decision candidate](failure_decision.md) distinguishes protocol facts,
implementation facts, inference and the unresolved author choice. The scientific
protocol has not changed. A literal crash/OOM observation requirement was not
found in §7 or Gate-B §10/D10. Technical PASS is limited to tested attribution;
it does not claim empirical worker-crash/OOM qualification or author acceptance.
No further failure/model-generation diagnostic was performed in this closure.

## Database principal and operator setup

Migration 002 already specifies the role and separation from the migration owner.
The exact implementation is SQL login `rac_application_login`, database user
`rac_application_user`, sole explicit database role `rac_application`, in
`rest_api_checker`. No additional role grants, schema changes or login redesign.
Password-policy checking is on; password expiration is off for this local service
login. A strong generated password exists only in:

- Application: `~/.config/rest-api-checker/application-credentials.env`, mode 0600.
- Administrative credential retained unchanged:
  `/private/tmp/rac-sqlserver-environment-20260926/credentials.env`.
- Non-secret operator binding: `~/.config/rest-api-checker/config.toml`.

No password, credential-file contents or secret connection string is in evidence
or Git. `principal.json` records provisioning; `setup_verified.json` records actual
principal/SID, schema, role grants, counts and read-only web checks. The principal
is neither sysadmin nor db_owner. The automatic CONNECT grant is retained; no
additional direct database-user permissions are permitted by the freeze check.
See [credential precedence](../operator_convenience.md#applicationadmin-credential-separation-2026-09-26).
Normal operation never falls back to admin credentials. Existing explicit CLI
credential flags retain their meaning. The administrative file remains at its
existing location; no new retention/backup policy was invented.

Positive permission tests used disposable marked databases: connection; schema
verification; dataset/membership/reference/prompt/model/config reads; approved
source/experiment/runtime inserts; reservation/start/finalization; technical
attempt 1 plus identical valid attempt 2; one prediction for one logical run;
completion; immutable report insertion/read. Report content was fabricated and
no evaluator selected a prompt. Normal source setup in the real DB registered
only the three previously measured models and their three D07 configurations.

Negative tests actually denied database creation, dropping another disposable
DB, table create/alter/drop, migration application/history write, user creation,
db_owner/sysadmin escalation, evidence DELETE, immutable model/report UPDATE,
and BACKUP on a disposable DB. Effective ALTER ANY LOGIN was absent. No destructive
negative test targeted the real application DB. The role's bounded lifecycle
UPDATE grants and repository-level immutability constraints remain unchanged.

The web smoke used application credentials for seven GET routes, all HTTP 200;
it remained query-only. The full tests include SQL persistence and backup/restore
with the administrative harness, and Q01–Q26. Final full suite: **696 passed**, zero failures/errors/skips. Focused qualification:
**241 passed**; additional CLI/preflight regression: **104 passed**. Counts,
durations and original JUnit hashes are in `test_results.json` (full/focused).
During development, a fixture report missing its required source closure and
incorrect SQL permission-inspection expectations and historical CLI preflight
count assertions were corrected; the final suite
and evidence record the corrected, successful checks.

## Runtime and source closure

Fresh metadata-only inspection found **no drift**: Ollama 0.34.4; native runner
0.4.1-dev / `161755f29`; Apple M5 Pro, arm64, 64 GiB RAM, Metal; exact native
binary hashes and all three full `/api/show` documents and manifest/tag identities.
The prior nine fabricated completions were not repeated. Qwen3.6:27b, Gemma3:27b,
Mistral-small3.2:24b retain measured Q4_K_M. Full digests/native templates are bound
from the unmodified [runtime evidence](../runtime_qualification_2026-09-26/report.md).

D07 remains temperature 0.2, top_p 0.9, top_k 40, min_p 0.0, repeat_penalty 1.0,
repeat_last_n 64, draft_num_predict 0, num_ctx 32768, num_predict 512;
application `/api/chat`, stream=false, timeout 300 seconds; seeds 101/202/303.
Qwen requests think=false; Gemma/Mistral omit it. One frozen system prompt and
one lossless rendered user evidence message; native templates, no history/tools/
images or schema-constrained generation. Prior effective float32/inner streaming
findings remain as captured, not reinterpreted as exact decimal runtime storage.

The candidate builder reconstructs all 324 complete requests **from actual SQL
bindings** and matches their exact request hashes against existing native-template/
tokenizer measurements. No context estimator and no DEV generation is used.
Max input/total/margin: Qwen 1426/1938/30830, Gemma 1461/1973/30795,
Mistral 1481/1993/30775; P3/DEV-01 is worst for all. Complete OpenAPI evidence,
response body, native template and 512-output allowance are covered.

All 222 protected baseline hashes remain unchanged, including P1/P2/P3, released
DEV manifest/cases, references, OpenAPI inputs, protocol and frozen schedule.
The research repository's pre-existing literature edits were preserved; it is not
misreported as clean. Its HEAD/status and source hashes are recorded in the
candidate. No research file was edited here.

## Review artifact and future execution boundary

Generate once from the committed clean implementation with
`.venv/bin/python tools/gate_b_closure/candidate.py`. This only reads SQL/local
sources/runtime metadata and writes:

- `artifacts/gate_b_freeze_candidate_v1/candidate.json`
- `artifacts/gate_b_freeze_candidate_v1/candidate.sha256`

The candidate binds development/prompt-comparison phase; dataset/version/release;
12 exact memberships and reference revisions; P1/P2/P3 hashes; all model digests,
quantization/native metadata; host/Ollama/runner binaries/templates; D07/thinking/
seeds; renderer/parser/evaluator code identities and input policy; all 324 ordered
logical identities and resolved SQL IDs; schedule seed 20260925 and artifact hash;
324 request/context proofs; schema 2; exact application login/SID/user/role grants;
all archived source files and relational bindings; research source identities;
and the exact implementation commit. No SQL experiment/schedule is created.

**Author next action:** review the candidate SHA-256 and failure decision, then
choose Option A or B. For A, independently create a separate author acceptance
record containing `decision=AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON`, the exact
`candidate_sha256`, `failure_qualification=ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM`,
real `author`, and offset-qualified `accepted_at`. No such record is produced by
this task. B requires additional safely scoped evidence and a new candidate.

A minimal explicit module, `rest_api_checker.accepted_comparison`, consumes that
external acceptance. Its `prepare`, `run`, and evidence-only `reconcile` actions
are **future operations**, never invoked here. All require `--candidate` and
`--acceptance`; missing/incomplete acceptance fails before SQL/network access.
The adapter validates exact clean implementation/source/SQL closure and performs
metadata-only live identity checks before every physical dispatch, including
retry. `prepare` refuses an existing experiment. `run` also requires
`--experiment-id` and `--spool`. Existing `rac` menus and original fabricated-only
run/resume guards remain unchanged; they do not become execution buttons.

Unexpected technical failures are retained and paused. Reconciliation requires
`--technical-review`, with the exact `spool_sha256`, `attribution` (isolated,
systematic, ambiguous), named `reviewer`, `reason`, and offset-qualified
`reviewed_at`. The review is archived; only isolated attribution allows the
unchanged retry rule. Reconciliation never calls a model. Unknown envelopes remain
blocked even if someone supplies “isolated”; no parser repair/retry is introduced.

No comparison, sensitivity or main evaluation was executed; no real study
prediction, evaluation report, sensitivity variant or prompt winner was created.
The stop boundary is a reviewable, non-executable candidate and explicit author
decision, not experiment execution.
