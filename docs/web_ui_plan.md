# Read-only research interface implementation plan

Reconnaissance completed against the current schema, CLI, orchestration,
inspection helpers, evaluator, tests and protocol v1 §6. This change presents
existing scientific records; it does not change the study or schema.

1. Reuse SQL connection configuration, datetime adapters, JSON pointers and
   immutable-file verification conventions. Consume persisted
   `comparison-evaluation-v1` report ratios, cells, diagnostics and ranking.
   Do not call report creation, preflight execution or request reconstruction.
2. Add `web/app.py`, `web/queries.py`, `web/presentation.py`, Jinja templates,
   small CSS/JavaScript and pinned local HTMX/Chart.js distributions. Add a
   local-only `rest-api-checker-web` entry point and necessary web dependencies.
3. Implement explicit SELECT-only query methods. Aggregate operational counts;
   paginate/filter runs in SQL; fetch evidence only on detail pages. Close and
   roll back read connections. Route handlers receive only read methods.
4. Routes: Overview, Evaluation, Runs/list and detail, Data datasets/cases/
   references/artifacts and dedicated detail pages. Carry experiment selection
   in URLs; prefer persisted started/unfinished, then latest completed.
5. Replace only the Overview operational fragment every 3 seconds while
   persisted started/unfinished. Stop after completion or failure; offer an
   explicit polling-paused state. No live scientific recomputation.
6. Load Chart.js only on Evaluation. Feed grouped bars from stored ratios;
   restrict dimension/metric combinations to those already present. Format
   percentages server-side and keep exact numerator/denominator visible.
7. Test empty/running/completed/unavailable pages, all outcomes, pagination and
   filters, details, hostile evidence, polling, no writes/inference, persisted
   report presentation and read SQL. SQL tests retain the existing opt-in.
   Check real browser rendering with fabricated data at desktop widths.
8. Validated assumptions: IDs are BIGINT; experiment kinds are comparison,
   sensitivity and evaluation; no state enum/heartbeat or persisted Gate-B
   report exists. Started/unfinished is not proof of a live worker. Only the
   comparison report format currently exists. Missing readiness or future
   evaluation formats remain explicitly unavailable. Dataset records have no
   approval workflow. Existing raw inspection calls orchestration and is not
   reused. Existing preflight commits and is not called from web requests.

Scope excludes research edits, frozen-input changes, migrations, execution,
inference, prompt selection changes, and new scientific metrics.
