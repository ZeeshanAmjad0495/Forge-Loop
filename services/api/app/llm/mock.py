import json

_MOCK_DECOMPOSITION_RESPONSE = json.dumps(
    {
        "dev_tasks": [
            {
                "title": "Implement backend API endpoint",
                "description": "Add the new API endpoint with request validation and error handling.",
                "task_type": "backend",
                "priority": "high",
                "acceptance_criteria": [
                    "Endpoint returns correct status codes",
                    "Input validation rejects malformed requests",
                ],
                "definition_of_done": [
                    "Unit tests pass",
                    "Integration test passes",
                    "Code reviewed",
                ],
                "qa_required": True,
                "suggested_agent_type": "backend_coder",
                "depends_on": [1],
                "subtasks": [
                    {
                        "title": "Write request/response models",
                        "description": "Define Pydantic models for request and response bodies.",
                        "acceptance_criteria": ["Models pass mypy"],
                        "qa_required": False,
                    }
                ],
            },
            {
                "title": "Update API documentation",
                "description": "Document the new endpoint in the project README and OpenAPI schema.",
                "task_type": "documentation",
                "priority": "low",
                "acceptance_criteria": ["README describes endpoint", "OpenAPI spec is accurate"],
                "definition_of_done": ["Documentation merged"],
                "qa_required": False,
                "suggested_agent_type": None,
                "depends_on": [],
                "subtasks": [],
            },
        ]
    },
    indent=2,
)

_MOCK_ANALYSIS_RESPONSE = json.dumps(
    {
        "summary": "Implement the changes described in the ticket.",
        "clarified_requirement": "The system should behave as specified in the ticket description with no ambiguities assumed.",
        "assumptions": [
            "Existing system behaviour is stable.",
            "No breaking changes to public interfaces.",
        ],
        "ambiguities": [
            "Exact acceptance criteria not specified in the ticket.",
        ],
        "clarification_questions": [],
        "risks": [
            "Unintended side effects in adjacent features.",
        ],
        "affected_areas": [
            "To be determined after further codebase investigation.",
        ],
        "readiness": "ready_for_planning",
    },
    indent=2,
)


class MockLLMProvider:
    provider_name = "mock"
    model_name = "mock-planning-model"

    def generate_text(self, prompt: str) -> str:
        if "TASK_DECOMPOSITION_AGENT" in prompt:
            return _MOCK_DECOMPOSITION_RESPONSE
        if "REQUIREMENT_ANALYSIS_AGENT" in prompt:
            return _MOCK_ANALYSIS_RESPONSE
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
