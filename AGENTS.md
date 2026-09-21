# AGENTS.md

## Project purpose

This repository implements the experimental system for the bachelor thesis:

"Evaluating LLM-Based Detection of Validation Response Contract Inconsistencies in REST APIs"

It is a research evaluation system, not a commercial product.
Implement only what is needed to answer the research questions.

## Research authority

Research repository, READ ONLY:

/Users/aerfurt/University/Bachelor/bachelor_rest_api_checker

Relevant approved methodology lives primarily in:

- 03_research_design/research_design_v2.md
- 03_research_design/reference_oracle_protocol_v1.md
- 03_research_design/oracle_qualification_review_v1.md
- 03_research_design/fault_model_v1.md

Do not silently redefine research methodology in implementation code.

## Core methodological constraints

- OpenAPI is the only API-specific contract authority.
- API source code is not a contract authority.
- The deterministic Reference Oracle is a measurement/reference instrument,
  not a competing detector.
- Reference labels must never be derived from:
  - fault IDs,
  - intended mutation categories,
  - LLM outputs,
  - source code,
  - legacy labels.
- Q01-Q26 define the approved oracle qualification behavior.
- Do not change PASS / FAIL / NOT_APPLICABLE semantics without an explicit
  research decision.
- Synthetic fault intent is not reference truth. The resulting artifact must
  be evaluated by the qualified Reference Oracle.

## Engineering principles

- Python 3.12.
- Use uv and pyproject.toml.
- Prefer established validators over custom schema-validation logic.
- Keep implementations minimal and explicit.
- Avoid speculative abstractions and premature generic frameworks.
- Do not add databases, UIs, plugin systems, provider abstractions, or similar
  infrastructure until an approved experiment step requires them.
- Preserve raw evidence and provenance needed for reproducibility.
- Code and technical documentation are written in English.

## Testing

For behavior changes:

1. Add or update focused tests.
2. Run targeted tests.
3. Run the full test suite before commit when feasible.
4. Q01-Q26 must remain green unless methodology was explicitly revised.

Never update tests merely to make a changed implementation pass when the
research protocol still requires the old behavior.

## Git workflow

- Implementation work uses a dedicated feature/chore branch.
- Commit before review.
- Keep branches after merge unless explicitly requested otherwise.
- Commit messages must not mention AI, Codex, agents, or assistants.
- Do not modify the research repository from this repository.

## Methodology guard

If implementation requires a scientific/methodological decision that is not
already resolved, STOP before changing semantics.

Use:

- `.codex/skills/implementation-step/SKILL.md`
- `.codex/skills/research-protocol-guard/SKILL.md`

Read `docs/implementation_state.md` before starting an implementation step.
