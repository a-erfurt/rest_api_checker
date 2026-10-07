# Interactive Web UI and CLI parity — 2026-10-07

The existing read-only Web UI now opens the latest interactive result from bare
`rac` option 3. Post-run **Open in Web UI** retains the exact selected run. This
pass preserves all earlier work documented below; no branch switch, commit or push
was performed. The current branch remains `main` at
`47fc67d09108ce18e891c0c86ce2195f6aab25d9`.

## Behavior and implementation

- Latest lookup is SELECT-only, across explicit live contexts because the schema
  has no ownership field. It excludes Dataset 3 / Experiment 10003 and prefers
  attempted/started results over untouched pending repetitions, then newest run ID.
  Absence falls back gracefully; normal server startup and direct commands remain.
- The detail page presents metadata, parser status and semantic result separately,
  the CLI-style C1/C2/C3 table and vectors, category reasons, case details, associated
  files, exact provider output, previous/next navigation and collapsed technical
  evidence. It reuses `live_result`, `live_presenter` and `interactive_evidence`;
  no second parser, Oracle or scoring implementation was added.
- Actual model digest is shown only from integrity-checked persisted request
  provenance for a dispatched attempt. Setup metadata is not relabelled as proof
  that a model was used. Failures/pending outputs never receive inferred verdicts.
- Evidence links are bound to a run's associated archive entries. No filesystem
  path input or arbitrary file-ID endpoint is introduced. Jinja escaping, CSP,
  GET-only routes, SELECT-only queries and rollback-only connections remain.
  Legacy diagnostic tabs omit private transport/spool metadata; reference excerpts
  identify their source archive and clearly label any private metadata omission.
- Runs has readable status/result rows and global browsing with existing filters.
  Overview adds a latest-run card and avoids selecting unfinished interactive
  containers by default. Interactive Evaluation shows a run-inspection note and
  no meaningless P1/P2/P3 tabs. Original experiment/report views remain available.

## Tests

Comparable starting baseline: **1260 passed / 106 skipped / 5 failed**.
The first restricted run had three additional temporary-directory permission
failures; rerunning those three with repository write permission passed all three.
Final full suite: **1336 passed / 106 skipped / 5 failed**, 41.92 seconds.
All five failures are unchanged baseline qualification/evidence failures:

- `tests/test_cli.py::test_json_preflight_truthful`
- `tests/test_gate_b_closure.py::test_closure_evidence_drift_never_passes`
- `tests/test_operator.py::test_preflight_actual_backend_stays_blocked`
- `tests/test_runtime_evidence.py::test_captured_readiness_preserves_limitations_and_author_gate`
- `tests/test_sensitivity_execution.py::test_final_offline_verification_and_historical_separation`

The Web suite passes **114 tests**. The final source-archive-label clarification
was followed by **27 passing interactive Web tests**. Coverage includes latest
resolution/fallback, exact post-run links, valid correct/incorrect comparisons,
stale prediction suppression after invalid outcomes, reasons, files/raw text,
escaping/private metadata, collapsed technical evidence, blank global filters,
interactive evaluation and unchanged final/full-experiment read-only behavior.
Optional SQL tests remain skipped without an explicitly configured disposable
test database. No SQL test fixture was pointed at the live database.

## Manual verification using existing stored data

- Actual `.venv/bin/rac` → option **3** opened `/runs/20442`, the latest stored
  interactive run. The browser-open audit event records that exact URL; the
  terminal prints `Web UI opened: latest run`.
- Gemma **20440**, `V2-EDX-002`: VALID, PPP → PPP, CORRECT; EDX operation, model,
  P2, repetition, duration, reasons and all required sections visible.
- Incorrect Gemma **20435**, `DEV-01`: VALID, PPF → PPP; the C3 mismatch and
  INCORRECT status are visibly distinct from parser status.
- No interactive parser failure currently exists. Stored final run **11078** was
  inspected read-only: PARSER FAILURE / NO USABLE PREDICTION, PFN reference,
  prediction dashes, no inferred reasons, exact stored malformed output and
  CATEGORY_FIELDS diagnostic. Pending **20436** also has no usable prediction.
- The real shared post-run action was replayed with stored run **20440**, while
  latest remained **20442**. It opened `/runs/20440` exactly. No new model run
  was performed to test this action; fabricated execution tests cover creation.
- **22 live HTTP routes returned 200**, including evidence files, Runs filters,
  interactive Overview/Evaluation, and Experiment 10003 Overview/Evaluation/Runs/Data.
  Provider output and text artifacts equal stored content after HTML unescaping;
  reference metadata uses the explicitly labelled private-field/path projection.
- Browser inspection at **1366 × 900** and the normal narrower **705 px** panel
  confirmed layout, correct/incorrect/failure states and evidence navigation.
  Experiment 10003 has no persisted Web-compatible report: its existing
  unavailable-report message remains truthful; no report was created.

## Preservation and evidence

Before/after read-only snapshots at **10:42–10:54 Europe/Berlin** match across all
**19 tables**, including schema migrations and the actual content hashes of
**10,332 archived files**. All historical rows are unchanged, including
Experiment 10003's **738 runs / 738 attempts / 734 predictions** and Dataset 3's
**82 memberships**. No DB/schema write, model call, thesis access or scientific
artifact modification was performed.

[Verification receipt](docs/web_interactive_run_verification.json) contains the
baseline/final results, checked routes, browser-open targets and preservation
hashes. Raw local logs and snapshots are in `/private/tmp/rac-web-verification/`
and `/private/tmp/rac-web-work/`. Pre-existing dirty changes remain in place.

---

# Interactive model digest fix — 2026-10-07

This bounded follow-up fixes only current-model resolution for bare `rac`.
The earlier UX polish report is retained below. No commit, push, branch switch,
research/thesis edit, parser change or qualified runtime change was performed.

## Digest policy and implementation

The blocker was `live_adhoc_runtime.capture()`: it required a unique installed tag
whose digest equalled the historically configured model row. In the current
Ollama 0.40.0 environment, Gemma and Mistral each have multiple same-tag runner
manifests. `/api/show` identifies the selected manifest explicitly.

Interactive capture now records that selected installed digest (or the unique
tag digest on runtimes without selected-manifest metadata). It retains current
version/show/template evidence and continues to reject ambiguity or changes to
that captured identity before dispatch. A missing model gets the concise friendly
error and returns through the existing main-menu error handler.

The shared runner keeps the original source/selection snapshot intact. It builds
canonical execution requests with the current digest, reuses an unchanged model
row of that identity or inserts a new row through `Repository.model()`, and binds
the new run/schedule/proofs/request inventory to it. New model metadata is covered
by the archived file hashes. The setup additionally records the historical
selection and current run identity. Interactive menus remain one entry per tag.
No existing model row or digest is overwritten. Existing strict `load_runtime`,
`freeze.verify_live`, Main-v2 admission and native context checks are unchanged.

## Tests and one real interactive verification

- Before this fix: **1244 passed / 105 skipped / 5 failed**.
- After this fix: **1256 passed / 106 skipped / 5 failed** in 43.14 seconds.
- The same five qualification/evidence baseline failures remain (listed in the
  earlier report). There are no new failures.
- **12 new focused tests pass**, including different installed digests, current
  metadata persistence, unchanged historical rows, normalized digest-row reuse,
  selected runner manifests, ambiguity, missing-model/main-menu behavior and
  strict qualified digest rejection. The combined relevant suite passes 115 tests.
- One new disposable SQL/Web roundtrip test is skipped because `RAC_SQL_TEST_ENV`
  is not configured. It does not provision or use the live database implicitly.
- All automated model transports are fabricated. The following real attempt was
  separately authorized and was executed exactly once through bare `rac`.

Real run, **7 October 2026, 10:28:04–10:28:17 Europe/Berlin**:

| Field | Verified value |
|---|---|
| Source | Dataset 3, EDX, `V2-EDX-002`, conforming reference PPP; read only |
| Model/runtime | Gemma 3 27B, Q4_K_M, Ollama 0.40.0 |
| Destination | New development Dataset **10006**, `LIVE-ADHOC` Experiment **20009** |
| Run/attempt | Run **20440**, Attempt **20439**, one repetition / seed 101 |
| Parser/result | **VALID**, prediction **PPP**, reference **PPP**, **CORRECT** |
| Duration | **13173 ms**, one model attempt; no retry or repair |
| Historical model | Row **2**, unchanged digest `a418f5838eaf7fe2cfe0a3046c8384b68ba43a4435542c942f9db00a5f342203` |
| Current model | New row **4**, digest `8dda00f4f636a0ae610bf6eae134d59de477256140276ec847510ce898cf910c` |
| Current metadata | Exact show evidence in archive file **23099**, bound into the setup closure |

The menu correctly displayed Gemma as installed. The result appeared immediately
and was then reopened through **Browse previous results**. The DB-backed Web app
returned HTTP 200 for `/runs?experiment=20009`, `/runs/20440`, the raw tab and the
attempts tab; the detail HTML contains the case, Gemma and the stored explanation.
These Web checks used the actual application routes and live SQL through
`TestClient`; no web server was listening on port 8000, and no browser rendering
or screenshot is claimed.

## Preservation evidence and concurrent activity

Before/after content checks confirm **Experiment 10003**, its **738 runs**, **738
attempts** and **734 predictions**, **Dataset 3** and its **82 memberships**, all
**three historical model rows**, and all **10298 pre-existing archived files**
are unchanged. All original API/contract/response/case/reference/prompt/config
rows are unchanged as well. The new run targets only its separate context and
new model identity. No schema migration or destructive database action occurred.

The entire live database was not idle during this work window: pre-existing
interactive run 20438 / experiment 20007 completed at 10:24:34, and separate
interactive experiment 20008 ran at 10:24:57–10:25:09, before this task's single
Gemma attempt. The initial global snapshot therefore differs outside the protected
scope as well; a claim that every pre-existing database row is unchanged would be
incorrect. These observations are not additional attempts performed by this fix.

The exact transcript, test logs, before/after snapshots, protected-scope hashes,
Web response HTML and verification receipt are under `/tmp/rac-digest-fix/`.
Production edits are confined to `live_adhoc_runtime.py` and `live_demo.py`, with
two new targeted test files and the two requested documentation files. Earlier
uncommitted changes are preserved.

---

# Interactive CLI UX polish review — 2026-10-07

This pass polishes the existing bare `rac` flow for compact supervisor-facing use.
It preserves the pre-existing working tree, direct commands, parser semantics and
scientific data. No branch switch, commit or push is part of this task. The guide
is [docs/live_demo.md](docs/live_demo.md); its screen examples are conceptual text,
not fabricated screenshots or claims of measured output.

## Current behavior

- Compact Rich main menu, bold headings, dim supporting text and consistent status badges.
- Dynamic service labels **EDX** and **Resistance**, without exposing storage aliases; one-line method/path/OpenAPI operation descriptions.
- Fully referenced final evaluation cases are the root default. `s` opens other case sets with dataset names and versions; generated interactive contexts are not offered as sources.
- Case-type filtering precedes the case list: conforming, C1, C2, C3, controls/formatting or all cases. References determine categories; metadata only identifies recorded controls and adds descriptions.
- Short case entries with readable key, category, vector and one concise explanation. Missing descriptive metadata uses an HTTP/Content-Type/reference fallback.
- `d NUMBER` opens C1/C2/C3 reference details, overall conforming/inconsistent status and available files. Eight items per page, search, paging and back remain available.
- Model names use readable labels and stored quantization; installation/loading state appears only when available. One repetition is the default; 1–3 remain supported.
- A compact confirmation table keeps P2 automatic and explains that results are stored separately. Enter declines without allocation or generation.
- One result panel shows duration, C1/C2/C3 comparison, vectors, correctness and parser status. Reasons, IDs, attempt metadata and recovery paths require explicit details.
- Parser failures show **NO USABLE OUTPUT** and **No prediction was inferred.** Stale stored prediction fields cannot produce a verdict for a failed run.
- Multiple repetitions use a compact table and one coverage/correctness/agreement summary per model.
- Post-run options provide details, raw response, case files, Web UI, another case, main menu and exit. Previous-result browsing uses the same read-only views.

Normal interactive screens do not use the historical “live demo” or “Live/ad-hoc”
wording. Internal formats, archive paths and existing command names remain intact
where required for compatibility and provenance.

## Case evidence and interpretation

Case categories come from stored reference vectors; construction intent, family
names and model output cannot change reference truth. The presenter combines only
available stored response/provenance/reference fields and operation-specific
OpenAPI metadata. It does not add a hard-coded case-ID explanation table or infer
broader scientific conclusions from descriptions.

Files are loaded through the existing read-only archive/query layer with byte
integrity checks. Available associations can include response body, OpenAPI
contract, original input/request, reference explanation, case provenance and raw
model output. Missing optional artifacts are omitted. Original inputs require an
explicit provenance association plus a resolvable stored identity/hash; filesystem
paths are not guessed.

Viewing displays literal stored content with terminal control characters escaped,
syntax highlighting and a pager where available. Non-UTF-8 content is represented
explicitly as base64. Reference/provenance JSON may be projected through its
stored source pointer. File details disclose archive name, SHA-256, bytes and
pointer without pretending database bytes are local files. Viewing does not modify
the archive or repair parser failures.

## Runtime and final-source isolation

Root selection requests `plan(..., adhoc=True)`. Planning is read-only; optional
version/tags/loaded-model probes are nonblocking metadata reads and do not load
models. A different runtime version produces one short notice. Current installed
identity capture and subsequent drift checks remain enforced after explicit
confirmation; historical digest matching applies to qualified paths, as described
in the later digest-fix verification above.

For an evaluation source, `_execution_context` creates a new development dataset
and membership only after confirmation and successful runtime/context checks.
The membership reuses the selected case/reference; the original Dataset 3 or
other evaluation membership is not updated. The new experiment targets only the
new destination. Source bindings remain captured and checked before dispatch.

Internal setups retain `live-adhoc-setup-v1`, `scientific_evaluation=False` and
`gate_b_complete=False`, with exact request hashes and current runtime/template
evidence. The operational byte-budget guard remains distinct from native-token
qualification. The canonical runner, transport, parser, archive and retry policy
remain authoritative; there is no automatic retry or reconstruction of failed
model outputs.

The existing strict `rac demo run` path remains development-only and rejects final
source cases. Its qualified runtime/native-token checks, explicit arguments and
offline `--dry-run` semantics are preserved. Scientific/final commands retain
their guards. No thesis repository, methodology, final reference or archived
final response/result is an edit target.

## Files affected by this polish

The checkout already contained the root wizard and related uncommitted changes
before this pass. This list describes polish scope, not a clean-base Git diff:

- `src/rest_api_checker/interactive_app.py` — compact root/result/browse flow and file actions.
- `src/rest_api_checker/interactive_menu.py` — Rich menu presentation and optional actions.
- `src/rest_api_checker/interactive_evidence.py` — read-only details and available artifact viewing.
- `src/rest_api_checker/live_demo_cli.py` — final-source selection, categories, short confirmation and output suppression.
- `src/rest_api_checker/live_demo.py` — read-only final-source catalog and separate execution destination.
- `src/rest_api_checker/live_presenter.py` — concise service, operation, model and reference-derived case labels.
- `src/rest_api_checker/live_result.py` — compact single/multiple results and explicit technical details.
- `src/rest_api_checker/live_adhoc_runtime.py` — compact informational runtime notice.
- `tests/test_interactive_app.py`, `tests/test_root_live_wizard.py`, `tests/test_live_demo_cli.py` — root/integration/direct-command checks.
- `tests/test_interactive_case_sources.py` — final defaults and isolated execution with fabricated repositories.
- `tests/test_interactive_evidence.py`, `tests/test_live_presenter.py` — available evidence, integrity and metadata/reference presentation.
- `tests/test_interactive_output_boundaries.py` — root output deduplication and hidden/explicit provenance checks.
- `tests/test_live_result.py`, `tests/test_live_adhoc_runtime.py` — result states, 80/100-column output and compact notice.
- `docs/live_demo.md`, `LIVE_DEMO_CLI_REVIEW.md` — guide and review.

Pre-existing modifications such as the operator dispatch and optional batch
context-proof factory are retained; their original implementation history is
summarized below. No unrelated cleanup or commit is implied by this file list.

## Verification for this polish pass

Pre-change full-suite baseline: **1183 passed, 105 skipped, 8 failed**. Five
failures are the previously recorded qualification/evidence baseline issues;
three additional `main_v2` launcher failures were caused by sandbox execution
permissions. Baseline logs are under `/tmp/rac-ux-polish`.

Final full suite: **1244 passed, 105 skipped, 5 failed** in 40.59 seconds.
The five failures are exactly the pre-existing qualification/evidence failures
listed below. The three additional baseline launcher failures passed once their
fabricated temporary test directories could be created. No new failure remains.
`git diff --check` and direct `rac --help` / `rac demo run --help` passed.

Current logs and checks are stored under `/tmp/rac-ux-polish`:

- `baseline-tests.log`: original sandbox baseline.
- `focused-tests.log`: 211 focused tests passed before the final wrapping/output-boundary additions.
- `verified-final-tests.log`: final complete suite including those additions.
- `launcher-permission-check.log`: the three fabricated launcher tests passed.
- `manual-final.txt`: recorded bare-CLI navigation against the existing database.
- `verification.json`, `before-files.json`, `before-db.json`, `after-db.json`: scope and preservation evidence.

The fixture forbids real HTTP/model inference throughout the test suite. SQL
integration tests remain skipped without disposable-database authorization.
Final-source execution was exercised with fabricated repositories/transport,
including source drift, parser failure, multiple repetitions and preservation of
existing cases, references, membership, experiments and archive bytes. A new final
case was not actually dispatched to a model in this pass.

Completed manual checks (terminal width 80):

1. Bare main menu and dynamic EDX/Resistance service/operation selection: passed.
2. EDX C1/C2/C3/conforming filters and Resistance conforming/C2 filters: passed.
3. Case C1/C2/C3 details, actual response/input files and full archive details: passed.
4. Model availability, default repetition, compact confirmation and decline: passed.
5. Existing final valid result, explicit reasons/IDs, files/raw output and return paths: passed.
6. Existing final parser failure (`V2-RES-020`): no inferred prediction, raw evidence accessible; passed.
7. Main-menu/exit navigation and direct help: passed. Web UI root/deep-link routing is regression-tested; no new web server was needed.

The inspected run and parser-failure screens used stored results only. No new
model call or database write occurred. All **19 database tables / 14331 rows**
have identical before/after content fingerprints, including archive bytes,
Dataset 3, Experiment 10003 and reference/prediction records. Existing local
`artifacts/` files also retained their hashes. Files outside the listed polish
scope retained their starting hashes; pre-existing operator, batch and
implementation-state edits were preserved. Thesis repositories were not touched.
No commit, push or branch switch was performed.

The visual evidence is actual terminal text plus Rich output checks at 80/100
columns; no native-terminal screenshot or screen-reader compliance claim is made.
The guide's screen examples remain explicitly conceptual.

## Earlier implementation history — not re-executed by this pass

The prior root-wizard implementation recorded **1186 passed, 105 skipped, 5
failed**, from an earlier **1098 passed, 105 skipped, 5 failed** baseline. Its
machine-readable record is `docs/interactive_root_cli_verification.json`. Those
figures and the following smoke evidence describe the earlier implementation,
not the new final-case default.

The five documented baseline failures were:

- `test_cli.py::test_json_preflight_truthful`
- `test_gate_b_closure.py::test_closure_evidence_drift_never_passes`
- `test_operator.py::test_preflight_actual_backend_stays_blocked`
- `test_runtime_evidence.py::test_captured_readiness_preserves_limitations_and_author_gate`
- `test_sensitivity_execution.py::test_final_offline_verification_and_historical_separation`

The earlier pass performed one authorized real smoke run: EDX DEV-02,
`mistral-small3.2:24b`, P2, one attempt, Ollama 0.40.0; experiment 20003/run 20433,
15.403 seconds. Parser VALID, reference PPP, prediction PPF, result INCORRECT.
No repair or retry occurred. Its details/raw/Web views were checked, and the
recovery directory was
`~/.local/state/rest-api-checker/live-demo/ff1b2ef78ed34d44890da85732750f07/`.

The prior preservation record reported identical fingerprints for all existing
rows/archive bytes, including Dataset 3 and Experiment 10003 (738 runs, 734 valid
outputs and four retained parser failures). That run added one experiment, run,
attempt and prediction plus ten archive rows, with no new membership or report.
Its 36 development-case/model combinations also received read-only byte-budget
checks. These historical checks do not establish coverage for every final case.

The earlier implementation began on a clean `main`; this polish began with its
changes already present. No old working-tree snapshot is restored by this pass.
Thesis and research repositories remain outside implementation scope.

## Remaining limitations

- Five pre-existing qualification/evidence tests still fail; this presentation pass does not change those scientific/runtime artifacts.
- In explicit plain/no-color mode, content remains readable but bypasses the interactive pager.
- Execution on a final source is covered by fabricated integration tests, not a new real model run.

- Supported model discovery remains limited to the three configured model names; it does not qualify arbitrary new models or contracts.
- Interactive runtime/context safety is operational, not scientific runtime qualification. Large inputs or metadata drift can block a run.
- Final cases are read-only sources; selecting one does not authorize altering the scientific evaluation or relabelling its references.
- Input/request artifacts appear only when their real association resolves in the archive. A historical provenance path alone is insufficient.
- A parser-valid answer can be incorrect; the UI preserves that distinction and never repairs invalid outputs.
- Web UI occupies the terminal. Occupied ports are reported without stopping another listener; no background server manager is added.
- Interrupted or ambiguous attempts are not retried/resumed automatically. Explicit details retain their available traceability.
- Optional SQL tests remain skipped without disposable credentials. Baseline failures and final verification limits must remain visible in the completion record.
