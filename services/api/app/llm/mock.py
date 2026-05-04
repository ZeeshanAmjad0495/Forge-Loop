class MockLLMProvider:
    provider_name = "mock"
    model_name = "mock-planning-model"

    def generate_text(self, prompt: str) -> str:
        return """\
# Implementation Brief

## 1. Requirement Summary

Implement the changes described in the ticket.

## 2. Business Goal

Deliver the requested functionality to meet user needs.

## 3. Assumptions

- Existing system behaviour is stable.
- No breaking changes to public interfaces.

## 4. Ambiguities / Questions

- Confirm acceptance criteria with stakeholder.

## 5. Affected Areas

- To be determined after further investigation.

## 6. Technical Approach

- Implement the minimal change that satisfies the requirement.

## 7. Task Breakdown

- [ ] Investigate affected code paths.
- [ ] Implement change.
- [ ] Write tests.
- [ ] Review and merge.

## 8. Test Strategy

- Unit tests for new logic.
- Integration test for the affected endpoint.

## 9. Edge Cases

- Empty input.
- Concurrent requests.

## 10. Risks

- Unintended side effects in adjacent features.

## 11. Definition of Done

- All tests pass.
- Code reviewed and merged.
- No regressions.

## 12. Human Approval Points

- Stakeholder sign-off before release.
"""
