# ForgeLoop Tooling Strategy

## Core Principle

ForgeLoop is a **control plane**, not a coding agent. It does not reimplement tools that already exist. When code execution, testing, scanning, or review is needed, ForgeLoop invokes existing open-source tools, stores their output as artifacts, and enforces human approval before any result advances to the next stage.

---

## Delegation Model

```
ForgeLoop owns:
  project context, workflow state, task lifecycle,
  artifact store, approval gates, audit trail

ForgeLoop delegates to tools:
  code generation → OpenHands / Aider / Cline / OpenCode / Hermes Agent
  test execution  → TestZeus / Playwright Test Agents
  code review     → PR-Agent / Kodus/Kody
  security scan   → Semgrep / OSV-Scanner / Trivy
  accessibility   → axe-core
```

Integration pattern for each tool:
1. ForgeLoop invokes tool via API or CLI
2. Tool output is stored as a `ToolRun` artifact in ForgeLoop
3. Human reviews output (or ForgeLoop evaluates it automatically for low-risk stages)
4. Human approves or requests changes before the workflow advances

---

## Tool Catalogue

### Code Automation

| Tool | Role | Integration approach |
|------|------|---------------------|
| OpenHands | Autonomous coding agent | API invocation, returns diff/PR |
| Aider | AI pair programmer (CLI) | CLI invocation, captures output |
| Cline | VS Code AI coder | CLI or API |
| OpenCode | Terminal coding agent | CLI invocation |
| Hermes Agent | Lightweight agent framework | API invocation |

ForgeLoop does not prefer one over another. The project's repo safety profile and task type determine which tool is invoked. Multiple candidates may run in parallel (Release 5 multi-candidate pattern).

### QA / Test Execution

| Tool | Role |
|------|------|
| TestZeus | AI-driven test generation and execution |
| Playwright Test Agents | E2E browser test automation |

### Code Review

| Tool | Role |
|------|------|
| PR-Agent | Automated PR review, summary, suggestions |
| Kodus / Kody | AI code review platform |

### Security Scanning

| Tool | Role |
|------|------|
| Semgrep | Static analysis (SAST) |
| OSV-Scanner | Open source vulnerability scanning |
| Trivy | Container and dependency scanning |

### Accessibility

| Tool | Role |
|------|------|
| axe-core | Accessibility rule engine |

---

## What ForgeLoop Never Does

- Does not write production code directly without a tool runner
- Does not autonomously merge, deploy, or remediate without human approval
- Does not send proprietary or customer data to external tools unless explicitly approved
- Does not rebuild functionality that existing tools already provide well

---

## Current State

No tool runners are integrated yet. Tool runner abstraction is planned for Release 5.

See `docs/roadmap.md` for release schedule.
