# Web UI verification — 2026-09-26

Implemented on evaluator/CLI baseline
`aa4001de1e311011f1ea264cd68e3213e8889963` in
`feature/read-only-research-ui`. No merge or evaluator reconciliation was needed.

## Automated checks

- Full suite: **579 passed**, no failures/errors/skips, 146.42 seconds.
  Includes **71 SQL Server integration tests**, existing Q01–Q26 qualification,
  disposable SQL/backup coverage and the new query integration tests.
- Focused web suite after final launcher review: **87 passed**.
- Offline sdist and wheel build passed. Wheel contains all templates, static
  files, pinned browser libraries/licenses and the web console entry point.
- `rest-api-checker-web --help` and `git diff --check` passed.

Full-suite command (private credentials remain outside the repository):

```sh
RAC_SQL_TEST_ENV=/private/tmp/rac-sqlserver-environment-20260926/credentials.env \
RAC_SQL_TEST_BACKUP_DIR=/private/tmp/rac-sqlserver-persistence-20260926 \
.venv/bin/python -m pytest tests tools/sqlserver_environment/test_probe.py -q
```

Ordinary tests remain usable without SQL credentials; the established opt-in
skips external SQL tests. All UI records, responses and provider evidence in
tests are fabricated. No study request was dispatched and no Ollama inference
was executed. SQL tests used disposable databases through the existing fixture.

Coverage includes empty/running/completed Overview, unavailable/malformed/missing
reports, missing selection, refusal of partial evaluation, all three verdicts,
parser/technical failures, unfinished predictions, route availability, server
pagination/filter/search, every data/artifact route and evidence tab, hashes,
hostile HTML/script escaping, polling stop/error states and read-only boundaries.
Regression fixes during development included test-package name collision,
dictionary `items` template lookup, blank optional form filters, scoped Data
navigation and explicit missing-selection rendering. Final runs have no failures.

## Browser review

Native Chrome with a local fabricated fixture at `127.0.0.1:8765` was inspected
through actual rendered pages, at responsive desktop widths **1120**, **1440**
and **2560** pixels. Reviewed Overview, completed Evaluation, Runs/filtering,
run/raw detail and Data inventory/detail. Grouped bars rendered with the fixed
RUB palette; tables and controls remained usable without page-level horizontal
overflow. Sidebar collapse, Focus Mode, long-content expansion and Technical
Details were exercised. Hostile model markup stayed literal displayed text.
Operational fragment requests refreshed every 3 seconds. Stopping the fabricated
preview server produced the visible polling-paused/stale-values message.
Browser print preview
rendered the scientific content without the sidebar; the chart section is kept
together by print CSS. No PDF export engine or screenshot artifact was created.

A transient Data error during browser review came from running old app code
against a newly edited template helper; restarting the preview resolved it.
Browser developer tools also requested absent favicon/source-map resources;
these do not affect the application. Cross-browser and phone testing were not
performed. Visual review used fabricated records, not a real study database.

## Final boundary review

Handlers expose only GET routes and explicit read queries. SQL is parameterized,
run/data lists use OFFSET/FETCH, and large evidence is loaded on relevant detail
tabs. There is no mutable repository, orchestration, provider or report-generation
API in the web layer. Startup does not connect, migrate, import or create records;
request connections roll back and close. Raw content is escaped with Jinja,
chart data uses safe JSON serialization, and scripts are local under a restrictive
content security policy.

Scientific values, denominators, diagnostics and ranking trace come from the
verified immutable report. The web formats percentages and compares displayed
reference/prediction tokens; it does not recompute scientific scores or choose a
winner. Pending experiments never display scientific evaluation. Failures remain
distinct from semantic predictions and stay in authoritative denominators.
No scientific source, frozen artifact, migration or evaluator behavior changed.

Known limits follow the existing backend: only `comparison-evaluation-v1` is
supported; no persisted Gate-B summary or worker heartbeat exists. Other phases
and absent evidence are shown explicitly without invented state or metrics.
