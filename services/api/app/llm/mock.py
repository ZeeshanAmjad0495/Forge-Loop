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

_MOCK_REQUIREMENT_GENERATION_RESPONSE = json.dumps(
    {
        "requirements": [
            {
                "title": "CSV upload validation",
                "problem_statement": "Users need confidence that uploaded CSV files match the expected schema before downstream processing.",
                "business_goal": "Reduce data-quality incidents and support handling time caused by malformed input files.",
                "target_users": ["Operations analyst", "Data steward"],
                "functional_requirements": [
                    "Accept CSV file uploads up to a configurable size limit.",
                    "Validate header row against the expected schema.",
                    "Validate each row against type and required-field rules.",
                ],
                "non_functional_requirements": [
                    "Validation result must return within 5 seconds for files up to 10 MB.",
                ],
                "acceptance_criteria": [
                    "A file with a missing required column is rejected with a clear error.",
                    "A file with all valid rows is accepted and queued for processing.",
                ],
                "constraints": [
                    "Validation runs synchronously inside the upload request.",
                ],
                "non_goals": [
                    "Automatically correcting malformed rows.",
                ],
                "assumptions": [
                    "Schema definition is provided per project and does not change per upload.",
                ],
            },
            {
                "title": "Validation error reporting",
                "problem_statement": "When uploads fail validation, users do not have enough information to fix the file and retry.",
                "business_goal": "Decrease retry friction and improve self-service correction of upload errors.",
                "target_users": ["Operations analyst"],
                "functional_requirements": [
                    "Return a structured list of validation errors per failed row.",
                    "Include the row number, column, and reason for each error.",
                ],
                "non_functional_requirements": [
                    "Error payload must remain readable for files with up to 1000 errors.",
                ],
                "acceptance_criteria": [
                    "A failed upload returns at least one error entry per failing row.",
                    "Each error entry includes row, column, and reason fields.",
                ],
                "constraints": [],
                "non_goals": [
                    "Surfacing internal stack traces to end users.",
                ],
                "assumptions": [
                    "Error UI is rendered by the existing frontend error panel.",
                ],
            },
            {
                "title": "Configurable validation rules",
                "problem_statement": "Different projects need slightly different validation rules but currently rules are hardcoded.",
                "business_goal": "Allow operations to onboard new file formats without code changes.",
                "target_users": ["Operations admin"],
                "functional_requirements": [
                    "Allow admins to define required columns per project.",
                    "Allow admins to define type checks per column.",
                ],
                "non_functional_requirements": [
                    "Rule changes must take effect on the next upload without service restart.",
                ],
                "acceptance_criteria": [
                    "An admin can mark a column as required and the next upload enforces it.",
                ],
                "constraints": [
                    "Rules are scoped to a single project.",
                ],
                "non_goals": [
                    "Cross-project rule inheritance.",
                ],
                "assumptions": [
                    "Admin authentication is handled by the existing auth flow.",
                ],
            },
        ]
    },
    indent=2,
)

_MOCK_CI_FAILURE_ANALYSIS_RESPONSE = """\
# CI Failure Analysis

## 1. Failure Summary

The CI job failed during the test phase. The exact failing test is not
identified in the supplied logs excerpt and should be confirmed from the full
job output.

## 2. Likely Root Causes

- A recent code change altered behaviour covered by an existing test.
- A flaky test sensitive to timing or external state.
- An environment or dependency drift in the CI runner.

## 3. Failure Category

code_regression — most likely, pending confirmation from the full logs.

## 4. Affected Areas

- The module or package referenced by the failing test.
- Any code paths recently modified on the failing branch.

## 5. Suggested Debugging Steps

- Re-run the job locally on the same commit to reproduce.
- Inspect the failing test output and recent diffs on the branch.
- Compare against the last known-passing commit on the target branch.

## 6. Suggested ForgeLoop Follow-up Action

Open a dev task to investigate and fix the failing test; do not auto-merge.

## 7. Human Review Required

yes — failures require a human owner before any remediation.
"""

_MOCK_MEMORY_LEARNING_RESPONSE = """\
# Project Memory Learning

## Summary

Two durable lessons surface from this evidence: a recurring failure pattern
worth recording for future triage, and a testing rule the team should adopt
to prevent the same regression. Confidence is moderate pending a human
review of the source.

## Candidates

```json
[
  {
    "memory_type": "known_failure_pattern",
    "title": "Test phase regression after recent diff",
    "content": "When CI fails in the test phase shortly after a code diff on the same branch, the most likely cause is a regression in the changed module. Re-run locally before triaging further.",
    "tags": ["ci", "regression"],
    "confidence": 0.6
  },
  {
    "memory_type": "testing_rule",
    "title": "Compare against last known-passing commit",
    "content": "When a test suddenly fails on a feature branch, compare the failing test output against the last known-passing commit on the target branch before assuming a flake.",
    "tags": ["testing", "triage"],
    "confidence": 0.7
  }
]
```
"""

_MOCK_INCIDENT_TRIAGE_RESPONSE = """\
# Incident Triage Brief

## 1. Incident Summary

The incident describes an operational problem that needs human triage. The
exact production state is not known from the supplied evidence and must be
confirmed by an on-call engineer before any remediation.

## 2. Impact Assessment

Impact appears scoped to the affected area listed on the incident. Confirm
blast radius (users, regions, dependent services) before acting.

## 3. Likely Root Causes

- A recent code change altered behaviour of the affected component.
- A configuration drift between the working environment and production.
- An external dependency or upstream service is degraded.

## 4. Uncertainty / Missing Evidence

- Full production logs covering the failure window are not attached.
- Recent deploys, config changes, and feature flag flips are not listed.
- Metrics and dashboards have not been linked.

## 5. Immediate Safe Actions

- Acknowledge the incident and assign a human owner.
- Capture a short timeline of what changed in the last 24 hours.
- Preserve current production state; do not auto-restart.

## 6. Remediation Plan

- Identify the change set most likely responsible.
- Prepare a small, reviewable fix on a branch (human-driven, not automated).
- Plan a controlled rollback path before any forward fix is deployed.

## 7. Prevention Actions

- Add a regression test covering the failure mode.
- Add monitoring / alerting on the affected signal if not already present.
- Update project memory with the incident and resolution after closure.

## 8. Affected Areas

- The component or service named in the incident.
- Adjacent components consuming its output.

## 9. Suggested ForgeLoop Follow-up Work Item

Open a remediation dev task linked to this incident, requiring human approval
before any coding runner picks it up. Do not auto-merge or auto-deploy.

## 10. Human Approval Points

- Approval to begin remediation work.
- Approval of the proposed fix before merge.
- Approval of any deployment or rollback action.

## 11. Failure Category

needs_human_review — pending confirmation from production logs and recent
change history.
"""

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
        if "REQUIREMENT_GENERATION_AGENT" in prompt:
            return _MOCK_REQUIREMENT_GENERATION_RESPONSE
        if "REQUIREMENT_ANALYSIS_AGENT" in prompt:
            return _MOCK_ANALYSIS_RESPONSE
        if "CI Failure Analysis" in prompt:
            return _MOCK_CI_FAILURE_ANALYSIS_RESPONSE
        if "Incident Triage Brief" in prompt:
            return _MOCK_INCIDENT_TRIAGE_RESPONSE
        if "Project Memory Learning" in prompt:
            return _MOCK_MEMORY_LEARNING_RESPONSE
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
