# Implementation Step

Use this procedure for normal implementation tasks in `rest_api_checker`.

## Procedure

1. Read `AGENTS.md`.
2. Read `docs/implementation_state.md`.
3. Identify the minimum research artifact(s) needed for the task.
   Do not reread the entire research repository unless necessary.
4. Inspect the existing implementation and relevant tests.
5. State the smallest intended implementation change.
6. Check whether the task changes research semantics.
   If yes or unclear, follow `research-protocol-guard` and stop.
7. Implement only the required behavior.
8. Add or update focused tests.
9. Run targeted tests.
10. Run the full test suite.
11. Run `git diff --check`.
12. Inspect the complete diff and `git status`.
13. Update `docs/implementation_state.md` only if project state or milestone
    meaningfully changed.
14. Commit the completed step.
15. Stop. Do not continue into the next milestone automatically.

## Constraints

- Do not introduce architecture for hypothetical future requirements.
- Do not duplicate methodology text in source code or technical docs.
  Reference the research artifact instead.
- Preserve existing qualified behavior unless an explicit research decision
  authorizes a change.
- Do not derive reference labels from mutation intent.
- Do not tune implementation against future final LLM test results.

## Definition of Done

A step is done only when:

- requested behavior is implemented,
- relevant tests pass,
- the full suite passes,
- Q01-Q26 remain valid when oracle behavior is touched,
- provenance requirements are preserved,
- documentation/state is updated if needed,
- the diff contains no unrelated changes,
- the work is committed on its branch.
