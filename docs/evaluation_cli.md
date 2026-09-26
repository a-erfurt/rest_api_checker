# Evaluation and thesis CLI

Authority: research `prompt_development_protocol_v1.md` §6 (D08/D09), §7
(D03/D10), §10 and `database_design_v1.md` §§5–7.1. This stage implements
comparison evaluation and terminal presentation without changing methodology.

**The real 324 comparison runs have NOT started. No study prompt winner exists.
No sensitivity variant exists. Demo data is FABRICATED / TEST DATA.** No Ollama
inference, web UI, final dataset or Main Experiment is part of this stage.

## Commands

Run `uv sync --locked` to install the console entry point, then
`rest-api-checker --help`. `python -m rest_api_checker` is equivalent when using
the configured project interpreter. The CLI retains argparse and extends the
existing SQL administration functions. The old
`python -m rest_api_checker.persistence` entry point remains compatible.

```text
rest-api-checker
  db status | version | init | migrate --expected-current N
  db import-dev --staging PATH --release PATH | import-prompts
  db create-test | destroy-test | backup --server-path PATH | restore-test --server-path PATH
  dataset list | cases DATASET_ID | inventory
  experiment list | show ID | schedule ID | progress ID
  experiment run ID --spool PATH [--fabricated]
  experiment resume ID --spool PATH [--fabricated]
  experiment reconcile --spool-file PATH [--fabricated]
  experiment demo [--delay SECONDS] [--export NEW_DIRECTORY] [--keep]
  inspect run RUN_ID | attempts RUN_ID
  evaluate comparison EXPERIMENT_ID | list | show REPORT_ID
  evaluate export REPORT_ID --output NEW_FILE
  preflight [--experiment-id ID]
```

Common options (before the group or after the leaf command):
`--env-file PRIVATE_FILE`, `--database NAME`, `--root TECHNICAL_ROOT`,
`--research RESEARCH_ROOT`, `--json`, `--plain`, `--verbose`.
Default root is the current directory, research is its sibling checkout, and
database is `rest_api_checker`. No implicit initialization or migration occurs.
Use explicit test names for fabricated work; no generic destructive SQL command
is exposed. Existing administration safeguards still apply.

`dataset inventory` shows models, prompts and exact stored configurations.
Experiment summaries show planned/completed/pending and distinct outcome counts;
`schedule` adds each persisted identity/order/repetition/seed. `progress` is a
read-only current snapshot; live progress accompanies `run` and `resume`.

Run inspection prioritizes case/model/prompt/repetition/seed/status, the exact
bound reference, category predictions and correctness, reasons and attempts.
Reasons are model text, not verified explanations. Parser/technical failures
have no semantic verdict. `--verbose` adds exact request JSON, complete rendered
evidence (including raw body) and lossless base64 provider envelopes. Model text
is rendered literally with terminal control characters escaped.

## Evaluator and immutable reports

`evaluation.py` is the single engine used by CLI and JSON reports. It starts
from all `experiment_runs`, compares their complete identities bidirectionally
with the frozen schedule, then validates the exact approved 324-slot design.
Missing/extra/duplicate/unfinished runs, drift and unaccountable attempt or
prediction bindings block publication. The original report requires the released
DEV references, revision 1, including exact manifest/source pointers. It never
selects a newer reference. Reference-correction and sensitivity workflows remain
deferred.

Newly planned setups contain a content-bound projection of memberships,
references, cases, responses, operations, contracts, prompts, models and configs.
Old setup bytes are never augmented in place; a setup missing this binding is
blocked for report generation/resume. No real study had started at this boundary.
No database migration is required.

Report creation uses a SERIALIZABLE transaction, verifies source file hashes,
exact relational bindings, retry entitlement and terminal attempt/prediction
agreement, and reparses captured final content under the bound parser. It archives
the immutable analysis-input bytes first and computes from those bytes. That
snapshot contains the setup, references, relational content digest, all scheduled
outcomes/attempts/predictions, prompt lengths and source/evidence closure. Closure
follows repository-owned diagnostic predecessors, never arbitrary provider links
or unrelated experiments/reports. Completed JSON and `evaluation_reports` metadata
are inserted only after successful calculation. The existing immutable files
trigger and application-role permissions prevent overwrites; administration
credentials remain outside the normal application trust boundary.

Each reevaluation appends a report row with the evaluator artifact SHA-256;
identical immutable bytes may be deduplicated by the archive. Existing reports
remain readable. Export refuses to overwrite a file. A report includes exact
integer counts/denominators, rational values, source/setup/model/prompt/reference
identities, run-level correctness, ranking, tie trace and diagnostics. The input
snapshot additionally retains raw-evidence file identities, not duplicated raw
observations. A standalone report is an analysis export, not a full archive
backup; use the existing archive/backup facilities for the referenced evidence.

The engine implements the approved formulas without majority vote:

| Quantity | Exact comparison denominator |
|---|---:|
| Each model/prompt/category cell | 36 |
| Score (sum correct category outcomes, equivalent to nine-cell mean) | 324 per prompt |
| Robust (minimum of nine cells) | 36 |
| StableCorrect (case/model/category correct in all repetitions) | 108 |
| Reliability (terminal valid logical runs) | 108 |
| FullCase (complete reference-vector matches) | 108 |

Lexicographic order is Score, Robust, StableCorrect, Reliability, FullCase,
shorter frozen UTF-8 instruction length, then P1/P2/P3. Python `Fraction` performs
exact comparisons. Rounding occurs only in presentation. Both failure types give
zero category successes while retaining the planned denominator; they acquire no
invented verdict. Reference NOT_APPLICABLE is a scored state.

Diagnostics include per-model/prompt/category and repetition correctness,
three-state confusion counts over valid outputs, failures separately,
valid-only accuracy with `/36` coverage, stable-correct units, full-case results,
and category/vector repetition disagreement over complete valid triples with
`/12` coverage. Zero-denominator metrics store JSON null and display `N/A`.
Default tables show integer fractions; `--verbose` adds percentages, per-repetition
tables, confusion, valid-only coverage and disagreement. Exact tie values always
appear in the selection trace. All three prompts' model/category tables remain
visible. A fabricated report labels its selection as demo-only.

## Progress and interruption

One compact Rich panel uses cyan for neutral emphasis. It refreshes four times
per second, with a logical-run progress bar, percentage, session elapsed time,
waiting spinner, current model/prompt/case/repetition/attempt and result counters.
It uses normal terminal scrollback, not an alternate full-screen UI. The final
panel and summary remain visible. See the Rich
[live-display API](https://rich.readthedocs.io/en/stable/live.html).

The denominator is persisted logical runs. A first technical failure leaves the
run pending; retry displays `attempt 2/2`. Only valid, parser-failure or terminal
technical-failure settlement advances completion. The fake demo's 326 physical
attempts therefore complete exactly 324 logical runs.

On SIGINT the scheduler sets a stop flag and schedules no further attempt. The
active provider attempt may finish (bounded by its existing 300-second timeout),
spool and persistence reconciliation complete where safe, then the CLI prints
completed/pending counts and inspect/resume guidance with exit 130. Repeated
Ctrl-C does not abandon an active database transaction. A hard process kill can
still interrupt external execution; exactly-once external execution is not claimed.

Resume uses persisted runs in frozen order and skips terminal runs. An explicitly
qualified first technical failure can use its remaining identical retry. Any
reserved/ambiguous slot is `BLOCKED / NEEDS RECONCILIATION`, remains pending and
is never dispatched again automatically. `experiment reconcile` consumes a
durable spool without calling a provider. Nonqualifying failure attribution stays
blocked. The CLI currently admits fabricated execution/reconciliation only;
real execution is blocked before provider construction because actual runtime
verification/attribution and Gate-B acceptance are not implemented.

## Plain and JSON modes

Redirected output, `--plain`, and `NO_COLOR` disable animations/colors. Plain
execution emits bounded milestones (one per 36 logical completions/model change),
retry/interruption notices and a final summary, never polling logs. `--json`
writes exactly one JSON value to stdout, with diagnostics on stderr and no Rich
output. Inspect/status/evaluation/preflight use the same backend in either mode.
Exit codes: 0 success, 2 command usage, 3 blocked/failed verification or operation,
130 interruption. A BLOCKED Gate-B preflight deliberately returns 3.

## Offline preflight

`preflight` rechecks the released DEV manifest/file closure and approval, exact
prompt hashes/source bindings, all 12 rendered input hashes/round trips/closure,
renderer allowlist rejection, parser hash/27-vector acceptance/rejection probes,
and the 324-slot non-dispatched schedule artifact. With a database it also checks
schema/checksums; with an experiment it checks persisted schedule/bindings.
Missing source files produce FAIL; an unsupplied database produces BLOCKED, not
PASS. These are concrete implemented checks, not a claim to rerun the full test
suite. Fabricated metadata/context proofs never discharge real runtime checks.

Remaining Gate-B blockers: actual full model/Q4_K_M and runtime/hardware evidence;
native templates/defaults/effective D07 and thinking behavior; complete measured
tokenizer/template context fit; runtime-specific failure attribution; complete
setup/source closure, application-role deployment and exact-artifact/freeze
acceptance. No real inference is attempted by preflight.

## Fabricated demo

```sh
rest-api-checker --env-file /private/tmp/rac-sqlserver-environment-20260926/credentials.env \
  experiment demo --export /private/tmp/rac-demo-new-export
```

The demo creates a fresh marked `rac_test_<uuid>` SQL Server database, imports
unchanged approved input artifacts, uses explicitly fabricated model/template/
context evidence and fixed fake answers independent of references, and exercises
valid output, parser failure, successful technical retry, terminal technical
failure and evaluation. It never constructs an Ollama client. It refuses an
unmarked/non-disposable database or non-fabricated experiment. `--delay` slows
fake responses for visual review; `--json` emits the result/report/preflight.

On successful completion the default removes the disposable database and spool.
`--export` preserves input/report JSON in a new directory. `--keep` retains the
marked demo resources for inspection. Interrupted/blocked demos also retain their
database and spool automatically and print the concrete resume command; no run
state is destroyed on Ctrl-C. Use `db destroy-test` for explicit later cleanup.
No demo result is a scientific prompt-selection result.

## Verification

Tests include independent hand-computed metric fixtures, every tie criterion,
exact near-ties, failure denominators/N/A, plain/JSON/live/NO_COLOR output,
SQL drift/reconciliation, append-only reports, application-role write rejection,
actual SIGINT with fabricated provider receipts, resume/retry accounting and
isolation. The full suite also retains Q01–Q26 and SQL backup/restore checks.
See [verification record](evaluation_verification_2026-09-26.md).
