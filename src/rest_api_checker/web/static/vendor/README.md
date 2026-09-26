# Local browser dependencies

Pinned upstream distributions; no frontend build step or CDN request at runtime.
Their license notices are retained alongside these files.

| File | Upstream distribution | SHA-256 |
| --- | --- | --- |
| `htmx-2.0.4.min.js` | https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js | `e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447` |
| `chart-4.4.8.umd.js` | https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.js | `e4cf4d144b222634f2e64ff707cd57b953f8de4b65b231cd5ac6bde114648e4d` |

Chart.js is loaded only for a completed Evaluation view. Its development source
map is not shipped; this does not affect rendering. HTMX is used for operational
Overview polling. App-specific scripts perform presentation and navigation only.
