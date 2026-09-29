# Final evaluation base preparation

Authority: research `final_case_construction_plan_v1.md/.json` at
`e549cad575b34ada71b282fb0c2876acbb146ce0`, and the 2026-09-27 explicit
base-only authorization. No scientific recipe or reference policy is changed.

Run the standalone standard-library tool directly, without importing the
application package. It emits six BT directories and a manifest, never FC
artifacts. Five retained controls remain prospective dependent IDs only.
HTTS-PO-0003 is bound to its existing archive; it is not copied or counted as a
seventh constructed base. The tool never imports/calls the Oracle or validators.

```sh
python tools/final_evaluation_bases/prepare.py --research /path/to/research --output /new/staging/directory --technical-commit COMMIT --materialized-at FIXED_UTC_TIMESTAMP
```

Supply the verified implementation commit and preserve the same construction
record timestamp for reproduction. The operator must verify commit identities,
complete source closure and exclusion corpus separately before publishing these
base artifacts. The tool checks the bound plan pair and direct recipe sources;
it is not an exclusion classifier or reference eligibility decision.

Bodies are compact UTF-8 with insertion order and no trailing newline. Status
and raw Content-Type sidecars also have no trailing newline. Recipes and
metadata are UTF-8 JSON with two-space indentation and a final newline.
The output directory must not already exist. Duplicate body hashes hold the
entire in-memory construction before writing. Existing paths are not overwritten.

Targeted verification uses fabricated serializer fixtures, never the six study
bodies as Oracle qualification fixtures. Run only:

```sh
python -m pytest tests/test_final_evaluation_bases.py -q
```

Focused result on 2026-09-27: **17 passed**.

The full suite is deliberately not executed under the current explicit Oracle
and network prohibition. Existing Oracle/construction code is untouched; no
claim of a new qualification run is made. The next phase requires separately
authorized Oracle execution and later independent manual review.
