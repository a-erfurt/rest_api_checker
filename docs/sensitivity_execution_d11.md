# P2 sensitivity execution and D11 evaluation

Authority: research `03_research_design/prompt_development_protocol_v1.md`,
sections 5–7 and 9/D11, at research commit
`a54ec11b33d90722a482464dcda9823fdc50cf90`.

The adapter supports only the approved `P2_SENSITIVITY_V1` bytes. The 108-slot
schedule remains the order-preserving P2 projection of the accepted comparison
schedule: 12 DEV cases × three models × repetitions 1/2/3, seeds 101/202/303.
Its SHA-256 remains
`0dbe99e7022f4dc46ece2a6127889b4f4c8a5822869557b332602f5221e0c700`.
This retains the preliminary documented implementation choice under the
protocol's deterministic, pre-execution schedule freeze and exact pairing rules.
It does not claim that D11 prescribed a particular shuffle implementation.

## Boundaries

`rest_api_checker.sensitivity_execution` provides `prepare`, `run`, and
`reconcile`, each requiring `--candidate` and `--acceptance`. It consumes a
separate author record whose decision is `AUTHOR_ACCEPTED_FOR_P2_SENSITIVITY`,
with `candidate_sha256`, a nonempty `author`, and offset-qualified `accepted_at`.
The final candidate must be reviewed before such a record is supplied. There is
no acceptance writer. Prompt approval and comparison acceptance cannot authorize
this phase; the preliminary v1 candidate is rejected even with an acceptance.

Invalid acceptance and local source/commit/freeze drift fail before SQL access.
The application principal, schema, baseline rows, model/configuration and
request/context identities are checked before preparation or dispatch. Live
runtime identities are rechecked immediately before every physical attempt.
Preparation registers the variant and creates exactly 108 logical runs only
after acceptance. It refuses an existing second experiment. No baseline run or
report is rewritten.

The original batch, attempt, provider, parser and spool lifecycle is reused via
explicit request preparation/validation hooks. Defaults retain comparison-only
request validation. Sensitivity requests receive their own exact reconstruction
check; the default comparison allowlist still rejects them. No renderer, parser,
output schema, context/token limit, model configuration or API format constraint
changes. Markdown fences remain parser failures.

Parser failure is terminal. Technical evidence is durably retained and pauses
for spool-hash-bound review. Only isolated attribution permits one identical
second attempt. Ambiguous/systematic attribution and reserved attempts block;
resume does not dispatch reserved work. The existing cooperative SIGINT behavior
retains active-attempt evidence before stopping subsequent dispatch.

## D11 mapping

| Protocol requirement | Persisted report fields |
|---|---|
| Nine category effects and aggregate | `models.*.category_deltas` (/36), `Score_delta` (/324) |
| Per-repetition category results | `baseline/variant.models.*.per_repetition` (/12) |
| ModelCorrect and difference | `baseline/variant.models.*.ModelCorrect` (/108 category outcomes), `models.*.ModelCorrect_delta` |
| StableCorrect | `baseline/variant.StableCorrect` (/108), model (/36), category (/12) views |
| Valid-triple disagreement and coverage | `repeat_disagreement` by category/vector; `valid_triple_coverage` (/12) |
| Parser/technical counts and rates | `outcomes` with integer numerator and denominator /36 or /108 |
| Reliability and full-case correctness | baseline/variant `Reliability`, `FullCase`, prompt /108 and model /36 |
| Matched valid-only verdict disagreement | `models.*.category_disagreement`, `vector_disagreement`, `paired_valid_coverage`, excluded failure pairs |
| Pooled disagreements | `pooled.category_disagreement` denominator 3 × valid pairs; vector denominator valid pairs |
| Terminal transitions | complete 3×3 tables, invalid-to-valid and valid-to-invalid counts, per model and pooled |

All arithmetic is exact rational arithmetic. Empty conditional denominators
retain numerator/denominator with JSON null value (metric N/A). Failure outcomes
remain in the planned correctness/reliability denominators and never become
semantic verdicts. There is no ranking, winner, majority vote, pass/fail
threshold, new inferential metric or retrospective prompt selection.

`sensitivity_analysis.analysis_input` validates complete persisted schedules,
exact baseline setup/report/candidate bindings, shared dataset/reference/model
and configuration rows, strict parser replay, attempts, retry provenance and
request hashes. It pairs the existing P2 outcomes by the frozen case/model/
repetition schedule, including failures. `create_report` records a new immutable
input/report and an explicit baseline-report foreign key; it does not recompute
or overwrite the comparison report. Tests use fabricated completions only.

## Historical validity and execution authorization

`freeze.verify_historical` verifies implementation source hashes/inventory at the
candidate's bound Git commit, plus preserved research/dataset/evidence bytes.
Offline preflight labels this as historical evidence and stays BLOCKED. Optional
historical code lookup in runtime/technical evidence inspection is explicit.
Default inspection still rejects current source drift.

`freeze.verify_candidate` remains the comparison execution gate and still
requires current source closure, clean tracked implementation and exact HEAD.
The accepted comparison adapter continues to use it. Historical verification
never produces acceptance or grants current execution permission.

The former three failures shared `Incomplete freeze source closure`: the new
sensitivity module expanded the source inventory after the comparison freeze.
The old exact-HEAD guard would also reject the later preparation commit.
Historical verification now answers the historical question without relaxing
current execution guards. Historical fixtures use their bound source revision.
Comparison candidate construction tests now use disposable application-principal
databases because the real study database is no longer empty.

## Final candidate construction

Commit implementation, tests and this documentation first. Then run
`tools/sensitivity_freeze/finalize.py` with the configured Python environment.
The command uses SELECT-only study reads and metadata-only runtime checks. It
copies the existing native context evidence only after every reconstructed
request matches byte-for-byte and runtime/template/tokenizer identities match.
It fails on drift rather than issuing generation. The original v1 directory is
preserved. The new ignored `artifacts/sensitivity_freeze_candidate_v2` binds the
exact implementation commit without a recursive commit/hash dependency.

The generated candidate remains **NOT ACCEPTED / DO NOT EXECUTE**. The next
manual step is review of that exact candidate hash, its D11 implementation and
verification evidence, followed by a separate explicit acceptance record if the
author approves. Creating or running the actual sensitivity experiment is a
later operator action, outside this implementation task.
