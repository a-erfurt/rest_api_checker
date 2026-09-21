# Validator spike and initial oracle qualification

Date: 2026-09-21. Scope: a deterministic reference oracle for the two frozen
response contracts, not a scored competing baseline or an experiment dataset.

## Authority

**FACT FROM SOURCE:** Research commit
`7e35cd24f7e1d53ee25ff47ca93143194f446032` contains the four supplied methodology
files and Alex Erfurt's appended Author Review of Q01–Q26: 26 approved, zero
corrected, zero unresolved. Earlier draft-status paragraphs remain historical
text; the appended sign-off and the explicit implementation request govern this
milestone. No research file was edited and no new human review is claimed.

The exact paths and SHA-256 values for all four methodology files are retained
in [provenance.json](../tests/contracts/provenance.json). The frozen contracts
were verified against both working-tree and committed bytes before copying:

| Contract | SHA-256 |
|---|---|
| EDX OAS 3.0.4 | `4fb9c2bf81b401463dcd66f463c214a3019b75b48f0a88db1cf541a770ea4fbc` |
| HTTS OAS 3.1.0 | `084b2d72929226f0984cda1ce7758c8e7d9fb1aa7e1001e308160da440828e42` |

The selected operations are POST `/edx/validation/body` and POST
`/resistance/validation/file`. The package holds other operations. Contract
copies remain byte-identical; test-session guards check both hashes before
loading and after running tests. Tests access only repository-local copies.

## Candidate comparison before selection

**FACT FROM SOURCE:** The maintained schema-validator package exposes separate
OAS 3.0 and 3.1 validator classes. Its current release is 0.9.0. The explicit class
argument matters because its default targets a newer OAS version.
[Package documentation](https://pypi.org/project/openapi-schema-validator/).
The current `jsonschema` release inspected was 4.26.0.
[Release record](https://pypi.org/project/jsonschema/).

| Candidate | Assessment and observed result |
|---|---|
| `openapi-schema-validator` 0.9.0, `OAS30Validator` | Executed probes accept `nullable` string null, reject Boolean/string as integer, enforce required/extra-property/array assertions, and resolve nested local references. Appropriate for the actual EDX schema subset. |
| Same package, `OAS31Validator` | Executed probes preserve 2020-12-style empty schemas, `anyOf`, array/item and required assertions. Appropriate for the actual HTTS schema subset. |
| `jsonschema` 4.26.0, `Draft202012Validator` | Executed structural probes pass, but unmodified OAS 3.0 `nullable` is ignored and null is rejected. A single generic 2020-12 validator is therefore unsuitable for EDX. This is an expected dialect incompatibility, not a disagreement with a qualification expectation. |
| `openapi-core` | Documentation-only assessment; not installed or benchmarked. Provides request/response validation and unmarshalling with integration interfaces. Its broader orchestration is unnecessary for this milestone's explicit selection/applicability policy. No claim that it is incorrect or incapable. [Official documentation](https://openapi-core.readthedocs.io/). |

**DESIGN DECISION — technical:** Select `openapi-schema-validator==0.9.0` with
explicit `OAS30Validator` for EDX and `OAS31Validator` for HTTS. Pin
`jsonschema==4.26.0` and `referencing==0.37.0` as directly used dependencies.
A local-only `referencing.Registry` provides the unchanged contract as reference
context; there is no remote retrieval callback. C1/C2, UTF-8 JSON parsing and
applicability are small explicit functions. Schema assertions remain delegated
to the established validator. No defaults, repairs or value coercion are applied.

The first isolated spike executed **41 passing probes** before oracle integration
and library selection. The same probes remain in `tests/test_validator_spike.py`.

## Executed evidence

Environment: CPython **3.12.14**, uv **0.12.17**, pytest **9.1.1**. `uv.lock`
records all resolved transitive versions and artifact hashes. The package build
backend is pinned to hatchling **1.29.0**. Reproduction commands are in README.

| Requirement | Evidence |
|---|---|
| OAS 3.0 nullable | Dialect comparison; Q07 and nested schema checks |
| `additionalProperties: false`, literal names | Structural probes; Q03/Q10 |
| Nested `$ref`, arrays/items | Two-dialect reference probe; Q08–Q10, Q14–Q21 |
| Empty OAS 3.1 schema | Q11/Q12/Q22; object, array, string, number, Boolean, null probes |
| Required members | Q17 and direct library probe |
| HTTS location `anyOf` | Q14/Q20; string/integer accepted, Boolean/null/array rejected |
| Non-coercing integer handling | Q04–Q06 and three-validator probes |
| Malformed JSON outside schema checking | Q13; empty/invalid UTF-8/trailing values/NaN/Infinity probes |
| Exact/range/default precedence | Synthetic HTTS-shaped contract probes; no changes to frozen copies |
| Declared alternative media | C2 component acceptance for EDX `text/plain`/`text/json`; full result held |
| Technical and unresolved paths | Missing schema, broken/remote refs, unsupported keywords, duplicate names, invalid headers, simulated library error |
| Repeatability and immutability | Repeated structured results, unchanged body/document/file bytes, hash guards reject modified copies |

**Observed result:** **141 tests passed, 0 failed**, including all **26/26**
author-approved Q cases. Their expected composition remains **12 CONSISTENT /
14 INCONSISTENT**. The remaining 115 tests include the 41 spike probes, fixture
inventory checks and implementation boundary probes; they are not additional
human annotations. A separate literal comparison against the committed review
confirmed all 26 bodies, operation contexts, expected vectors and overall labels.
Dependency compatibility checks passed.

**INFERENCE:** These results support use within the checked profile. They do not
prove universal OAS conformance, independent manual truth for future cases, or
100% oracle accuracy. There was no mismatch with Q01–Q26 and no expectation was
rewritten. Schema and representation diagnostics remain separate from labels.

## Limits and explicit holds

- Only the two named operations and exact versions 3.0.4/3.1.0 are admitted.
  Exact → range → default is implemented and tested, although the frozen
  operations need only exact entries. Media wildcards and parameterized contract
  keys are held; the frozen response maps do not require them.
- Media type/subtype case and outer whitespace are normalized. Only the
  `application/json; charset=utf-8` parameter form is admitted, with HTTP token
  case normalization. Quoted charset, other charset values, extra parameters,
  missing/malformed/conflicting headers and bodyless branches are held.
- EDX `text/plain` and `text/json` are preserved as declared media alternatives.
  Decoding remains an **OPEN QUESTION**; matched alternatives raise
  `UNQUALIFIED_REPRESENTATION`, without C3 N/A or any completed vector.
- Supported schema keywords are explicitly bounded to the reachable snapshot
  subset (type, properties, required, additionalProperties, items, anyOf, local
  `$ref`, OAS 3.0 nullable, title/description and EDX int32 format). Unknown
  keywords, dialect overrides, absent/malformed schemas, reference siblings,
  recursion and external/unresolved references are held before body validation.
  This preflight is an eligibility guard, not a custom schema validator or a
  general specification linter. Unrelated schemas in the document are not audited.
- **Measured format behavior:** Without a format checker the library accepts
  integer `2147483648` against `integer/int32`. Its OAS 3.0 format checker detects
  overflow. The oracle uses that checker only to hold such cases as
  `UNQUALIFIED_FORMAT_CASE`, not to invent qualified format-only C3 faults.
  Other formats are unqualified and held. OAS 3.0's validator rejects floating
  representations such as `0.0` as integer; these are held as
  `UNQUALIFIED_INTEGER_REPRESENTATION` rather than admitted as scientific faults.
- JSON decoding rejects NaN/Infinity as invalid representations; duplicate object
  names are held. Numeric overflow/underflow, loss of decimal value in float
  conversion and the interpreter's very-long-integer limit are held. These
  numeric-edge cases remain outside the protocol's initial dataset profile.
- Schema-assertion diagnostics are deterministically sorted and use stable codes,
  keyword names and instance/schema paths; raw library prose is not a label.
  Unexpected validator errors propagate as execution errors with the cause,
  never as scientific FAIL. No final dataset, label audit or experiment freeze
  follows merely from passing this suite.

**Protocol deviations:** None within Q01–Q26 and the admitted profile. Additional
probes and conservative holds are technical boundary checks, not new human
research decisions. The supplied fault model's conformant-parent precondition
remains applicable to later work; no fault generator has been implemented.

**Next recommended step (not implemented):** Define the concrete, author-reviewed
parent/variant fixtures for the admitted fault families and any supplemental
cases, then implement a small provenance-preserving fault generator. Recheck each
actual mutated response with this oracle without fault IDs or intended labels;
resolve unexpected outcomes and audit the development references before release.
