# Read-only research web UI

The web interface inspects persisted study records and immutable evaluator
reports. Experiment execution, reconciliation, configuration changes and report
creation remain CLI-only. No database is created or migrated at web startup.

## Start locally

```sh
uv sync --locked
uv run --locked rest-api-checker-web \
  --env-file /path/to/private/credentials.env \
  --database rest_api_checker
```

Open **http://127.0.0.1:8000**. The default binding is loopback; no authentication
or frontend build is needed. `--port` and `--host` are optional. Configuration
can also be supplied through `RAC_WEB_ENV_FILE` and `RAC_WEB_DATABASE`.

Use the existing [SQL Server configuration](persistence.md): ODBC Driver 18,
a private mode-0600 environment file containing `RAC_SQL_PORT`,
`RAC_SQL_PASSWORD`, and optionally `RAC_SQL_USER`. The database must already
exist with the current schema. A principal restricted to SELECT on the existing
tables is suitable for the web UI. Do not copy credentials into the repository.
No database configuration is needed to start the server; pages then display an
explicit unavailable state. The UI never contacts Ollama.

## Pages and inspection

- `/` (also `/overview`): experiment selection, operational progress, recent
  runs, attention links, recorded phases and compact schema/readiness context.
- `/evaluation`: completed persisted reports, prompt tabs, authoritative metric
  counts, C1/C2/C3 matrix, grouped bars, failure/stability/ranking and diagnostics.
- `/runs` and `/runs/{id}`: SQL filters/search and pagination (50 rows by default),
  reference/prediction comparison, reasons and tab-specific persisted evidence.
- `/data/datasets`, `/data/cases`, `/data/references`, `/data/artifacts`:
  paginated inventories and dedicated `/{id}` detail pages. Artifact `kind`
  selects models, prompts, configurations, contracts, experiments, reports or
  files. Dataset details show up to 200 relationships and disclose that limit.

Experiment selection is carried in URLs. The initial selection prefers a
recorded started/unfinished experiment, then the latest finished experiment.
There is no worker heartbeat in the schema: started/unfinished does not establish
that a worker is currently alive. Overview polls only its operational fragment
every **3 seconds**, stops after completion, and displays **Polling paused** on
failure. Reload after restoring connectivity. Other pages use normal navigation.

Scientific evaluation is withheld until the experiment is recorded finished and
all planned logical runs have outcomes. Display requires a supported, verified
persisted report; opening a page never creates one. The current backend supplies
`comparison-evaluation-v1`. Sensitivity and final-evaluation records can be
inspected, but no unsupported evaluation format or metric is invented. Missing
selection/readiness evidence is explicitly unavailable. The UI does not execute
Gate-B checks, verify live models or infer a prompt winner from ranking order.
Zero, unavailable and not applicable remain distinct.

## Screenshots and printing

Collapse the sidebar to give tables more space. **Focus Mode** hides navigation,
filters and secondary context; use **Exit focus** or Escape to restore them.
Use the browser's **Print / Save as PDF** for a landscape layout without chrome.
Expand any diagnostics or Technical Details you want included before printing.
Long evidence uses escaped monospace previews with **Show full** and local
scrolling; exact identifiers have copy buttons. Charts and polling libraries
are pinned local assets, so the interface needs no CDN or external fonts.

## Verification and maintenance

```sh
uv run --locked pytest tests/web tests/persistence/test_web_queries.py -q
```

Ordinary UI tests use fabricated in-memory records and block real inference.
SQL query tests follow the existing `RAC_SQL_TEST_ENV` opt-in; see the README
for the full SQL/backup command. `tests/web/browser_fixture.py` is a fabricated
visual-review fixture, not a source of study records. See
[implementation plan](web_ui_plan.md) and
[verification record](web_ui_verification_2026-09-26.md).

`web/queries.py` exposes only bounded SELECT operations to handlers. Connections
are rolled back and closed. `web/presentation.py` formats stored ratios and
projects existing report cells; neither templates nor JavaScript score results.
New report formats must be reconciled to their authoritative backend schema
before adding presentation support. This implementation already includes the
evaluator CLI baseline `aa4001de1e311011f1ea264cd68e3213e8889963`.
