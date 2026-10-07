# RestApiChecker interactive CLI

Start the application:

```sh
cd /Users/aerfurt/University/Bachelor/rest_api_checker
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/openssl@3/lib
.venv/bin/rac
```

The application checks an **already stored API response** against its existing
OpenAPI contract. It does not send another request to EDX or Resistance. Case
selection, evidence viewing and previous-result browsing are read-only. Only
explicit confirmation starts a separate model run.

## Main menu

The following text illustrates the menu; it is not a captured screenshot:

```text
RestApiChecker
Choose an action:

1  Run API response check
2  Browse previous results
3  Open Web UI
4  Exit
```

Choose a displayed number and press Enter. Menu positions are not database IDs.
Enter selects the first option; `q` goes back. `Ctrl-C` or end-of-input cancels
selection safely. Confirmation defaults to **No**: only `y` or `yes` starts a run.

## Guided response check

| Step | Display and behavior |
|---|---|
| Case set | **Final evaluation (default)** when a fully referenced final case set is available. At service selection, `s` opens **Other case sets** with dataset names and versions. |
| Service | **EDX** — Document/data-stream validation service; **Resistance** — File validation service. Services remain dynamically discovered. |
| Operation | Method, actual OpenAPI path and a concise summary. Paths retain their contract-defined casing. |
| Case type | Choose conforming, C1, C2, C3, controls/formatting or all cases before opening the case list. |
| Case | Readable case key, short category label, reference vector and one explanation line. `d NUMBER` opens details and files. |
| Model | Friendly model name, stored quantization and installed/loaded hints when those checks succeed. |
| Repetitions | Repeat the same case/model configuration 1–3 times; default **1**. |
| Confirmation | Compact Service / Operation / Case / Model / Prompt P2 / Repetitions table. Enter cancels without creating a run context. |

Development cases remain available through the optional case-set selector. A
final set takes precedence over development; if no fully referenced evaluation
set is available, the menu truthfully shows the available development source.
Generated interactive run contexts are excluded from the source selector.

**P2 is automatic and unchanged.** The root path uses one configured model per
check, compatible stored D07 settings, `format_json`, a 512-token output budget,
and the existing repetition seeds 101/202/303. None of these settings requires
entering a database ID.

### Case types and references

| Filter | Meaning |
|---|---|
| ✓ Conforming / baseline | The stored reference is PPP. |
| C1 Status fault | The stored reference is FNN: the HTTP status is not covered. |
| C2 Media-type fault | The stored reference is PFN: Content-Type is not documented for the covered response. |
| C3 Schema fault | The stored reference is PPF: the JSON body fails the documented schema check. |
| Controls / formatting | Explicitly recorded control or formatting metadata; the actual reference remains visible. |
| All cases | All available cases for the selected source, service and operation. |

`P` means PASS, `F` means FAIL, and `N` means not applicable. Categories come from
the stored reference vector; mutation intent and case names never determine
reference truth. Control metadata only adds a browsing filter and cannot change
a verdict. A filter without matching cases reports that fact and returns to the
case-type menu.

Case explanations use available stored metadata and reference diagnostics. If a
concrete explanation is unavailable, the fallback identifies the stored response,
HTTP status, Content-Type and reference vector. Construction paragraphs and
internal IDs stay out of the normal case list.

Long menus display eight options per page. Use `n` / `p` to change page, `/text`
to search labels, and `/` to clear a search. These controls also work when browsing
previous results.

### Case details and files

At case selection, enter `d NUMBER`, for example `d 1`. The read-only panel shows:

- Case key and service/operation.
- HTTP status, Content-Type and reference vector.
- Overall **CONFORMING**, **INCONSISTENT**, or **UNAVAILABLE** when no known vector exists.
- C1 Status, C2 Media Type and C3 Body Schema as PASS / FAIL / N/A.

The **Files / evidence** menu lists only associated artifacts that are actually
available: observed response body, OpenAPI contract, original input/request where
bound provenance resolves to an archive artifact, reference/explanation and case
provenance. After a run it can also show the archived raw model response.

Select a file to view it with terminal syntax highlighting and a pager where
available. `d NUMBER` within that menu shows archive name, SHA-256, byte count and
any source pointer. Database archive content is not presented as a guessed local
filesystem path.

Archive integrity is checked against stored bytes before display. Terminal
control characters are escaped and markup is displayed literally; binary content
uses an explicit base64 representation. Reference/provenance views can show the
JSON record selected by a stored source pointer. Viewing never repairs, rewrites
or reclassifies the underlying evidence.

## Results and next actions

A single run produces one compact panel. This illustrative comparison is not a
claim about a particular stored case or model run:

```text
✓ Run completed   14.4 s
Case: CASE-EXAMPLE    Model: Gemma 3 27B

Check           Reference   Prediction
C1 Status       PASS        PASS         ✓
C2 Media Type   PASS        PASS         ✓
C3 Body Schema  FAIL        PASS         ✗

Reference: PPF   Prediction: PPP
Overall: ✗ INCORRECT   Parser: ✓ VALID
```

Parser validity does not imply correctness. Failed or missing parsed output shows
**Parser: ✗ NO USABLE OUTPUT** and **No prediction was inferred.** A stale or
invalid output is never converted into a category prediction. Multiple repetitions
use a compact table with one summary of usable output, correctness and vector
agreement; full panels and category reasons are not repeated.

The post-run choices are:

- **View details** — stored category explanations, run/attempt identifiers and available recovery information.
- **View raw model response** — the archived provider output, including parser failures.
- **View case files** — response, contract and other available evidence.
- **Open in Web UI** — the selected run's read-only page.
- **Run another case**, **Main menu**, or **Exit**.

Internal IDs, recovery paths and model reasons are absent from the default result.
They remain available through explicit details. Historical storage names and
recovery-directory names are implementation details, not menu labels.

## Runtime policy and separate storage

A runtime-version difference is a compact, nonblocking notice in the root flow.
Optional local version, installed-model and loaded-model probes neither load a
model nor generate output. If a display probe fails, selection and cancellation
still work.

After confirmation, interactive execution resolves the selected tag to its
**currently installed digest**, even when it differs from the historical
qualified digest. When Ollama lists multiple runner variants for one tag, the
selected manifest reported by `/api/show` determines the identity. Ambiguous
metadata blocks safely instead of reporting an installed tag as missing.

The new context archives the actual Ollama version, model/show/template metadata,
and configured-versus-installed identity mapping. Its run and request metadata
use an existing matching model row or a newly inserted current-identity row;
historical model rows are never updated. Each tag still has one menu entry.
A genuinely missing tag reports, for example,
`✗ Gemma 3 27B is not installed in Ollama.`, then returns to the main flow.

The conservative byte budget remains an operational safeguard, not native token
measurement or scientific runtime qualification. Changes to the captured current
runtime/model/template before dispatch, incompatible configuration or an excessive
budget still block execution. **Qualified thesis/final runs and strict
`rac demo run` retain their exact historical digest/runtime guards.**

When the selected source is a final evaluation set, execution allocates a new
isolated development dataset/membership and a new non-scientific run context.
It reuses the selected case, immutable response and stored reference without
updating their rows or source membership. No new context is allocated during
selection, details viewing or declined confirmation. Dataset 3, Experiment 10003,
final references and archived final responses/results remain unchanged.

Internally, root runs retain the separate `LIVE-ADHOC` setup and
`scientific_evaluation=False`; browsing labels these contexts **Interactive run**.
The canonical attempt runner, strict parser and archive preserve output and
provenance. No automatic retries or output repair are added. The strict direct
commands retain their existing qualification guards.

## Browse previous results and Web UI

**Browse previous results** lists named contexts, timestamps when available and
completion counts. Select a context, search a readable case/model label, and open
a result. This uses the same compact comparison, details, raw-output and case-file
views. All browsing is read-only, including the final evaluation.

**Supervisor flow:** `rac` → run an API response check → inspect the CLI result
→ **Open in Web UI** → inspect the same persisted run. The post-run action opens
that exact result, even when a newer interactive run exists. No experiment or run
ID needs to be entered.

Main-menu **3 Open Web UI** opens the newest stored interactive run directly.
The existing schema has no user/owner field, so lookup uses all explicit
`LIVE-ADHOC` / `LIVE-DEMO` contexts in the configured database, excluding Dataset 3
and Experiment 10003. Started/attempted runs take precedence over untouched planned
repetitions; ties use newest stored run identity. With no interactive result the
CLI opens Overview, and the page's **Open latest run** action falls back to Runs.

The run page shows service/operation, case, readable model, prompt, repetition,
duration and separate parser/semantic statuses; the C1/C2/C3 reference/prediction
comparison uses the same presentation rules as the CLI. Reasons, case details,
associated response/contract/input/reference files and the exact raw provider
response appear on the same page. IDs, actual captured model digest (when stored),
runtime version and allowlisted diagnostics stay in collapsed **Technical Details**.
Invalid output is never repaired or interpreted as category verdicts. Missing
metadata stays unavailable. Binary evidence shows metadata; source-archive excerpts
are identified explicitly, and private metadata/local paths are omitted from the
reference metadata viewer without altering storage.

Use **Previous run**, **Next run**, **Back to runs** or **Open latest run** to browse.
Overview has a latest-run card; interactive contexts use friendly display labels
and individual-run links. Their Evaluation page explains that aggregate evaluation
is for completed batches. Full experiment routes remain available and read-only.

The launcher uses the configured loopback address (default
`http://127.0.0.1:8000`) and may check/start its configured SQL container. A newly
started server occupies the terminal; `Ctrl-C` stops it and returns to the menu.
An already running listener is opened only after it identifies as this read-only
UI; an unknown listener is left untouched and its URL is printed for inspection.
A successful interactive browser launch prints only a short confirmation.

## Rehearse without calling a model

Start bare `rac`, choose **Run API response check**, and follow **Final evaluation
→ EDX or Resistance → operation → case type → case → model**. Explore `d NUMBER`
and its evidence menu first. Accept one repetition, inspect **Ready to run**, then
press Enter at `Run now? [y/N]`. Next browse an existing result and its files, then
exit. Selection and declined confirmation create no run or destination dataset.

Only type `y` when a real model run is intended. A model smoke run is separate
from automated tests; [the review](../LIVE_DEMO_CLI_REVIEW.md) records what was
actually verified in each implementation pass.

## Existing direct commands

Help never enters the wizard:

```sh
.venv/bin/rac --help
.venv/bin/rac db status
.venv/bin/rac dataset list
.venv/bin/rac demo run --help
.venv/bin/rac web --open
```

`rac demo run` remains the existing **strict qualified, development-only** path.
It excludes final source cases, requires its qualified runtime binding, and
retains explicit `--case-id`, `--model-id`, `--yes` and optional multiple-model
selection. Its `--dry-run` is offline and read-only, without runtime contact or
generation. Bare `rac` uses the separate interactive path described above.

If SQL is stopped, `rac db start` checks/starts the existing configured container;
it does not create a new database. The root application does not silently
initialize or migrate SQL. Keep existing private credentials and
`~/.config/rest-api-checker/config.toml`; preserve the OpenSSL environment setting
above if the ODBC connection cannot load its SSL library.

Do not use `evaluate comparison` for an interactive subset: that command belongs
to the separately approved scientific comparison workflow. Automated tests use
fabricated responses. Optional SQL integration tests require disposable test
credentials and must never target the scientific database. Test totals and
remaining limitations are recorded in [the review](../LIVE_DEMO_CLI_REVIEW.md).
