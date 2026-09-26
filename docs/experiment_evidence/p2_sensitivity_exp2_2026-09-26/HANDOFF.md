# Experiment 2 — approved P2 sensitivity execution and diagnostic D11 handoff

Evidence labels: FACT FROM OBSERVATION describes retained execution/SQL evidence; FACT FROM PROTOCOL describes the existing approved method. No new scientific decision, author interpretation, prompt selection, or Gate C approval is recorded here.

## FACT FROM OBSERVATION — post-merge and authorization

- Execution branch: `main`; HEAD, local origin/main, and read-only remote origin/main all equalled `c10cbfcb27a3b325e23d17309981c3c4dce242bb`.
- The technical working tree was clean before acceptance, preparation and dispatch. Frozen source inventories passed the actual adapter gates.
- Research commit: `a54ec11b33d90722a482464dcda9823fdc50cf90`.
- Candidate SHA-256: `41c257a36cd2499fa8aa12fe8140e8fe24818fd5ed8586acc59fa8bbc4bcc9fc`. Original bytes still state `NOT ACCEPTED`, `DO NOT EXECUTE`, `gate_b_complete=false`; they were not edited.
- Prompt SHA-256: `e8d256399192e3f3ed66c23c78b80dc976bb8adc5e422a49ce3401ad407926cc`.
- Schedule SHA-256: `0dbe99e7022f4dc46ece2a6127889b4f4c8a5822869557b332602f5221e0c700`.
- Separate acceptance: `acceptance.json`, SHA-256 `5dabee95c34ead23aaf9c71b533bf55ce9498067884cb8450730f2a8620d5252`; recorded at `2026-09-26T17:51:17.854980+02:00` using the existing author/accepted_at schema.
- The approval_statement is the exact user approval. Its recording timestamp is not a fabricated historical chat timestamp.
- Local authorization/source checks preceded SQL/provider access; schema 2, application principal, baseline rows, model/runtime identities, schedule, requests and context proofs passed before preparation.
- Experiment ID 2 was returned by the adapter/database and was not assumed for preparation.
- Preparation persisted 108 planned logical runs; 0 attempts, predictions, reports or touched/partial runs. All 108 reconstructed request byte strings matched the frozen inventory.
- A new empty spool directory and the live identities were checked immediately before dispatch. The existing adapter repeated its runtime/source/database/context checks before every physical attempt.

## FACT FROM OBSERVATION — invocation and completion

Working directory: `/Users/aerfurt/University/Bachelor/rest_api_checker`.

Preparation:
```sh
.venv/bin/python -B -m rest_api_checker.sensitivity_execution prepare --candidate artifacts/sensitivity_freeze_candidate_v2/candidate.json --acceptance artifacts/sensitivity_freeze_candidate_v2/execution_20260926/acceptance.json
```

Execution:
```sh
/usr/bin/caffeinate -i .venv/bin/python -B -m rest_api_checker.sensitivity_execution run --candidate artifacts/sensitivity_freeze_candidate_v2/candidate.json --acceptance artifacts/sensitivity_freeze_candidate_v2/execution_20260926/acceptance.json --experiment-id 2 --spool /Users/aerfurt/University/Bachelor/rest_api_checker_spool/p2_sensitivity_exp2_20260926
```

Both stdout and stderr were redirected, without overwrite, to `artifacts/sensitivity_freeze_candidate_v2/execution_20260926/execution_console.log`.

- Shell exit: 0; adapter status `COMPLETED`, exit_code 0, message null. Final console state equals the live DB state.
- Start: `2026-09-26T15:55:23.7974490+00:00`; finish: `2026-09-26T16:22:35.4809230+00:00`.
- Finalized: 108/108; pending: 0; attempts: 108; predictions: 35; retries: 0.
- Valid: 35; parser failures: 73; terminal technical failures: 0.
- Pauses/holds/operator retry reviews: none. The adapter performed its normal durable spool import and finalization for each receipt; no separate recovery/reconciliation command was needed.
- Sequential execution used caffeinate. No parser repair, fence stripping, majority vote, configuration change, prompt rewrite or baseline redispatch occurred.

| Model | Planned/finalized | Valid | Parser failure | Technical failure |
| --- | --- | --- | --- | --- |
| gemma3:27b | 36/36 | 0 | 36 | 0 |
| mistral-small3.2:24b | 36/36 | 0 | 36 | 0 |
| qwen3.6:27b | 36/36 | 35 | 1 | 0 |

## FACT FROM OBSERVATION — integrity and database counts

All 108 spool envelopes passed checksum, run/attempt identity, request and setup binding checks. Every response equals its persisted raw bytes. Every spool envelope is also archived byte-for-byte. The full strict parser replay matched stored outcomes and all prediction fields. No incomplete, duplicate or unmatched spool file remained.

Spool: `/Users/aerfurt/University/Bachelor/rest_api_checker_spool/p2_sensitivity_exp2_20260926/`.

Every row bound by the original candidate, including all original archived file bytes, remained unchanged. Experiment 1 still has 324 finalized runs, 324 attempts, 103 predictions and its sole original report. Original report SHA-256: `34e2bbaef32dbda409eb1ce212bb9c989e54688e6514a6a1ded5bbccfcdaca5f`.

| Table | Before | After preparation | After execution | After D11 |
| --- | --- | --- | --- | --- |
| api_contracts | 2 | 2 | 2 | 2 |
| api_operations | 2 | 2 | 2 | 2 |
| apis | 2 | 2 | 2 | 2 |
| case_families | 3 | 3 | 3 | 3 |
| dataset_cases | 12 | 12 | 12 | 12 |
| datasets | 1 | 1 | 1 | 1 |
| evaluation_reports | 1 | 1 | 1 | 2 |
| experiment_runs | 324 | 432 | 432 | 432 |
| experiments | 1 | 2 | 2 | 2 |
| files | 2015 | 2019 | 2667 | 2669 |
| models | 3 | 3 | 3 | 3 |
| predictions | 103 | 103 | 138 | 138 |
| prompts | 3 | 4 | 4 | 4 |
| reference_results | 12 | 12 | 12 | 12 |
| responses | 12 | 12 | 12 | 12 |
| run_attempts | 324 | 324 | 432 | 432 |
| run_configs | 3 | 3 | 3 | 3 |
| test_cases | 12 | 12 | 12 | 12 |

## FACT FROM PROTOCOL / OBSERVATION — D11 only

Protocol §§6 and 9/D11 prescribe this diagnostic comparison after the approved wording runs; §10 requires its report before Gate C. D11 ran once only after clean completion and successful spool/evidence verification. The existing evaluator reused the original P2 outcomes, including their failures. It appended two archived files and one report row; it did not recalculate or replace Experiment 1 report 1.

- Entry point: `rest_api_checker.sensitivity_analysis.create_report(repo, 2)`.
- Report ID: 2; version `sensitivity-d11-evaluation-v1`; evaluator SHA-256 `2f0bbd4eca54dba0efd48d71f62e321a92be7608076b3130e61db13c3602dc62`.
- Report: `sensitivity-d11-evaluation-report.json`; SHA-256 `f6517c31a048a987695acb0aa1e3fadfce14403e4e3b07f9a7f2452718a78cf8`.
- Input: `sensitivity-d11-analysis-input.json`; SHA-256 `0fae26f1e6358e4f92f6c165c522fd05afec1eff67daed458c39b9aedebcdfd4`.
- Pure D11 replay reproduces the persisted report. All pre-D11 rows remained unchanged.
- No main evaluation, new ranking, winner, threshold, inferential metric or prompt reselection.

| Prespecified measure | Original P2 | Wording variant |
| --- | --- | --- |
| Score | 103/324 | 101/324 |
| StableCorrect | 34/108 | 32/108 |
| Reliability | 36/108 | 35/108 |
| FullCase | 31/108 | 31/108 |

Score delta: -2/324.

| Model | C1 delta | C2 delta | C3 delta | ModelCorrect delta | Paired valid coverage | Vector disagreement |
| --- | --- | --- | --- | --- | --- | --- |
| gemma3:27b | 0/36 | 0/36 | 0/36 | 0/108 | 0/36 | N/A (0/0) |
| mistral-small3.2:24b | 0/36 | 0/36 | 0/36 | 0/108 | 0/36 | N/A (0/0) |
| qwen3.6:27b | -1/36 | -1/36 | 0/36 | -2/108 | 35/36 | 2/35 |

The report retains all prespecified per-repetition category results, model/category stability, repeat disagreement and coverage, outcome rates, full-case correctness, valid-pair category/vector disagreement, excluded failure pairs and complete terminal transition tables. Empty conditional denominators remain N/A.

## Exact next step

Author review and interpretation of the completed comparison plus D11 sensitivity evidence. Then prepare the Gate C final selected-prompt freeze under protocol §10, preserving the original P2 selection and obtaining a separate actual author approval bound to exact artifact hashes. This execution acceptance is not Gate C approval. Do not begin main/final evaluation under this handoff.

## Evidence and versioning

The package includes acceptance, gate receipts, invocation/console/exit evidence, final counts, spool verification, the diagnostic input/report, and audit scripts. SHA256SUMS binds the package; full raw evidence remains in the SQL archive and original spool. The execution commit remains the exact approved commit above; an evidence-only commit, if made, is reported separately. No implementation or frozen scientific input was changed. No research, thesis or literature file was written. No push was performed.
