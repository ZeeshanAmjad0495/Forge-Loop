# Release 11 — Research + Architecture Improvement Loop

Status: complete (Tasks 63–69). MVP-foundation grade; not commit-pushed yet
pending human review.

## Tasks completed

- **Task 63 — ResearchScout agent foundation**: store/generate structured
  research briefs (manual or provider-assisted via the existing LLM provider
  abstraction; tests mock the provider).
- **Task 64 — Research source cache**: durable source records (paper, docs,
  blog, repo, etc.) with trust level, tags, and optional cache_key. No
  network fetching.
- **Task 65 — Architecture Review Agent foundation**: structured review
  briefs for projects, repositories, or ForgeLoop itself. Optional
  provider-assisted generation; no automatic code changes.
- **Task 66 — Improvement proposal workflow**: human-approved proposals
  with status state machine (proposed → approved/rejected/deferred →
  implemented/archived). Source-derivable from briefs and reviews. No
  execution.
- **Task 67 — Architecture Decision Records (ADRs)**: long-term decision
  memory with transitions proposed → accepted/rejected → deprecated →
  superseded. Optional creation from an approved improvement proposal.
- **Task 68 — Experiment runner for proposed changes**: lightweight
  ExperimentPlan + ExperimentRun records. Tracks baseline/result metrics
  and a decision; never executes experiments.
- **Task 69 — Post-project retrospective generator**: ProjectRetrospective
  records linked to projects and (optionally) build trials. Provider-assisted
  generation is mocked in tests; can spawn improvement proposals via an
  explicit endpoint, with the proposal linked back to the retrospective.

## Entities added

- `ResearchBrief`, `ResearchSource` (`models/research.py`)
- `ArchitectureReview` (`models/architecture.py`)
- `ImprovementProposal` (`models/improvements.py`)
- `ArchitectureDecisionRecord` (`models/adr.py`)
- `ExperimentPlan`, `ExperimentRun` (`models/experiments.py`)
- `ProjectRetrospective` (`models/retrospectives.py`)

Each entity ships with:

- A `Protocol` repository interface and in-memory + Firestore implementations
  in `services/api/app/repositories.py`.
- A MongoDB implementation in `services/api/app/repositories_mongo.py` with
  appropriate indexes added to `_INDEX_PLAN`.
- Wiring through the `Repositories` dataclass, `get_repositories()` factory,
  and `repositories_state.py` singletons.

## Audit actions and artifact types added

New `AuditAction` values:

- `research_brief_created/generated/updated/archived`
- `research_source_created/updated/deleted`
- `architecture_review_created/generated/updated/archived`
- `improvement_proposal_created/updated/approved/rejected/deferred/implemented/archived`
- `architecture_decision_created/updated/accepted/rejected/deprecated/superseded`
- `experiment_plan_created/updated/approved/rejected`
- `experiment_run_created/updated/completed`
- `project_retrospective_created/generated/updated/archived`

New `Artifact.artifact_type` values:

- `research_brief`
- `architecture_review`
- `project_retrospective`

## APIs added

ResearchScout (Task 63):

- `POST /research-briefs`, `GET /research-briefs`
- `GET /research-briefs/{brief_id}`, `PATCH /research-briefs/{brief_id}`
- `POST /research-briefs/{brief_id}/archive`
- `POST /research-briefs/generate?provider_name=...`
- `GET /projects/{project_id}/research-briefs`

Research source cache (Task 64):

- `POST /research-sources`, `GET /research-sources`
- `GET /research-sources/{source_id}`, `PATCH /research-sources/{source_id}`
- `GET /projects/{project_id}/research-sources`
- `POST /research-briefs/{brief_id}/sources/{source_id}` (idempotent attach)

Architecture Review Agent (Task 65):

- `POST /architecture-reviews`, `GET /architecture-reviews`
- `GET /architecture-reviews/{review_id}`, `PATCH /architecture-reviews/{review_id}`
- `POST /architecture-reviews/{review_id}/archive`
- `POST /architecture-reviews/generate?provider_name=...`
- `GET /projects/{project_id}/architecture-reviews`

Improvement proposals (Task 66):

- `POST /improvement-proposals`, `GET /improvement-proposals`
- `GET /improvement-proposals/{proposal_id}`, `PATCH /improvement-proposals/{proposal_id}`
- `POST /improvement-proposals/{proposal_id}/approve|reject|defer|mark-implemented|archive`
- `POST /research-briefs/{brief_id}/improvement-proposals`
- `POST /architecture-reviews/{review_id}/improvement-proposals`
- `GET /projects/{project_id}/improvement-proposals`

Architecture Decision Records (Task 67):

- `POST /architecture-decisions`, `GET /architecture-decisions`
- `GET /architecture-decisions/{adr_id}`, `PATCH /architecture-decisions/{adr_id}`
- `POST /architecture-decisions/{adr_id}/accept|reject|deprecate|supersede`
- `POST /improvement-proposals/{proposal_id}/architecture-decision`
- `GET /projects/{project_id}/architecture-decisions`

Experiment runner (Task 68):

- `POST /experiment-plans`, `GET /experiment-plans`
- `GET /experiment-plans/{plan_id}`, `PATCH /experiment-plans/{plan_id}`
- `POST /experiment-plans/{plan_id}/approve|reject`
- `POST /experiment-plans/{plan_id}/runs`, `GET /experiment-plans/{plan_id}/runs`
- `GET /experiment-runs/{run_id}`, `PATCH /experiment-runs/{run_id}`
- `POST /experiment-runs/{run_id}/complete`
- `GET /projects/{project_id}/experiment-plans`

Retrospectives (Task 69):

- `POST /projects/{project_id}/retrospectives`, `GET /projects/{project_id}/retrospectives`
- `GET /retrospectives/{retrospective_id}`, `PATCH /retrospectives/{retrospective_id}`
- `POST /retrospectives/{retrospective_id}/archive`
- `POST /build-trials/{trial_id}/retrospective/generate?provider_name=...`
- `POST /retrospectives/{retrospective_id}/improvement-proposals`

## Tests

Full backend suite run after Task 69:

```
1051 passed, 1 skipped in 13.39s
```

New test modules:

- `tests/test_research_scout.py`
- `tests/test_research_sources.py`
- `tests/test_architecture_reviews.py`
- `tests/test_improvement_proposals.py`
- `tests/test_architecture_decisions.py`
- `tests/test_experiments.py`
- `tests/test_retrospectives.py`

All Release 11 tests stub the LLM provider (no real LLM/network/GCP/Mongo
calls). The Mongo parity test (`tests/test_repositories_mongo_parity.py`)
covers the new repositories via `mongomock`.

Frontend was not modified in Release 11. Frontend build was therefore not
run, per the release rules.

## Known follow-ups (deliberately out of scope)

- Automatic web crawling / live source fetching.
- Background research/architecture-review schedulers.
- Auto-creation of improvement proposals from briefs/reviews/retrospectives
  without explicit endpoint calls.
- Auto-execution of experiments and auto-application of accepted ADRs.
- UI for any of the above; no frontend work was done.
- Provider-assisted improvement proposal generation.
- ContextPack wiring into ResearchScout / Architecture Review prompts.

## Boundary preserved

The release does not:

- modify code, open PRs, or invoke OpenHands;
- run real LLMs / network / GCP / MongoDB in tests;
- bypass the human-approval workflow for any state transition;
- introduce new coding runners, swarms, or autonomous self-modification;
- add SaaS / billing / multi-tenancy / marketing workflows.

## Commit / push status

Not committed and not pushed. Per the release runner instructions, the
summary is presented first for human review before any commit/push action.
