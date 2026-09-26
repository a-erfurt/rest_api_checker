# Experiment 1 — completed prompt comparison analysis and handoff

Date: 2026-09-26. Phase: development-only comparison. Evidence labels below distinguish data, protocol/implementation, inference and open questions. This report is AI-assisted technical analysis, not author interpretation or Gate-C approval.

## FACT FROM DATA — completion and integrity
Experiment 1 completed cleanly: **324/324 finalized, 103 valid, 221 parser failures, 0 technical failures; 0 pending; 324 physical attempts; 0 retries; 103 predictions.** This is a real (`fabricated=false`) comparison, not the fabricated demonstration. All 324 final envelopes are complete provider receipts. All attempts are attempt 1, finalized, and agree with their logical run; exactly the 103 valid runs have one prediction. No failure has a salvaged prediction.

Start: `2026-09-26T11:59:50.5868310+00:00` (13:59:50 CEST); finish: `2026-09-26T12:56:29.3867110+00:00` (14:56:29 CEST). Elapsed approximately 56 minutes 39 seconds. Console final JSON: `status=COMPLETED`, `exit_code=0`, `message=null`; its entire state equals the live DB state. This is a recorded runner exit code, not an independently retained parent-shell wait status.

Console: `/Users/aerfurt/University/Bachelor/rest_api_checker_spool/prompt_comparison_exp1_console.log`; SHA-256 `1dbe932ee52f7651b6f5c5a8330036125ea2749ca15fef5b88618e8db4722d89`. Spool: `/Users/aerfurt/University/Bachelor/rest_api_checker_spool/prompt_comparison_exp1/`. Exactly 324 entries, no incomplete or unmatched files. All spool checksums, response bytes, run/attempt IDs, setup hashes and request hashes match the archive. Schedule order/identities match the frozen 324 slots. Source closure comprises 2013 archived files and 248 frozen local source hashes.

DB counts (global application DB; there is exactly one experiment):

| Table | Before evaluation | After evaluation |
| --- | --- | --- |
| api_contracts | 2 | 2 |
| api_operations | 2 | 2 |
| apis | 2 | 2 |
| case_families | 3 | 3 |
| dataset_cases | 12 | 12 |
| datasets | 1 | 1 |
| evaluation_reports | 0 | 1 |
| experiment_runs | 324 | 324 |
| experiments | 1 | 1 |
| files | 2013 | 2015 |
| models | 3 | 3 |
| predictions | 103 | 103 |
| prompts | 3 | 3 |
| reference_results | 12 | 12 |
| responses | 12 | 12 |
| run_attempts | 324 | 324 |
| run_configs | 3 | 3 |
| test_cases | 12 | 12 |

All protected relational table fingerprints stayed identical. Existing archive file IDs/names/hash/size records stayed identical. Only the evaluator appended its input snapshot (file 2014), report (file 2015), and evaluation_reports row 1. Frozen local source hashes were checked again after evaluation. No prompts, parser, references, OpenAPI, dataset, configurations, run records, attempts or predictions were edited.

## FACT FROM PROTOCOL/IMPLEMENTATION — authority and evaluation admissibility
Authorities: research `03_research_design/prompt_development_protocol_v1.md` §§5–7, 9–10; `prompt_candidates_v1/common_output_contract_v1.txt`; technical `src/rest_api_checker/evaluation.py`, `experiment/parser.py`, `persistence/inspection.py`, `freeze.py`, `accepted_comparison.py`. These local frozen sources, not old chat statements, control this analysis.

The archived author record accepts candidate `32d4e76018fc6024b3de757d853068ef87d9df20f76a603171772ba2227fefdd` at `2026-09-26T13:40:41.628196+02:00`. Its decision is `AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON`, including bounded failure qualification with unobserved crash/OOM. The exact acceptance/candidate hashes and copied candidate fields agree with setup file 69. Implementation commit: `aecae65851e1fdeca440a9576f755510764c11a7`. Old preparation prose saying 'not execution-ready' is historical; the separately archived hash-bound acceptance is the later execution authority. It is not a Gate-C approval.

Parser: `strict-output-v1`, SHA-256 `d8d7fa7a853e0a09b73067f78304ae833b90e2405645b7818139b904ffc33783`. Evaluator: `comparison-evaluation-v1`, SHA-256 `5b231ae95ae018f2d5fb895606436143e819d1638ee65e9ffa846bb7992fae8d`. Both match the accepted candidate and current executable bytes. Ground truth remains the released version-1 references and source pointers; no Oracle rerun or reference decision was made.

Evaluation admissibility was established before scoring: finished comparison, complete exact schedule, fixed bindings, reference/source continuity, fixed parser/evaluator hashes, consistent attempts/predictions, and exact reparsing of unmodified final content. Provisional comparison selection precedes the separate sensitivity phase (§§6,9); waiting for all 432 runs before provisional selection would contradict that sequence. Gate C still requires the later sensitivity work and author approval.

Code review confirmed Score /324, worst-cell Robust /36, StableCorrect /108, Reliability /108 and FullCase /108; failed logical runs stay in denominators with zero successes and no imputed labels. NOT_APPLICABLE is scored. No majority vote. Exact rational lexicographic order: Score, Robust, StableCorrect, Reliability, FullCase, shorter frozen instruction bytes, P1/P2/P3. Valid-only and repeat-disagreement diagnostics have explicit coverage and N/A for zero denominators. Parser checks output structure only, not semantic correctness or dependency coherence.

Verification: 17 existing evaluator tests passed; 124 existing experiment-boundary tests passed. The first combined test invocation referenced a nonexistent parser-test path and ran no tests; the correct existing suites were then run successfully. No new tests or production code were added. The retained offline replay independently reuses the frozen evaluator and matches every metric, diagnostic and ranking; it does not constitute independent scientific validation of the Ground Truth.

## FACT FROM DATA — failure distributions
Overall valid rate: 103/324 = 31.79%; parser-failure rate: 221/324 = 68.21%; technical-failure rate: 0/324. Each model has 108 logical runs; each prompt has 108; each model/prompt has 36; each case has 27; each repetition has 108.

### model
| model | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| gemma3:27b | 0 | 108 | 0 | 108 |
| mistral-small3.2:24b | 0 | 108 | 0 | 108 |
| qwen3.6:27b | 103 | 5 | 0 | 108 |

### prompt
| prompt | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| P1 | 33 | 75 | 0 | 108 |
| P2 | 36 | 72 | 0 | 108 |
| P3 | 34 | 74 | 0 | 108 |

### model/prompt
| model | prompt | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 0 | 36 | 0 | 36 |
| gemma3:27b | P2 | 0 | 36 | 0 | 36 |
| gemma3:27b | P3 | 0 | 36 | 0 | 36 |
| mistral-small3.2:24b | P1 | 0 | 36 | 0 | 36 |
| mistral-small3.2:24b | P2 | 0 | 36 | 0 | 36 |
| mistral-small3.2:24b | P3 | 0 | 36 | 0 | 36 |
| qwen3.6:27b | P1 | 33 | 3 | 0 | 36 |
| qwen3.6:27b | P2 | 36 | 0 | 0 | 36 |
| qwen3.6:27b | P3 | 34 | 2 | 0 | 36 |

### case
| case | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| DEV-01 | 9 | 18 | 0 | 27 |
| DEV-02 | 5 | 22 | 0 | 27 |
| DEV-03 | 9 | 18 | 0 | 27 |
| DEV-04 | 9 | 18 | 0 | 27 |
| DEV-05 | 9 | 18 | 0 | 27 |
| DEV-06 | 9 | 18 | 0 | 27 |
| DEV-07 | 9 | 18 | 0 | 27 |
| DEV-08 | 9 | 18 | 0 | 27 |
| DEV-09 | 9 | 18 | 0 | 27 |
| DEV-10 | 8 | 19 | 0 | 27 |
| DEV-11 | 9 | 18 | 0 | 27 |
| DEV-12 | 9 | 18 | 0 | 27 |

### repetition
| repetition | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| 1 | 36 | 72 | 0 | 108 |
| 2 | 34 | 74 | 0 | 108 |
| 3 | 33 | 75 | 0 | 108 |

### model/prompt/repetition
| model | prompt | repetition | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 1 | 0 | 12 | 0 | 12 |
| gemma3:27b | P1 | 2 | 0 | 12 | 0 | 12 |
| gemma3:27b | P1 | 3 | 0 | 12 | 0 | 12 |
| gemma3:27b | P2 | 1 | 0 | 12 | 0 | 12 |
| gemma3:27b | P2 | 2 | 0 | 12 | 0 | 12 |
| gemma3:27b | P2 | 3 | 0 | 12 | 0 | 12 |
| gemma3:27b | P3 | 1 | 0 | 12 | 0 | 12 |
| gemma3:27b | P3 | 2 | 0 | 12 | 0 | 12 |
| gemma3:27b | P3 | 3 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P1 | 1 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P1 | 2 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P1 | 3 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P2 | 1 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P2 | 2 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P2 | 3 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P3 | 1 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P3 | 2 | 0 | 12 | 0 | 12 |
| mistral-small3.2:24b | P3 | 3 | 0 | 12 | 0 | 12 |
| qwen3.6:27b | P1 | 1 | 12 | 0 | 0 | 12 |
| qwen3.6:27b | P1 | 2 | 11 | 1 | 0 | 12 |
| qwen3.6:27b | P1 | 3 | 10 | 2 | 0 | 12 |
| qwen3.6:27b | P2 | 1 | 12 | 0 | 0 | 12 |
| qwen3.6:27b | P2 | 2 | 12 | 0 | 0 | 12 |
| qwen3.6:27b | P2 | 3 | 12 | 0 | 0 | 12 |
| qwen3.6:27b | P3 | 1 | 12 | 0 | 0 | 12 |
| qwen3.6:27b | P3 | 2 | 11 | 1 | 0 | 12 |
| qwen3.6:27b | P3 | 3 | 11 | 1 | 0 | 12 |

Additional strata below use existing relational metadata, not fault intent as a label.

### operation
| operation | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| /edx/validation/body | 50 | 112 | 0 | 162 |
| /resistance/validation/file | 53 | 109 | 0 | 162 |

### origin
| origin | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| natural_observation | 27 | 54 | 0 | 81 |
| synthetic_conformant_control | 14 | 40 | 0 | 54 |
| synthetic_inconsistency | 62 | 127 | 0 | 189 |

### family_id
| family_id | Valid | Parser | Technical | Denominator |
| --- | --- | --- | --- | --- |
| 1 | 50 | 112 | 0 | 162 |
| 2 | 36 | 72 | 0 | 108 |
| 3 | 17 | 37 | 0 | 54 |

All model×case, prompt×case, model×repetition, prompt×repetition, model×prompt×case and full four-way cells are preserved in `distributions.json`; all cells include valid/parser/technical counts and the exact planned denominator. Gemma and Mistral each have 0/9 valid per case and 0/12 valid per prompt/repetition. Qwen exceptions occur only at DEV-02 (4 failures) and DEV-10 (1 failure).

## FACT FROM DATA — descriptive parser failure audit
Every rejected output has the stored strict-parser code **INVALID_JSON** (221/221), reproduced on the complete original message.content. The following mutually exclusive subcategories are descriptive observations added by this analysis; they do not change stored outcomes or repair outputs. No Markdown stripping, prefix extraction, partial-category salvage, label coercion, counterfactual score or alternate parser was used. Standard JSON error text/offsets describe the untouched full string only.

| Descriptive category | Count / parser failures | Count / all runs | Evidence |
| --- | --- | --- | --- |
| Markdown fenced final content | 216/221 | 216/324 | 108 Gemma + 108 Mistral; opening ```json, closing ```, exactly two fences; done_reason=stop |
| Unterminated JSON string at token limit | 3/221 | 3/324 | Qwen runs 13,43,108; done_reason=length; eval_count=512 |
| Extra prose after JSON at token limit | 2/221 | 2/324 | Qwen runs 47,58; Extra data; done_reason=length; eval_count=512 |

216/221 = 97.74% of failures carry Markdown fences. All 216 stop normally; all five length-limited outputs fail. The two Extra-data failures would violate the one-object/no-prose rule even without considering their final truncation. No separate nonempty thinking field exists in any of the 324 receipts; visible self-reconsideration occurs inside final content. This observation does not establish hidden internal thinking behavior.

| Run | Prompt | Case | Rep / seed | JSON error | Offset (0-based) | Stop / tokens |
| --- | --- | --- | --- | --- | --- | --- |
| 13 | P1 | DEV-02 | 3 / 303 | Unterminated string starting at | 351 | length / 512 |
| 43 | P1 | DEV-02 | 2 / 202 | Unterminated string starting at | 351 | length / 512 |
| 47 | P3 | DEV-02 | 2 / 202 | Extra data | 1178 | length / 512 |
| 58 | P1 | DEV-10 | 3 / 303 | Extra data | 963 | length / 512 |
| 108 | P3 | DEV-02 | 3 / 303 | Unterminated string starting at | 353 | length / 512 |

Representative original content follows. Text is model output, not verified explanation. Full raw strings and lossless base64 envelopes for all 324 runs are in `raw_outputs.json`; every rejected run has IDs, original response SHA-256, spool path/hash, JSON error offset and descriptive class in `failure_classification.json`.

### Raw evidence — run 109, gemma3:27b, P3, DEV-11, repetition 2
Response file 721, SHA-256 `ea11ecd19931d935c58d13a36750d8fd1be05afda71b51abd37d4cd8c51e8f98`.

Complete message.content (outer four-backtick fence is report formatting):

````text
```json
{
  "c1": {
    "verdict": "PASS",
    "reason": "Observed status 200 matches documented status 200."
  },
  "c2": {
    "verdict": "FAIL",
    "reason": "Observed content type text/plain does not match documented content type application/json."
  },
  "c3": {
    "verdict": "NOT_APPLICABLE",
    "reason": "C2 failed, downstream checks are skipped."
  }
}
```
````

### Raw evidence — run 217, mistral-small3.2:24b, P1, DEV-07, repetition 2
Response file 1369, SHA-256 `ad9218233da93623d2dcaa23234ce045be7e99506ed3cdc1a72f884f827f5b64`.

Complete message.content (outer four-backtick fence is report formatting):

````text
```json
{
  "c1": {
    "verdict": "PASS",
    "reason": "Observed status 200 matches documented response"
  },
  "c2": {
    "verdict": "PASS",
    "reason": "Observed content_type application/json matches declared media type"
  },
  "c3": {
    "verdict": "PASS",
    "reason": "Body conforms to empty schema"
  }
}
```
````

### Raw evidence — run 13, qwen3.6:27b, P1, DEV-02, repetition 3
Response file 145, SHA-256 `5ceaaaa891cec6be552e14e82f80bde89c25518dcac49fb51cab969c127dcf41`.

Exact final 300 characters (excerpt only; not an accepted prediction):

````text
it be FAIL? Let me re-read the prompt. 'valid JSON violating the applicable schema gives C3 FAIL'. Is 0 a valid int32? Yes. Is the JSON valid? Yes. Is the schema conformance met? Yes. So it should be PASS. Let me double check the 'nullable' definition. In OpenAPI 3.0, nullable means the value can be
````

### Raw evidence — run 47, qwen3.6:27b, P3, DEV-02, repetition 2
Response file 349, SHA-256 `4c6fe0d4c0daa925a3813a589afc570b7c08a3c4ae83be236636324b1589bde7`.

Exact excerpt beginning at character 1178 (the JSON decoder’s Extra-data position):

````text
Wait, I need to re-evaluate C3 carefully.
Schema: `TypeValidatorResult`
- `type`: object
- `additionalProperties`: false
- `properties`:
  - `code`: type integer, format int32
  - `data`: type array, nullable
  - `message`: type string, nullable
  - `mode`: type string, nullable
  - `warning`: type 
````

### Raw evidence — run 58, qwen3.6:27b, P1, DEV-10, repetition 3
Response file 415, SHA-256 `c96b6e4d2f957aaffc6a5e762c9df1f98ed8d21589a981019e1e06dd0cd34284`.

Exact excerpt beginning at character 963 (the JSON decoder’s Extra-data position):

````text
Wait, I need to be precise.
Observed item: `{"type":"missing","loc":["body","file"],"input":null}`
Schema `ValidationError` required: `["loc","msg","type"]`
The observed item does NOT have `msg`.
Therefore, C3 should be FAIL.

Let's double check.
`ValidationError` properties:
- `ctx`: optional
- `in
````

## FACT FROM DATA — frozen evaluation report 1
Persisted at `2026-09-26T13:16:06.4833330+00:00`. Input file 2014: `c521f532e708a3244998888bd5ea2219911d674a5df5c14f8e457ccf71a2a41c`. Report file 2015: `34e2bbaef32dbda409eb1ce212bb9c989e54688e6514a6a1ded5bbccfcdaca5f`. The standalone exports are byte-identical to DB archived files.

| Prompt | Score | Robust | StableCorrect | Reliability | FullCase | UTF-8 instruction bytes |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | 96/324 | 0/36 | 30/108 | 33/108 | 30/108 | 4325 |
| P2 | 103/324 | 0/36 | 34/108 | 36/108 | 31/108 | 4996 |
| P3 | 98/324 | 0/36 | 32/108 | 34/108 | 30/108 | 5835 |

Formal frozen ranking: **P2 > P3 > P1**. Scores: 103/324 > 98/324 > 96/324. Selection is decided by Score; no tie-breaker is needed. P2 is the evaluator’s provisional selected_prompt, not an author-approved final prompt. No selected-prompt file or Gate-C manifest was created.

### All model/prompt/category cells (failure-aware)
| Model | Prompt | C1 | C2 | C3 | Full vector |
| --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 0/36 | 0/36 | 0/36 | 0/36 |
| mistral-small3.2:24b | P1 | 0/36 | 0/36 | 0/36 | 0/36 |
| qwen3.6:27b | P1 | 33/36 | 33/36 | 30/36 | 30/36 |
| gemma3:27b | P2 | 0/36 | 0/36 | 0/36 | 0/36 |
| mistral-small3.2:24b | P2 | 0/36 | 0/36 | 0/36 | 0/36 |
| qwen3.6:27b | P2 | 36/36 | 36/36 | 31/36 | 31/36 |
| gemma3:27b | P3 | 0/36 | 0/36 | 0/36 | 0/36 |
| mistral-small3.2:24b | P3 | 0/36 | 0/36 | 0/36 | 0/36 |
| qwen3.6:27b | P3 | 34/36 | 34/36 | 30/36 | 30/36 |

### Valid-only diagnostics and coverage
| Model | Prompt | Valid coverage | C1 valid-only | C2 valid-only | C3 valid-only | Valid triple coverage | Vector disagreement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| mistral-small3.2:24b | P1 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| qwen3.6:27b | P1 | 33/36 | 33/33 | 33/33 | 30/33 | 10/12 | 0/10 |
| gemma3:27b | P2 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| mistral-small3.2:24b | P2 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| qwen3.6:27b | P2 | 36/36 | 36/36 | 36/36 | 31/36 | 12/12 | 1/12 |
| gemma3:27b | P3 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| mistral-small3.2:24b | P3 | 0/36 | N/A (0/0) | N/A (0/0) | N/A (0/0) | 0/12 | N/A (0/0) |
| qwen3.6:27b | P3 | 34/36 | 34/34 | 34/34 | 30/34 | 11/12 | 0/11 |

Qwen pooled descriptive values across all prompts: C1 103/108, C2 103/108, C3 91/108; full vectors 91/108. Conditional on its 103 valid outputs: C1 103/103, C2 103/103, C3 91/103; all categories 297/309. Across all models the planned category total is 972, with 297/972 correct outcomes (descriptive, not an additional selection criterion). Gemma/Mistral semantic accuracy conditional on valid outputs is N/A, not 0%: each has 0/108 valid coverage. Their end-to-end category cells remain 0/36.

### Per-repetition category correctness
| Model | Prompt | Repetition | C1 | C2 | C3 |
| --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 1 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P1 | 2 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P1 | 3 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P1 | 1 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P1 | 2 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P1 | 3 | 0/12 | 0/12 | 0/12 |
| qwen3.6:27b | P1 | 1 | 12/12 | 12/12 | 10/12 |
| qwen3.6:27b | P1 | 2 | 11/12 | 11/12 | 10/12 |
| qwen3.6:27b | P1 | 3 | 10/12 | 10/12 | 10/12 |
| gemma3:27b | P2 | 1 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P2 | 2 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P2 | 3 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P2 | 1 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P2 | 2 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P2 | 3 | 0/12 | 0/12 | 0/12 |
| qwen3.6:27b | P2 | 1 | 12/12 | 12/12 | 11/12 |
| qwen3.6:27b | P2 | 2 | 12/12 | 12/12 | 10/12 |
| qwen3.6:27b | P2 | 3 | 12/12 | 12/12 | 10/12 |
| gemma3:27b | P3 | 1 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P3 | 2 | 0/12 | 0/12 | 0/12 |
| gemma3:27b | P3 | 3 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P3 | 1 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P3 | 2 | 0/12 | 0/12 | 0/12 |
| mistral-small3.2:24b | P3 | 3 | 0/12 | 0/12 | 0/12 |
| qwen3.6:27b | P3 | 1 | 12/12 | 12/12 | 10/12 |
| qwen3.6:27b | P3 | 2 | 11/12 | 11/12 | 10/12 |
| qwen3.6:27b | P3 | 3 | 11/12 | 11/12 | 10/12 |

### Three-state confusion on valid outputs
Only nonzero cells are listed; all absent cells are exactly zero. Complete 3×3 matrices for every model/prompt/category, with failures alongside outcome counts, are retained in the evaluator JSON. Gemma/Mistral have no confusion observations.

| Prompt | Model | Category | Reference | Prediction | Count |
| --- | --- | --- | --- | --- | --- |
| P1 | qwen3.6:27b | c1 | FAIL | FAIL | 3 |
| P1 | qwen3.6:27b | c1 | PASS | PASS | 30 |
| P1 | qwen3.6:27b | c2 | FAIL | FAIL | 6 |
| P1 | qwen3.6:27b | c2 | NOT_APPLICABLE | NOT_APPLICABLE | 3 |
| P1 | qwen3.6:27b | c2 | PASS | PASS | 24 |
| P1 | qwen3.6:27b | c3 | FAIL | FAIL | 12 |
| P1 | qwen3.6:27b | c3 | FAIL | PASS | 2 |
| P1 | qwen3.6:27b | c3 | NOT_APPLICABLE | NOT_APPLICABLE | 9 |
| P1 | qwen3.6:27b | c3 | PASS | FAIL | 1 |
| P1 | qwen3.6:27b | c3 | PASS | PASS | 9 |
| P2 | qwen3.6:27b | c1 | FAIL | FAIL | 3 |
| P2 | qwen3.6:27b | c1 | PASS | PASS | 33 |
| P2 | qwen3.6:27b | c2 | FAIL | FAIL | 6 |
| P2 | qwen3.6:27b | c2 | NOT_APPLICABLE | NOT_APPLICABLE | 3 |
| P2 | qwen3.6:27b | c2 | PASS | PASS | 27 |
| P2 | qwen3.6:27b | c3 | FAIL | FAIL | 12 |
| P2 | qwen3.6:27b | c3 | FAIL | PASS | 3 |
| P2 | qwen3.6:27b | c3 | NOT_APPLICABLE | NOT_APPLICABLE | 9 |
| P2 | qwen3.6:27b | c3 | PASS | FAIL | 2 |
| P2 | qwen3.6:27b | c3 | PASS | PASS | 10 |
| P3 | qwen3.6:27b | c1 | FAIL | FAIL | 3 |
| P3 | qwen3.6:27b | c1 | PASS | PASS | 31 |
| P3 | qwen3.6:27b | c2 | FAIL | FAIL | 6 |
| P3 | qwen3.6:27b | c2 | NOT_APPLICABLE | NOT_APPLICABLE | 3 |
| P3 | qwen3.6:27b | c2 | PASS | PASS | 25 |
| P3 | qwen3.6:27b | c3 | FAIL | FAIL | 12 |
| P3 | qwen3.6:27b | c3 | FAIL | PASS | 3 |
| P3 | qwen3.6:27b | c3 | NOT_APPLICABLE | NOT_APPLICABLE | 9 |
| P3 | qwen3.6:27b | c3 | PASS | FAIL | 1 |
| P3 | qwen3.6:27b | c3 | PASS | PASS | 9 |

### Semantic mismatches among accepted outputs only
| Run | Prompt | Case | Repetition | C3 reference | C3 prediction |
| --- | --- | --- | --- | --- | --- |
| 2 | P2 | DEV-02 | 3 | PASS | FAIL |
| 24 | P3 | DEV-02 | 1 | PASS | FAIL |
| 29 | P1 | DEV-02 | 1 | PASS | FAIL |
| 34 | P3 | DEV-10 | 2 | FAIL | PASS |
| 36 | P1 | DEV-10 | 1 | FAIL | PASS |
| 45 | P1 | DEV-10 | 2 | FAIL | PASS |
| 56 | P3 | DEV-10 | 3 | FAIL | PASS |
| 59 | P2 | DEV-10 | 3 | FAIL | PASS |
| 70 | P3 | DEV-10 | 1 | FAIL | PASS |
| 71 | P2 | DEV-10 | 2 | FAIL | PASS |
| 95 | P2 | DEV-02 | 2 | PASS | FAIL |
| 97 | P2 | DEV-10 | 1 | FAIL | PASS |

All 12/103 mismatching valid vectors are Qwen C3 errors: four DEV-02 predictions FAIL instead of reference PASS, eight DEV-10 predictions PASS instead of reference FAIL. C1 and C2 have no mismatches among valid outputs. Parser failures are not added to this semantic-confusion inventory. No reason-text plausibility overrides the stored verdict.

## INFERENCE — interpretation and limits
- The dominant observed obstacle is compliance with the output format: 216/221 parser failures visibly violate the explicit no-Markdown rule. This supports a format-adherence explanation for rejection, but does not demonstrate correct contract recognition within those strings. Their inner objects were neither extracted nor rescored.
- Five Qwen failures combine length-limited generation with unfinished strings or prohibited continuation prose. Length is an observed stop condition, not proof that increasing the limit would yield a valid or correct answer.
- Formal selection is driven entirely by Qwen because Gemma/Mistral contribute zero successful category outcomes under every prompt. All prompts have Robust=0/36. The ranking therefore supplies no evidence that P2 achieves cross-model usable output reliability.
- P2 has both better Qwen output coverage (36/36 versus 34/36 and 33/36) and remaining semantic C3 errors. Conditional C3 accuracy is 31/36 for P2, 30/34 for P3, 30/33 for P1; these conditional samples differ and must not replace the frozen ranking. P2’s score lead over P3 is 5/324, consisting arithmetically of four additional correct C1/C2 outcomes and one additional correct C3 outcome. No significance or broad superiority claim follows.
- The absence of technical failures supports accountable execution for this run, not universal reliability or empirical crash/OOM qualification. Model identity and execution time/block are linked by the frozen per-model schedule; causal claims beyond this observed setting are unwarranted.
- Twelve development cases in three parent families are repeatedly measured; 324 runs are not 324 independent cases. These development results are excluded from final/headline evaluation and do not establish cross-API generalization.

## OPEN QUESTION — author interpretation and future work
1. How should the thesis discuss format adherence as part of the deliberately frozen prompt-only-JSON end-to-end task, given zero usable outputs for two models? These data answer end-to-end usability, but leave their semantic contract-detection accuracy unidentified.
2. What explains the persistent valid C3 errors at DEV-02/DEV-10? Reason text may support later qualitative interpretation, but cannot independently establish correctness, hidden reasoning or a reference defect. This audit found no binding/parser/evaluator defect requiring a rerun.
3. Will the single approved paraphrase exhibit similar reliability and semantic behavior? Unknown until separately approved sensitivity execution. No variant or sensitivity result exists here.
4. Is any separately versioned future experiment with a different output regime scientifically warranted? This is an author/design question, not a repair to Experiment 1. No changed parsing, token limit, JSON mode or prompt is authorized by the present result.

## Exact next scientific step — handoff, then STOP
The author reviews this failure analysis and the formal provisional P2 selection, records their own interpretation and determines whether any genuine protocol/implementation defect requires documented reopening. If continuing the unchanged approved protocol, the next artifact is **one semantically equivalent wording variant of P2 under §9/D11**, drafted in a fresh result-isolated context supplied only with P2 and the approved equivalence checklist. Preserve rule content/order, shared semantic core, output keys/labels and evidence serialization; disclose author exposure to these results. The author then reviews semantic equivalence and approves/freezes exact variant bytes and hash **before** separately authorizing its 108 sensitivity runs. Reuse P2’s existing 108 outcomes as baseline, including 72 failures. No rerun of the baseline.

This task creates no variant, launches no sensitivity or main-evaluation runs, changes no frozen experiment artifact, and records no Gate-C approval. Gate C remains pending after later accountable sensitivity execution/reporting and author approval.

## Reproduction and evidence index
`reproduce_analysis.py` is an offline read-only replay over the retained input snapshot and exact raw envelopes. It refuses a pre-existing output directory, verifies hashes and the frozen parser/evaluator, reproduces all descriptive grouping cells and all evaluator values, and performs no DB/provider calls. From the technical repository, use a fresh output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/experiment_evidence/prompt_comparison_exp1_2026-09-26/reproduce_analysis.py \
  /tmp/rac-exp1-reproduction-new
```

To inspect the already persisted evaluation without creating another report: `.venv/bin/rac evaluate show 1 --json`. Do not rerun `evaluate comparison 1` merely to inspect it: the authorized command executed once in this audit appends a report each time. `collect_readonly.py` preserves the actual initial live collection procedure (SELECT/read only; new temporary output directory recommended); `postcheck_record.py` records the one-time post-evaluation comparison with that baseline. No credentials or connection secrets are included.

Evidence files: `comparison-analysis-input.json`, `comparison-evaluation-report.json`, `raw_outputs.json`, `failure_classification.json`, `distributions.json`, `status.json`, `console_summary.json`, `acceptance.json`, `db_before.json`, `postcheck.json`, `reports_before.json`, `replay_checks.json`, and test receipts. SHA256SUMS binds all package files except itself. The original DB archive remains the complete source/evidence store; this package is not a full database backup.

Technical worktree was clean at entry, at commit aecae65851e1fdeca440a9576f755510764c11a7. Research checkout already had modified `01_sources/literature/literature.bib` and untracked `01_sources/literature/thesis_citation_plan.md`; both were left untouched. No branch switch, commit or protected tracked-file edit was needed for this evidence-only handoff. The report package is the sole new repository artifact.
