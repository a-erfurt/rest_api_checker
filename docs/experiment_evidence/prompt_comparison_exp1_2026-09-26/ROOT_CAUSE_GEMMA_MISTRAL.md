# Experiment 1 — root cause of Gemma and Mistral parser failures

Date: 2026-09-26. Scope: **analysis only**, completed development prompt comparison, experiment_id=1. This is AI-assisted descriptive technical analysis for author review; it is not a scientific author decision, prompt selection, Gate-C approval, or a new evaluation.

## Finding

**Gemma: MODEL FORMAT NON-COMPLIANCE. Mistral: MODEL FORMAT NON-COMPLIANCE.** These classifications apply to the frozen model + native template + runtime + prompt-only JSON condition. No setup defect explaining the failures was found in the inspected evidence. Native framing may contribute to model behavior, but its causal contribution is not identifiable from this experiment.

Every Gemma and Mistral output contains exactly one closed Markdown JSON fence, ends normally with `done_reason=stop`, and stays far below 512 output tokens. All 216 fenced contents are syntactically valid JSON with the required object structure after hypothetical removal of only the two fence lines. This is a descriptive format observation, **not acceptance, a recovered prediction, a correctness judgment, or rescoring**. All 216 remain parser failures.

All five outputs at the cap belong to Qwen. Three have unterminated JSON strings; two already contain prohibited text after a JSON object. A larger cap is not established as a remedy, especially for the latter two.

## 1. Evidence and integrity

**FACT FROM DATA.** All 324 stored run records and original response envelopes were inspected: 103 valid, 221 parser failures, zero technical failures, one physical attempt per logical run. Original envelopes were decoded losslessly from `raw_outputs.json`, hashed against the immutable analysis snapshot, and matched to the original 324 spool files. No live DB connection was necessary.

The offline reconstruction verifies:

- 248 frozen implementation/research source hashes against the accepted setup.
- All files covered by the pre-existing evidence package's `SHA256SUMS`.
- 324 reconstructed HTTP request byte hashes against archived request-file hashes, dispatch/spool hashes, diagnostic hashes and prequalification inventory.
- 324 reconstructed provenance sidecar hashes. Qualification metadata uses source paths; dispatch metadata uses `files:<id>` identities. The script accounts for that documented difference; message bytes are identical.
- All 216 Gemma/Mistral native rendered strings against stored native-render SHA-256 values.
- Actual `prompt_eval_count` equals the complete native context qualification count for **324/324** runs, with zero discrepancies.
- Effective D07 values in all nine historical diagnostic runner-slot snapshots (three models × three seeds).

The accepted setup names implementation commit `aecae65851e1fdeca440a9576f755510764c11a7`. The hash-bound author acceptance is separate from historical qualification reports that still say BLOCKED: candidate `32d4e76018fc6024b3de757d853068ef87d9df20f76a603171772ba2227fefdd`, acceptance `1d0b565d07ded7af5385e5a5edd1546a9eb0fa5fb273360cf01a86b16ea9ea46`. See `analysis_input.json`, `acceptance.json`, and `artifacts/gate_b_freeze_candidate_v1/`. Historical pre-acceptance prose is not evidence that this later comparison was unauthorized.

This audit does not claim fresh SQL-to-export verification: it verifies the stored export, archival hash identities, original spool receipts and frozen local sources. It also does not claim a new runtime observation.

### Primary input identities

| Evidence file | SHA-256 |
| --- | --- |
| SHA256SUMS | `2c9e4d7cec4c2c1517e8205240fd29e10003d8a72296a60fd5cd2bc61bec6b0b` |
| comparison-analysis-input.json | `c521f532e708a3244998888bd5ea2219911d674a5df5c14f8e457ccf71a2a41c` |
| raw_outputs.json | `80c1ec1b9d31956f72c923329aef02f5ad9b668dcbf08ad53979ad85b4401b06` |
| context.json | `2d5fd56dc51968c38b3096893bf97ea67998109b765ba1eb8bd2d950af6ff46d` |
| gemma_template.txt | `e0a42594d802e5d31cdc786deb4823edb8adff66094d49de8fffe976d753e348` |
| mistral_system.txt | `9c810f69c610d59a322085379f81ad72814b84916a1c3d0262cf1b1114bbfb36` |
| mistral_template.txt | `706c4d1164f7f1bbce2a852f2bc9cfa66b98d24f79300b9034388e07fcda98c8` |
| request_inventory.json | `ecb85223dd2385b30cd02dd93f55484ad486a9fed0387355a1f52a6ec8087711` |
| source_review.json | `3e0968aa1f75fb665fdde45368eceb83290d5405d6fb2e27a5fa629963f63928` |

## 2. Frozen output contract

**FACT FROM SOURCE.** All three complete prompt files contain the same explicit output contract. Relevant exact wording:

> Return exactly one JSON object with exactly the keys "c1", "c2" and "c3".

> Each value must be an object containing exactly "verdict" and "reason".

> Return no Markdown fences, surrounding prose, confidence score, overall verdict or metadata.

> Give only the short explanations required in reason; do not provide an extended reasoning trace.

The full paragraphs also require all six members, restrict verdicts to PASS/FAIL/NOT_APPLICABLE, require nonblank reason strings, prohibit duplicate keys and additional fields, and allow normal JSON whitespace/member ordering. These are explicit requirements, not an inferred preference for JSON.

Files are under the research repository's `03_research_design/prompt_candidates_v1/`. Hashes match the frozen setup and every reconstructed system message:

| Prompt | File and output-contract lines | SHA-256 |
| --- | --- | --- |
| P1 | p1_minimal_direct_v1.txt, lines 19–22 | `f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6` |
| P2 | p2_structured_checklist_v1.txt, lines 21–24 | `50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f` |
| P3 | p3_explicit_contract_interpretation_v1.txt, lines 23–26 | `5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb` |

**INFERENCE.** The output-format requirement is unambiguous for a reasonable reader/model: exactly one specified JSON object and explicitly no Markdown fences or surrounding prose. This says nothing about optimal prompt style or guaranteed model compliance. No prompt-style optimization was performed.

## 3. What was delivered

**FACT FROM IMPLEMENTATION.** `src/rest_api_checker/experiment/request.py::build_request` validates the exact prompt hash and constructs one system message containing the full frozen P1/P2/P3 bytes plus one user message containing the complete operation evidence. `renderer.py::render` retains operation response alternatives and referenced definitions and losslessly carries the observed response. Bookkeeping/provenance is a sidecar, not a model message. `provider.py::OllamaClient.send` revalidates request bytes and sends them directly to `/api/chat`; no SDK or implicit JSON-mode adapter intervenes.

Every request has `stream=false`, no `format`, tools, images, or conversation history. Only Qwen has `think=false`; Gemma/Mistral omit `think`, as approved in D06. Repetitions map to seeds 101/202/303. All other D07 options are identical:

```json
{"temperature":0.2,"top_p":0.9,"top_k":40,"min_p":0.0,"repeat_penalty":1.0,"repeat_last_n":64,"draft_num_predict":0,"num_ctx":32768,"num_predict":512}
```

Timeout is 300 seconds. Stored `run_configs` agree with these values. Exact semantic prompt and evidence bytes are common across models for each prompt/case; native delimiters and tokenization differ by design.

### Gemma native framing

**FACT FROM RUNTIME EVIDENCE.** Captured `gemma_template.txt` maps both `system` and `user` roles into separate native user turns. With the two approved messages the effective text is exactly:

```text
<start_of_turn>user
<FULL FROZEN P1/P2/P3 TEXT, INCLUDING OUTPUT CONTRACT><end_of_turn>
<start_of_turn>user
<FULL RENDERED OPERATION/RESPONSE EVIDENCE><end_of_turn>
<start_of_turn>model
```

The angle-bracket descriptions above are explanatory placeholders only. Full reconstructed bytes are delivered in the `gemma3_P*_DEV-02_R1_native.txt` files. They are not a fresh model invocation. The same deterministic reconstruction matches all **108/108** captured study render hashes, and it matches the saved fabricated diagnostic render. A tokenizer-added BOS is accounted for by the historical native tokenization evidence; the text artifacts represent the captured rendered string, not an invented token-ID trace.

The system text is **present in full**, including the explicit no-fence instruction. It does not retain a separate native system role. Two successive user turns can plausibly change relative instruction salience; the current data cannot isolate that effect. D05 explicitly selected each model's native template, this behavior was captured before comparison, and the later setup acceptance bound that evidence. It is therefore not an observed deviation from the approved experimental setup.

### Mistral native framing

**FACT FROM RUNTIME EVIDENCE.** The stored template emits:

```text
[SYSTEM_PROMPT]<FULL FROZEN P1/P2/P3 TEXT>[/SYSTEM_PROMPT][INST]<FULL RENDERED OPERATION/RESPONSE EVIDENCE>[/INST]
```

All **108/108** reconstructed strings match the historical render hashes. The full instructions are inside `[SYSTEM_PROMPT]`, including no-Markdown/no-extra-text. `mistral_system.txt` contains a longer native assistant/persona default. The saved diagnostic render and the complete study render hashes show that this default is **replaced/suppressed when the explicit system message is supplied**, not concatenated with the experiment prompt. Reconstructing only the supplied system/user text exactly matches the stored study hashes. This independently corroborates the historical `source_review.json` finding without relying solely on its prose.

### Representative byte-complete artifacts

The following runs cover every prompt for both investigated models. Each saved request is reconstructed byte-for-byte and hash-matched to the archived request; each native text is hash-matched to the prequalification render for that exact request. They are reconstructions supported by stored evidence, not new network captures.

| Model / prompt | Run / case / repetition | Request SHA-256 | Native-render SHA-256 |
| --- | --- | --- | --- |
| gemma3:27b / P1 | 180 / DEV-02 / 1 | `a8b4e1c52de60589b724d7cf72d48b72788d81124e470ac49dfffe9dc28681b6` | `3fbf9bc6ff70a894a0f6bc752ae09a45b56e29d8f2ccfc378e8fe67d76543e02` |
| gemma3:27b / P3 | 207 / DEV-02 / 1 | `52fe9e7d2a69638dacb4b47d8f5b94d1b605e1bcca3f83ec29b8dab9d9cf7098` | `753e62e252bc016ffbea0593fb3631ea3fb290ce53eccb6dad0d25a8e97e43a3` |
| gemma3:27b / P2 | 208 / DEV-02 / 1 | `a764487f60aa07841c1e748647afff1ec8f4ce8c38a2b454cf0aa4e437d697b9` | `55c206254c1b1afd065b4daa7e132201926bec947413bacc07fc23be313af513` |
| mistral-small3.2:24b / P1 | 249 / DEV-02 / 1 | `92d2dcdf000e8caacef46c99b94bd8f50ef848b9b1265d31ecccd8d65e127293` | `04bd07ae97128dd5164b78f424935cbee60c17454a0575bc83f8c55213245409` |
| mistral-small3.2:24b / P2 | 251 / DEV-02 / 1 | `7f0ab3992fbb369bd07a4364872423f7c07e6641786b3868ff574a6fe0ffd83c` | `44cea39d85b6dd7c179e05ac9a5d21d2bf1bcb3f644c2deeddbe7c53f172c65d` |
| mistral-small3.2:24b / P3 | 317 / DEV-02 / 1 | `f63d92da03466ca770401c0b6acb258f48fef2f372552b1351c67e4b7082f2de` | `67a4302bc1ad5e69e07dca80b3aa6e2bf0036dc7dfc00e53b1a38ed30ab10b2f` |

`ROOT_CAUSE_RECONSTRUCTION.json` records all 324 request matches and all native-render identities. `ROOT_CAUSE_EXAMPLES.json` includes exact original final content and response hashes for the representative runs. Qwen request artifacts are also included for comparison; its special native qwen3.5 renderer was not independently reimplemented here. The simple `/api/show` template `{{ .Prompt }}` is not its full effective framing. Its historical native render/tokenizer counts, empty closed thinking prefix, and final-answer-only outputs are retained in the qualification evidence.

## 4. Exact descriptive counts

**FACT FROM DATA.** “Valid” below means the original strict parser accepted the original complete content. “Shape after fence removal” is an in-memory descriptive inspection only. It does not mean the category verdicts are correct.

| Model | Runs | Originally valid | Parser failures | Fences | stop / length | At 512 | Output-token range |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:27b | 108 | 0 | 108 | 108 | 108 / 0 | 0 | 106–132 |
| mistral-small3.2:24b | 108 | 0 | 108 | 108 | 108 / 0 | 0 | 90–116 |
| qwen3.6:27b | 108 | 103 | 5 | 0 | 103 / 5 | 5 | 133–512 |

All Gemma/Mistral fenced outputs have **one opening ` ```json ` line and one closing ` ``` ` line**, valid/complete enclosed JSON, the exact `{c1,c2,c3} → {verdict,reason}` structure, legal verdict literals and nonblank reason strings. There are no duplicate keys, extra members, non-JSON constants, or text before/after the fence. Counts for each of these passing descriptive checks are 108/108 per model. Counts of external surrounding prose are 0/108 per model. The production parser rejects all originals with `INVALID_JSON` because the complete original content starts with a Markdown fence.

The inspection deletes only the two delimiter lines in a temporary string and applies strict JSON syntax plus explicit member/type checks. It never invokes the production parser on modified content and never compares these objects with references. No recovered semantic objects or predictions are exported.

### Per prompt, including Qwen control comparison

| Model | Prompt | Valid / failures | Fence rate | stop / length | At cap | Input tokens min / median / max | Output tokens min / median / max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:27b | P1 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1132 / 1156.5 / 1178 | 112 / 121.5 / 129 |
| gemma3:27b | P2 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1279 / 1303.5 / 1325 | 106 / 123.0 / 131 |
| gemma3:27b | P3 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1415 / 1439.5 / 1461 | 110 / 121.0 / 132 |
| mistral-small3.2:24b | P1 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1155 / 1168.0 / 1189 | 92 / 105.0 / 112 |
| mistral-small3.2:24b | P2 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1303 / 1316.0 / 1337 | 90 / 106.0 / 114 |
| mistral-small3.2:24b | P3 | 0 / 36 | 36/36 | 36 / 0 | 0 | 1447 / 1460.0 / 1481 | 95 / 106.0 / 116 |
| qwen3.6:27b | P1 | 33 / 3 | 0/36 | 33 / 3 | 3 | 1104 / 1122.5 / 1141 | 134 / 150.0 / 512 |
| qwen3.6:27b | P2 | 36 / 0 | 0/36 | 36 / 0 | 0 | 1246 / 1264.5 / 1283 | 133 / 149.0 / 446 |
| qwen3.6:27b | P3 | 34 / 2 | 0/36 | 34 / 2 | 2 | 1389 / 1407.5 / 1426 | 133 / 151.0 / 512 |

Qwen emitted syntactically valid raw JSON for 103/108 runs and no triple-backtick fences in any run. Its five invalid original outputs also begin as raw JSON. Gemma/Mistral wrapped every answer in fences under P1, P2 and P3: 36/36 per model/prompt, 100% throughout. This is a model/runtime-condition difference under common semantic instructions, not proof of an inherent family-wide property.

### Per case: Gemma and Mistral

Each case has nine runs per model (three prompts × three repetitions). In **every row**, all nine are fenced parser failures, all nine end with stop, all nine pass the fence-only syntax/shape inspection, and zero hit the cap or contain surrounding prose. The token ranges below include all nine runs.

| Model | Case | Runs = failures = fences = stop | Prompt-token range | Output-token range |
| --- | --- | --- | --- | --- |
| gemma3:27b | DEV-01 | 9 | 1178–1461 | 112–114 |
| gemma3:27b | DEV-02 | 9 | 1156–1439 | 112–117 |
| gemma3:27b | DEV-03 | 9 | 1156–1439 | 106–116 |
| gemma3:27b | DEV-04 | 9 | 1156–1439 | 128–131 |
| gemma3:27b | DEV-05 | 9 | 1157–1440 | 112–112 |
| gemma3:27b | DEV-06 | 9 | 1160–1443 | 114–126 |
| gemma3:27b | DEV-07 | 9 | 1163–1446 | 110–129 |
| gemma3:27b | DEV-08 | 9 | 1132–1415 | 120–126 |
| gemma3:27b | DEV-09 | 9 | 1159–1442 | 127–128 |
| gemma3:27b | DEV-10 | 9 | 1154–1437 | 127–128 |
| gemma3:27b | DEV-11 | 9 | 1163–1446 | 127–129 |
| gemma3:27b | DEV-12 | 9 | 1133–1416 | 112–132 |
| mistral-small3.2:24b | DEV-01 | 9 | 1189–1481 | 100–116 |
| mistral-small3.2:24b | DEV-02 | 9 | 1165–1457 | 94–110 |
| mistral-small3.2:24b | DEV-03 | 9 | 1165–1457 | 97–115 |
| mistral-small3.2:24b | DEV-04 | 9 | 1165–1457 | 97–110 |
| mistral-small3.2:24b | DEV-05 | 9 | 1166–1458 | 94–111 |
| mistral-small3.2:24b | DEV-06 | 9 | 1170–1462 | 92–109 |
| mistral-small3.2:24b | DEV-07 | 9 | 1188–1480 | 102–110 |
| mistral-small3.2:24b | DEV-08 | 9 | 1155–1447 | 103–109 |
| mistral-small3.2:24b | DEV-09 | 9 | 1183–1475 | 106–107 |
| mistral-small3.2:24b | DEV-10 | 9 | 1178–1470 | 106–108 |
| mistral-small3.2:24b | DEV-11 | 9 | 1188–1480 | 104–114 |
| mistral-small3.2:24b | DEV-12 | 9 | 1156–1448 | 90–102 |

### Per repetition

Each model/repetition has 36 runs. Every Gemma/Mistral row again has 36 fences, 36 parser failures, 36 stop completions, 36 fence-only syntax/shape matches, zero cap hits and zero surrounding prose.

| Model | Repetition / seed | Runs | Prompt-token range | Output tokens min / median / max |
| --- | --- | --- | --- | --- |
| gemma3:27b | 1 / 101 | 36 | 1132–1461 | 112 / 121.0 / 131 |
| gemma3:27b | 2 / 202 | 36 | 1132–1461 | 112 / 122.5 / 132 |
| gemma3:27b | 3 / 303 | 36 | 1132–1461 | 106 / 121.5 / 129 |
| mistral-small3.2:24b | 1 / 101 | 36 | 1155–1481 | 95 / 106.0 / 116 |
| mistral-small3.2:24b | 2 / 202 | 36 | 1155–1481 | 93 / 105.0 / 116 |
| mistral-small3.2:24b | 3 / 303 | 36 | 1155–1481 | 90 / 106.0 / 115 |

`ROOT_CAUSE_RUNS.json` contains every one of the 324 run envelopes' descriptive fields, including exact input/output tokens, cap flag, completion reason, fence status, before/after text flags and shape/syntax flags. `ROOT_CAUSE_GROUPS.json` supplies exact token-frequency histograms and counts for model, model×prompt, model×case, model×repetition, model×prompt×case, model×prompt×repetition and the full four-way crossing. Thus every Gemma/Mistral prompt×case cell is 3/3 fenced failures, and every prompt×case×repetition cell is 1/1; no aggregation hides an exception.

## 5. Token-limit failures are separate

| Run / attempt | Model | Prompt | Case | Repetition / seed | done_reason / output tokens | Original-content defect |
| --- | --- | --- | --- | --- | --- | --- |
| 13 / 13 | qwen3.6:27b | P1 | DEV-02 | 3 / 303 | length / 512 | INCOMPLETE_JSON_STRING_AT_CAP |
| 43 / 43 | qwen3.6:27b | P1 | DEV-02 | 2 / 202 | length / 512 | INCOMPLETE_JSON_STRING_AT_CAP |
| 47 / 47 | qwen3.6:27b | P3 | DEV-02 | 2 / 202 | length / 512 | EXTRA_TEXT_AFTER_JSON_AT_CAP |
| 58 / 58 | qwen3.6:27b | P1 | DEV-10 | 3 / 303 | length / 512 | EXTRA_TEXT_AFTER_JSON_AT_CAP |
| 108 / 108 | qwen3.6:27b | P3 | DEV-02 | 3 / 303 | length / 512 | INCOMPLETE_JSON_STRING_AT_CAP |

**FACT FROM DATA.** Exactly 5/324 outputs reached the 512-token cap: Qwen 5/108, Gemma 0/108, Mistral 0/108. All five have `done_reason=length`; all 216 fenced failures have `done_reason=stop`. The remaining 103 raw-JSON outputs also have stop. These are complete HTTP/provider envelopes even when their final content was truncated by the output budget.

**INFERENCE.** `num_predict=512` cannot materially explain either investigated model's 108/108 failures: Gemma's maximum is 132 and Mistral's 116. Adding token budget would not remove an already emitted forbidden opening fence. The three Qwen unterminated strings show actual output-budget exhaustion. The two extra-text cases combine format non-compliance with budget exhaustion: more space would not retroactively remove the extra text already emitted.

The evidence does not establish that 512 was globally unsuitable. It was sufficient for 319/324 normally completed outputs, including every Gemma/Mistral answer. Context capacity is separate: the maximum complete input+allowance was 1973 for Gemma and 1993 for Mistral, far below 32768; all 324 actual input-token counts match the qualified counts. No truncation/dropped-instruction evidence was found. This does not establish how any output would behave at a different cap.

## 6. Representative original outputs

These are exact `message.content` strings, not verified factual explanations. Outer four-backtick fences below are report formatting; any inner triple-backtick fences are part of the original model output. No content was repaired.

### Run 180: gemma3:27b, P1, DEV-02, repetition 1

Original status `parser_failure`, `done_reason=stop`, input tokens 1156, output tokens 112. Response SHA-256: `ddf258736af561ea737aec17c942f832c6f653b81e5290e08d8351a84878756f`.

````text
```json
{
  "c1": {
    "verdict": "PASS",
    "reason": "Status 200 matches documented response."
  },
  "c2": {
    "verdict": "PASS",
    "reason": "Content-Type application/json matches documented media type."
  },
  "c3": {
    "verdict": "PASS",
    "reason": "Body conforms to TypeValidatorResult schema."
  }
}
```
````

### Run 249: mistral-small3.2:24b, P1, DEV-02, repetition 1

Original status `parser_failure`, `done_reason=stop`, input tokens 1165, output tokens 106. Response SHA-256: `0629d7cb676de29668b02c3ea10d1c09612dded97f34ed8e6bd87e18d884c668`.

````text
```json
{
  "c1": {
    "verdict": "PASS",
    "reason": "Observed status 200 matches documented response"
  },
  "c2": {
    "verdict": "PASS",
    "reason": "Observed Content-Type application/json matches declared media type"
  },
  "c3": {
    "verdict": "FAIL",
    "reason": "Body does not conform to schema: missing required fields"
  }
}
```
````

### Run 1: qwen3.6:27b, P3, DEV-08, repetition 1

Original status `valid`, `done_reason=stop`, input tokens 1389, output tokens 151. Response SHA-256: `3b4041822a52443e8f1f8f1e5d58a549d48e725d9693d656b0a98b215935d6cc`.

````text
{
  "c1": {
    "verdict": "PASS",
    "reason": "The observed HTTP status 200 matches the documented response entry for status 200."
  },
  "c2": {
    "verdict": "PASS",
    "reason": "The observed Content-Type 'application/json' matches the declared media type 'application/json' in the selected response."
  },
  "c3": {
    "verdict": "PASS",
    "reason": "The body 'null' is valid JSON. The schema for the 200 response is an empty object {}, which permits any valid JSON instance."
  }
}
````

### Qwen cap examples (literal excerpts)

The following are exact trailing excerpts, not complete responses or completed JSON. Full originals and hashes remain in `raw_outputs.json`; the five run identities are in the table above.

Run 13, final 240 characters:

````text
 the applicable schema gives C3 FAIL'. Is 0 a valid int32? Yes. Is the JSON valid? Yes. Is the schema conformance met? Yes. So it should be PASS. Let me double check the 'nullable' definition. In OpenAPI 3.0, nullable means the value can be
````

Run 58, final 240 characters:

````text
TTP status 422 matches the documented response entry for status code 422."
  },
  "c2": {
    "verdict": "PASS",
    "reason": "The observed Content-Type 'application/json' matches the declared media type 'application/json' for the selected
````

## 7. Runtime/template anomaly hypotheses

| Hypothesis | Stored evidence and result | Remaining limit |
| --- | --- | --- |
| Gemma lost the output instruction | Refuted by full native render reconstruction: 108 matching hashes, full contract present. | It has native user framing, not a privileged native system role. Priority/salience effects are not separately measured. |
| Gemma role mapping is an accidental application change | Captured template explicitly maps both roles to user; D05 approved native templates and the accepted setup bound this capture. No runtime/template edit or source drift found. | A scientific concern about this choice could justify a future alternative condition, not retrospective relabeling as a proven implementation defect. |
| Mistral default SYSTEM competed with the supplied prompt | No concatenation: explicit experimental system replaces default in saved diagnostic and all matching study render hashes. | Model-internal compliance remains unobservable. |
| Stop tokens inserted Markdown fences or truncated the body | Native templates contain no triple-backtick fence insertion; Gemma stored stop is `<end_of_turn>`. Mistral stored parameter file contains only temperature 0.15; templates use native role/end delimiters. All fenced objects are closed, normal completions, well below cap. No evidence that delimiters inject or truncate fences. | `stop` is an aggregate completion reason; it does not identify the exact EOS/stop token or internal causal mechanism. |
| D07 options unintentionally differed across models | All 324 request hashes/options and stored run configurations agree. Only approved thinking policy differs. Nine historical slot snapshots show effective sampling, seed, context and output allowance. | Effective slot settings were observed on fabricated qualification calls, not independently persisted for every study call. |
| Model defaults overrode D07 | Gemma defaults temperature 1, top_k 64, top_p 0.95; Mistral temperature 0.15; Qwen temperature 1, top_k 20, top_p 0.95 and draft_num_predict 3. Explicit requests and diagnostic slots show D07 overrides: temperature 0.2, top_k 40, top_p 0.9, speculation off. | Frozen native defaults beyond D07 remain part of each model condition; universal computational equivalence is not claimed. |
| Context overflow removed instructions | All actual prompt counts equal stored full-render counts, all input+512 totals fit 32768 with large margins. | No per-run input token-ID trace is present; count agreement alone would not prove content, so the separate request/render hashes are essential. |
| Parser stripped/added content incorrectly | Original envelope content equals diagnostics and raw export. Strict parser consumes the entire string and rejects leading fences; provider does not insert them. | Native provider behavior is bound to the captured runtime; unseen low-level defects cannot be universally disproved. |

**FACT FROM IMPLEMENTATION/RUNTIME EVIDENCE.** Captured runtime is Ollama 0.34.4, native runner 0.4.1-dev/build 1/commit 161755f29, Q4_K_M models. See `docs/runtime_qualification_2026-09-26/{report.md,source_review.json,*_slots.json,*_params.txt,*_show.json,*_diagnostic_render.json}`. The accepted runner's `accepted_comparison.py::run_accepted` invokes frozen-source/context checks and `freeze.py::verify_live` before each attempt; the latter checks runtime binaries/version, model digest and complete native show metadata. This is evidence about the guarded code path, not a separately retained per-call effective-sampler trace.

The historical source review says request options override model defaults; current analysis independently checks saved slots. The exact external runner source was not fully available to the historical qualification, so this report does not claim a new complete source audit or access to internal token probabilities.

## 8. Per-model classification

### Gemma 3 27B

- **FACT FROM DATA:** 108/108 parser failures; 108/108 fenced complete JSON objects; 108/108 stop; 0/108 cap; 106–132 output tokens; no surrounding prose; all fence-only structure checks pass.
- **FACT FROM IMPLEMENTATION/RUNTIME EVIDENCE:** All three frozen output contracts are explicit and remain intact in the effective native text. The native system-to-user mapping is captured, hash-matched and part of the approved condition. All request, native-render and prompt-token checks match.
- **INFERENCE:** The proximate failure is systematic violation of the requested surface format under the frozen native runtime condition. Token shortage and absent output instructions do not explain it.
- **CLASSIFICATION: MODEL FORMAT NON-COMPLIANCE.** No demonstrated SETUP DEFECT; no TOKEN LIMIT ISSUE for these runs. **OPEN QUESTION:** how much the two-user-turn framing contributed causally. This does not negate the observed format violation or establish an accidental setup defect.

### Mistral Small 3.2 24B

- **FACT FROM DATA:** 108/108 parser failures; 108/108 fenced complete JSON objects; 108/108 stop; 0/108 cap; 90–116 output tokens; no surrounding prose; all fence-only structure checks pass.
- **FACT FROM IMPLEMENTATION/RUNTIME EVIDENCE:** Complete frozen instructions occupy the explicit native system frame. The stored default SYSTEM text is absent from the matched effective renders. Exact requests, native-render hashes, prompt-token counts and D07 evidence agree.
- **INFERENCE:** Systematic surface-format non-compliance is the best supported explanation. Default-system conflict, dropped instructions and output-budget exhaustion are unsupported.
- **CLASSIFICATION: MODEL FORMAT NON-COMPLIANCE.** No demonstrated SETUP DEFECT; no TOKEN LIMIT ISSUE for these runs. **OPEN QUESTION:** the internal reason the model preferred fences, and the causal contribution of model/template/default interactions, cannot be isolated from these outputs.

These findings concern end-to-end formatting reliability of the frozen detector condition. They do not establish that the enclosed category decisions would be accurate; no semantic assessment of rejected content was performed.

## 9. Scientific implications and exact next step

**Recommended next step — NEW PROPOSAL for author decision:** Review and record acceptance/rejection of this root-cause finding. Preserve Experiment 1 and its original strict-parser outcomes unchanged. On this evidence, do not repair Gemma/Mistral or rerun them merely because they used fences. Continue the existing protocol's author review of the completed prompt comparison/Gate C before authorizing any subsequent sensitivity work. This analysis does not choose a prompt, create approval, or start sensitivity.

The author should explicitly distinguish the existing research question (end-to-end detector under prompt-only JSON) from a possible new question (semantic ability under a changed output interface). If format reliability prevents the intended semantic comparison, that is a limitation to document. A redesigned method may be legitimate prospectively, but it requires a new documented design, freeze and comparison rather than replacement of the observed failures.

| Possible result | What would follow scientifically |
| --- | --- |
| SETUP DEFECT demonstrated later | Preserve the old experiment, label the affected results invalid for claims about the intended configuration, define the exact defect and affected scope, fix and requalify it, create a new accepted setup, and repeat all affected model × P1/P2/P3 × case × repetition cells. If a shared method component changes, repeat all model conditions needed for a fair common comparison. Do not rerun only failed cells. No such corrective rerun is justified by a demonstrated defect here. |
| MODEL FORMAT NON-COMPLIANCE (current finding) | Failures remain failures in planned-run denominators. Removing fences, adding JSON mode, altering prompts or changing native role handling after observing results defines a new method/condition. Do not retroactively rescore, substitute outcomes or treat hypothetical syntax success as semantic correctness. Any prospective method change needs documented author justification and a new frozen comparison. |
| TOKEN LIMIT ISSUE | For the three incomplete Qwen strings, 512 terminated generation; the two extra-text outputs already violate the format. Existing observations remain valid outcomes of the frozen 512-token condition. A decision to enlarge the common budget changes D07 and needs requalification of request/context/runtime, a new freeze and complete comparable reruns. More tokens are not demonstrated to fix the errors. There is no token-limit rationale for rerunning Gemma/Mistral. |
| OPEN QUESTION | First inspect the already retained native texts, source hashes, original requests/spools and diagnostic slots. If a specific delivery or runtime doubt remains, additional non-destructive evidence would be original archived request/provenance bytes from SELECT-only DB export, any already retained per-attempt runner logs/slot snapshots or token traces, and exact version-matched native source. Do not substitute current model defaults for historical evidence. If such historical records were never captured, purely read-only retrospective analysis cannot recover them. Establishing whether alternative Gemma framing causes better adherence requires a separately authorized prospective controlled diagnostic; it cannot be inferred or run within this task. |

There is no need for new generations to confirm the observed fence counts, prompt wording or recorded native rendering: these are already verified. The remaining causal uncertainty should be stated as a limitation, not converted into an invented root cause.

## 10. Reproduction, artifacts and preservation

`root_cause_reproduce.py` performs only offline filesystem reads plus writing a **new** output directory. It imports the unchanged lossless input renderer/request builder to reconstruct requests; it never invokes a provider, database, tokenizer endpoint, evaluator, or experimental output parser. The fence-only inspection uses standard-library JSON in temporary memory and exports only descriptive booleans/counts.

```sh
PYTHONDONTWRITEBYTECODE=1   /Users/aerfurt/University/Bachelor/rest_api_checker/.venv/bin/python   /Users/aerfurt/University/Bachelor/rest_api_checker/docs/experiment_evidence/prompt_comparison_exp1_2026-09-26/root_cause_reproduce.py   /Users/aerfurt/University/Bachelor/rest_api_checker   /Users/aerfurt/University/Bachelor/bachelor_rest_api_checker   /private/tmp/rac-root-cause-new-replay
```

The destination must not already exist. Reproduction rechecks original hashes before analysis and regenerates the summary, all run/group data, reconstruction indexes and representative native/request artifacts. It does not regenerate this prose report or execute the old collection/evaluation scripts. A second clean replay was compared byte-for-byte with all 20 generated descriptive/request/native artifacts.

Deliverables:

- `ROOT_CAUSE_GEMMA_MISTRAL.md`: this source-labeled report and exact raw examples.
- `ROOT_CAUSE_SUMMARY.json`: top-level counts, hashes, qualifications and classification.
- `ROOT_CAUSE_RUNS.json`, `ROOT_CAUSE_GROUPS.json`: every run and all requested breakdowns, including exact token histograms.
- `ROOT_CAUSE_RECONSTRUCTION.json`, `ROOT_CAUSE_EXAMPLES.json`: per-request bindings and representative original outputs.
- Nine `*_request.json` and six `*_native.txt` representative reconstruction files.
- `root_cause_reproduce.py`: deterministic, offline reproduction.
- `ROOT_CAUSE_PRESERVATION.json`: before/after hashes for 965 pre-existing protected repository/research/artifact/spool files.
- `ROOT_CAUSE_SHA256SUMS`: a separate manifest for this additive analysis. The old `SHA256SUMS` is preserved unchanged.

**Preservation confirmation:** No pre-existing protected file changed. No prompts, strict parser, templates, renderer, provider, run configuration, dataset, reference, OpenAPI, frozen evaluator or experiment output was modified. No new LLM generation, comparison rerun, sensitivity run, experiment/database write, recovered prediction or rescoring was executed. Only new analysis deliverables were added. No Git commit, branch switch or experiment acceptance was performed.
