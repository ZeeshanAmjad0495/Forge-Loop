// Task 84: lightweight, static dashboard clarity. Presentational only —
// no data fetching, no new deps. Shows the canonical ForgeLoop pipeline
// and the cost/approval/routing warnings a supervisor should watch for.

const STAGES = [
  'Project',
  'Requirement / Ticket',
  'Plan',
  'DevTasks',
  'Runner / PR',
  'Review',
  'CI / Incident',
  'Memory',
]

const WARNINGS: { label: string; hint: string }[] = [
  { label: 'Kimi blocked / approval required', hint: 'expensive provider gated by the budget guard' },
  { label: 'Expensive provider usage', hint: 'a non-default (Kimi) provider was selected' },
  { label: 'Runner approval required', hint: 'OpenHands / broad change needs human approval' },
  { label: 'Context reduction recommended', hint: 'ContextPack exceeded its token budget' },
]

export function WorkflowStages() {
  return (
    <div className="workflow-stages">
      <ol className="workflow-stages__steps">
        {STAGES.map((s, i) => (
          <li key={s}>
            <span className="workflow-stages__num">{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      <details className="workflow-stages__legend">
        <summary>Cost / approval / routing warnings to watch</summary>
        <ul>
          {WARNINGS.map(w => (
            <li key={w.label}>
              <strong>{w.label}</strong> — {w.hint}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
