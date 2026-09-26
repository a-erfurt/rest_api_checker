# Sensitivity freeze preparation

This is a candidate-only addition. It records no acceptance and cannot dispatch
requests or persist an experiment. The original comparison execution allowlist
continues to reject the new variant.

After committing the preparation code, run:

```sh
uv run python tools/sensitivity_freeze/prepare.py
```

The command reads the dedicated application credentials from the established
external location; credentials are never archived. It checks the accepted
comparison source closure, released dataset/references, original P2 requests,
current runtime identities and the exact research approval record. All 108
variant requests differ only in their approved system text.

The schedule preserves the P2 subsequence of comparison-schedule-v1 (SHA-256
Fisher-Yates, seed 20260925, qwen/gemma/mistral block order), renaming the prompt
and numbering 1..108. This keeps original case/model/repetition pairing and
seeds 101/202/303. This deterministic implementation choice is subject to the
exact candidate review; it introduces no new scientific policy.

The previously qualified Ollama render-only path returns before completion.
Every repetition is measured independently with the installed native runner's
/tokenize endpoint (add_special=true, parse_special=true); raw render responses
and token IDs are archived. Metadata, binary and model identities are checked
before/after. No fabricated completion or new token-parity generation is used.
The unchanged historical parity evidence remains bound in the source closure.

Outputs are immutable local files under artifacts/sensitivity_freeze_candidate_v1.
An existing directory is refused rather than overwritten. candidate.json binds
its artifacts and exact implementation/research commits; verification.json binds
the candidate hash. The historical equivalence review is retained unchanged,
with current approval in a separate research record.

## Execution blockers

- Explicit review/acceptance of the exact candidate hash is pending.
- The sensitivity execution adapter is not implemented.
- The current comparison evaluator is bound unchanged; the D11 sensitivity
  evaluator is not implemented. Protocol sections 6 and 9 remain its authority.

Consequently this is a reviewable preparation candidate, not an execution
release. Implementing those adapters requires a separately scoped step without
scientific-policy changes, tests, a new commit and a newly reviewed freeze
binding. Approval of this candidate alone cannot enable existing comparison code
to execute sensitivity. Reuse the original 108 P2 outcomes, including failures;
never rerun the baseline or overwrite Experiment 1/report 1.

## Preparation test evidence

Focused approval/schedule/request/network safeguards: 16 passed.
Full suite: 611 passed, 94 skipped (opt-in SQL checks), 3 failed. All three
failures assert that the old comparison preflight returns BLOCKED, while it
returns FAIL after post-freeze changes. The accepted comparison candidate binds
commit aecae65851e1fdeca440a9576f755510764c11a7, whereas the task began at
9b65a0fd5d1c10ad4012c692e5b76bc0e25e0014. Its historical source closure matches
exactly when the new sensitivity module is excluded. Thus the prior HEAD already
violated the old exact-execution-commit guard, and the new module additionally
expands the source inventory. These historical tests/records were not changed.

Affected tests: test_json_preflight_truthful,
test_preflight_actual_backend_stays_blocked, and
test_captured_readiness_preserves_limitations_and_author_gate.
Candidate-specific live read-only verification is recorded separately beside
the generated candidate; it does not claim a green full suite.
