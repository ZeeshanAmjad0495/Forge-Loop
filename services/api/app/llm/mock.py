class MockLLMProvider:
    provider_name = "mock"
    model_name = "mock-planning-model"

    def generate_text(self, prompt: str) -> str:
        return """\
# Implementation Brief

## 1. Requirement Summary

Implement the changes described in the ticket.

## 2. Clarified Behavior

- The system should behave as specified in the ticket description.
- No changes to existing public interfaces unless explicitly required.

## 3. Assumptions

- Existing system behaviour is stable.
- No breaking changes to public interfaces.
- Dependencies and environment are unchanged.

## 4. Ambiguities / Questions

- Confirm exact acceptance criteria with stakeholder before starting.
- Clarify any edge cases not covered in the ticket description.

## 5. Affected Areas

- To be determined after further investigation of the codebase.

## 6. Developer Task Breakdown

- [ ] Read and understand the ticket requirements.
- [ ] Identify affected code paths and modules.
- [ ] Write failing tests first (TDD approach recommended).
- [ ] Implement the minimal change that satisfies the requirement.
- [ ] Verify all existing tests still pass.
- [ ] Open a pull request for review.

## 7. Suggested Implementation Approach

- Prefer the smallest safe change that satisfies the requirement.
- Avoid touching unrelated code.
- If a pattern already exists in the codebase for this type of change, follow it.

## 8. Test Strategy

- Unit tests for any new logic introduced.
- Integration test for the affected endpoint or flow.
- Ensure no existing tests regress.

## 9. Acceptance Criteria

- [ ] The feature behaves as described in the ticket.
- [ ] All new and existing tests pass.
- [ ] Code has been reviewed and approved.
- [ ] No unintended side effects observed.

## 10. Edge Cases

- Empty or missing input values.
- Concurrent requests to the same resource.
- Unexpected data types or formats.

## 11. Risks

- Unintended side effects in adjacent features.
- Missing context about existing system behaviour.

## 12. Rollback / Safety Notes

- Changes should be small enough to revert with a single git revert.
- Feature flag or environment variable can be used to disable if needed.

## 13. Human Approval Points

- Stakeholder sign-off on acceptance criteria before implementation begins.
- Code review approval before merging to main.
- QA sign-off before releasing to production.

## 14. PR Checklist

- [ ] Tests added or updated.
- [ ] No secrets or credentials committed.
- [ ] Documentation updated if behaviour changed.
- [ ] PR description explains the change and links to the ticket.
"""
