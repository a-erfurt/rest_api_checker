# Final evaluation candidate materialization

Authority: exact plan pair at research commit
`e549cad575b34ada71b282fb0c2876acbb146ce0`, seven accepted base reviews
through `3d21fef7743856bbfad51bcc306fa8499b0f2f90`, and the author's
explicit authorization to materialize the 14 registered candidates only.

Run the standalone tool directly with Python 3.12. It uses standard-library
JSON decoding only and never imports the application, Oracle, validators,
providers or database. The existing development constructor invokes the Oracle
and cannot be used under this phase boundary.

```sh
.venv/bin/python -B tools/final_evaluation_candidates/prepare.py \
  --research /path/to/bachelor_rest_api_checker \
  --technical /path/to/rest_api_checker \
  --output /new/staging/directory \
  --materialized-at FIXED_UTC_TIMESTAMP
```

Before writing, the tool verifies the committed plan, source closure, all
prerequisite package bytes, seven manual-review bindings, base recipe identity,
312 comparison source descriptors, exact candidate/group mappings and exclusions.
The output must not exist. The operator must verify the technical checkout is
clean at the recorded implementation commit and that task authorization remains
applicable. No invocation grants reference or dataset-release authority.

The historical implementation-state documentation is bound at its original
commit and at the approved base milestone. A later committed prefix may describe
this mechanical step while preserving every historical byte. All executable
sources used from the earlier milestone remain unchanged and hash-bound.

Body replacements/deletion use one UTF-8 byte splice. Prefix/suffix bytes remain
unchanged; independently edited parsed trees verify that no second field changed.
Natural retention and controls copy exact source bytes. Status/media changes
preserve the entire body. Metadata is research-only, with no final reference
vector; model evidence files contain only the raw response layers. Request and
OpenAPI evidence are hash-bound pointers, never network acquisitions.

The output contains per-case bodies/envelopes/metadata/traces, a manifest, source
lock, construction and exclusion reports, a human-readable report, an integrity
record and a hash inventory. All 14 candidates remain
`MATERIALIZED_REFERENCE_NOT_REVIEWED`; order is the planned construction/review
order only. No DB import, final membership/order, dataset freeze or Main run.

Verification: 48 focused tests passed (17 base serializer + 31 candidate tests),
using fabricated fixtures and no Oracle evaluation. Run:

```sh
.venv/bin/python -B -m pytest tests/test_final_evaluation_bases.py \
  tests/test_final_evaluation_candidates.py -q -p no:cacheprovider
```

These are the complete relevant safe materialization suites. The full technical
suite and the earlier construction suite execute Oracle functions and are
intentionally excluded. Qualification/Oracle code and expectations are unchanged.
The research handoff separately records two byte-identical materializations and
an independent verification of the actual artifacts, without contract verdicts.
