# ForgeLoop Studio — Future Vision

> **Nothing in this document is implemented.** The active build is ForgeLoop core (Releases 1–6, 32 tasks). This document exists for architectural awareness only. Do not implement any Studio module without explicit instruction.

---

## Overview

ForgeLoop Studio is a future AI-native product factory. ForgeLoop is its core engine. The full suite adds market discovery upstream (ProductScout), independent auditing downstream (AuditLens), and marketing/sales support (LaunchPilot).

---

## Flow Diagram

```
ProductScout
  → Product Brief / Requirements
  → ForgeLoop
       → Planning
       → Task / Subtask Decomposition
       → Coding Tool Runners
       → QA / STLC Pipeline
       → PR / Review Loop
       → Deployment / Maintenance
  → AuditLens
       → Independent Audit
       → Improvement Tickets
       → ForgeLoop
  → LaunchPilot
       → Website / Positioning / Outreach
       → Client Feedback / Custom Requirements
       → ForgeLoop
```

---

## Module Descriptions

**ProductScout** — market research and product discovery bot. Researches markets, competitors, pain points, target users, pricing signals, and product opportunities. Produces structured product briefs and requirements that enter ForgeLoop as tickets.

**ForgeLoop** — this repo. Human-supervised SDLC + STLC control plane. Converts requirements into architecture decisions, planning briefs, dev tasks, code (via tool runners), QA runs, PR/review loops, deployments, maintenance loops, and project memory. All transitions require human approval.

**AuditLens** — independent auditor. Audits implemented software for security, compliance, accessibility, UX, performance, test coverage, business logic gaps, and market-readiness. Generates improvement tickets that re-enter ForgeLoop. Can re-audit periodically as market expectations, dependencies, and security risks evolve.

**LaunchPilot** — marketing and sales support bot. Landing pages, product positioning, launch plans, outreach messages, demos, sales material, and client-specific requirement intake. Client feedback and custom requirements return to ForgeLoop as new tickets. Subsumes Release 7 (parked, not in active roadmap).

---

## Shared Data Model

These concepts are used across Studio modules. ForgeLoop owns and stores all of them.

| Concept | Owner | Description |
|---------|-------|-------------|
| `Project` | ForgeLoop | All work is project-scoped |
| `ProjectMemory` | ForgeLoop | Architecture decisions, standards, feedback, history |
| `Requirement` | ProductScout → ForgeLoop | Structured input from discovery |
| `Ticket` | ForgeLoop | Unit of work entering the engineering pipeline |
| `Task / Subtask` | ForgeLoop | Decomposed from approved tickets |
| `AgentRun` | ForgeLoop | One execution of an AI agent against a task |
| `Artifact` | ForgeLoop | Agent-generated output (brief, code diff, review notes, etc.) |
| `Evaluation` | ForgeLoop | Score and selection from multi-candidate agent runs |
| `Approval` | Human → ForgeLoop | Explicit human sign-off at gate transitions |
| `AuditEvent` | AuditLens → ForgeLoop | Finding from an independent audit pass |
| `ToolRun` | ForgeLoop | External coding-tool invocation record |
| `CostRecord` | ForgeLoop | Token usage and compute cost per agent run |

---

## Active Build Boundary

The current implementation is **ForgeLoop Releases 1–2**. Everything else in this document is future architecture only.
