# Evaluation and CLI verification — 2026-09-26

**PASS for the bounded implementation stage: 478 tests passed in 125.93 seconds,
including 61 SQL Server integration tests; zero failures, errors or skips.**
The full suite includes Q01–Q26 and independent SQL backup/restore verification.
The offline source-distribution/wheel build passed, including the evaluator and
`rest-api-checker` entry point. `git diff --check` passed.

Technical baseline: `fd78654`; implementation branch: `feature/evaluation-cli`.
Research HEAD remains `050af6b214e167c737f09ee4c9a4d8dc3862981d`.
Research was read-only. Its pre-existing modified `literature.bib` and untracked
`thesis_citation_plan.md` were left untouched. No methodology clarification was
needed. No schema/migration, Oracle, prompt, model-roster, D07, retry, dataset or
selection-hierarchy change was made.

**No real model inference or study execution occurred. The real 324 comparison
runs have NOT started. No study prompt winner or sensitivity variant exists.**
No Ollama endpoint was contacted. Tests forbid actual inference HTTP and inject
fabricated provider receipts. The public CLI's real dispatch path is blocked
before constructing a provider. No web UI, final dataset or Main Experiment was
implemented.

## Retained evidence

- [Full-suite JUnit](evaluation_evidence/full_suite.xml): 478 tests, including all
  443 baseline tests and 35 additional metric/CLI/SQL tests.
- [Final inventory](evaluation_evidence/final_inventory.json): source identities,
  test totals, evaluator artifact hash, research state and post-cleanup databases.
- [Fabricated demo summary](evaluation_evidence/fabricated_demo_summary.json):
  exact counts, metrics, tie trace and hashes of exported input/report and both
  terminal transcripts. All displayed selection results are fabricated-only.
- [Plain demo transcript](evaluation_evidence/fabricated_demo_plain.txt): bounded
  milestones, retries, final counts and all three prompt/model/category tables;
  CRLF converted to LF and trailing terminal padding removed for the Git copy.
- [Offline preflight](evaluation_evidence/preflight_offline.json): 5 PASS,
  6 BLOCKED (database omitted).
- [SQL-schema preflight](evaluation_evidence/preflight_sql_schema.json): 6 PASS,
  5 BLOCKED, measured against a fresh marked disposable database and then cleaned
  up. It contains no experiment and does not claim persisted-study freeze.

The raw animated transcript and complete fabricated input/report exports remain
outside Git at `/private/tmp/rac-evaluation-live-20260926.typescript` and
`/private/tmp/rac-evaluation-live-20260926/`. Their hashes are in the summary;
temporary paths are local verification evidence, not a long-term archive.

## Evaluator checks

The independent hand-counted fixture starts from perfect predictions and changes
one prompt/model's first repetition: one parser failure, one terminal technical
failure, and one wrong C3 applicability verdict on three distinct cases. Expected
results are Score `317/324`, Robust `33/36`, StableCorrect `101/108`, Reliability
`106/108`, FullCase `105/108`, C3 valid-only accuracy `33/34`, valid coverage
`34/36`, valid-triple coverage `10/12`, and vector disagreement `1/10`.
All match. NOT_APPLICABLE is scored; failures never appear in semantic confusion
counts. All-failure valid-only/disagreement metrics are null, not zero.

Every ranking criterion, exact sub-display-precision differences, frozen prompt
length and final P1/P2/P3 order are covered. SQL tests verify complete schedule
accounting, uncompleted-report rejection, missing/extra/duplicate protection,
configuration/model/reference drift, prediction/attempt binding, immutable original
reports, append-only reevaluation and application-role UPDATE/DELETE rejection.
The pure engine and CLI JSON read identical metrics. A snapshot closure defect
found during development was corrected: prior reports and unrelated archive files
are excluded; unchanged reevaluation now preserves the exact input/report bytes.

## Fabricated execution and presentation

Both an ordinary NO_COLOR terminal run and an actual ANSI/live terminal run
completed visibly. The live run showed the waiting spinner, elapsed time,
current model/prompt/case/repetition/attempt, progress percentage and counters.
It refreshed a compact panel, leaving a final summary in scrollback. The plain
transcript contains no ANSI sequences; the live transcript contains the expected
cursor/refresh sequences. Unit checks additionally exercise live-panel contents,
redirected output, JSON-only stdout and NO_COLOR overriding forced-color settings.

Each demo completed **324 logical runs in 326 physical attempts**:
322 valid outputs, 1 parser failure, 1 terminal technical failure, 0 pending.
One technical retry succeeds and another terminates technically. Retry events
leave the logical total at 324 and completion unchanged until settlement.
The fixed fabricated predictions are all PASS and never consult references.
Their comparison has P1/P2 Score `216/324`, P3 `212/324`; the artificial P1/P2
tie reaches UTF-8 length. This is a UX/engine fixture, not a study winner.

Actual SIGINT tests verify that current persistence finishes, no new work is
scheduled and exit 130 is returned. Resuming skips already terminal runs.
Stopping after first technical failure retains a pending run; resume sends its
one identical retry. Reserved ambiguous state repeatedly blocks without calling
the fake provider. An interrupted public `experiment demo --json` retains the
marked database/spool and prints a concrete resume command; the test verifies
the persisted pending state before explicitly cleaning it up. Isolation tests
reject a missing disposable marker before creating an experiment.

## Frozen artifacts and cleanup

DEV manifest remains
`8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974`.
All released file bindings were rechecked without Oracle remeasurement/importer
mutation. P1/P2/P3 hashes remain:

```text
P1 f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6
P2 50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f
P3 5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb
```

All integration/demo databases were uniquely named, explicitly marked disposable
SQL Server resources. Final read-only inventory found only the two historical
qualification databases, `rac_env_probe_20260926` and
`rac_env_probe_restore_20260926`. No `rac_test_*` database or real
`rest_api_checker` study database remained. No original probe/volume was removed.
The accepted local SQL Server emulation limitation is unchanged.

## Remaining Gate B

The preflight does not fabricate PASS for: full actual model/manifests/Q4_K_M and
runtime/hardware evidence; native templates/defaults and effective D07/thinking
behavior; complete tokenizer/template context-fit measurements; real runtime
failure attribution; full setup/source closure, application-role deployment and
exact-artifact/freeze acceptance. Reference corrections, sensitivity reports and
actual real-provider CLI wiring remain later bounded work. Code and fabricated
tests establish no installed-model capability or scientific execution approval.
