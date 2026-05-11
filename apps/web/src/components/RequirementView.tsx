import { useState } from 'react'
import {
  createRequirementAnalysisForRequirement,
  createTaskDecomposition,
  listProjectApprovals,
} from '../api'
import type {
  Approval,
  DevTask,
  Project,
  ProviderInfo,
  Requirement,
  Subtask,
} from '../types'
import { DevTaskCard } from './DevTaskCard'
import { RequirementAnalysisPanel, type AnalysisPhase } from './TicketView'

function RequirementBulletList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <>
      <strong>{label}</strong>
      <ul>
        {items.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </>
  )
}

type DecompPhase =
  | { name: 'idle' }
  | { name: 'decomposing' }
  | { name: 'done' }
  | { name: 'error'; message: string }

export function RequirementView({
  requirement: initialRequirement,
  project,
  onBack,
  providers,
  selectedProvider,
  onProviderChange,
}: {
  requirement: Requirement
  project: Project
  onBack: () => void
  providers: ProviderInfo[]
  selectedProvider: string
  onProviderChange: (name: string) => void
}) {
  const [requirement, setRequirement] = useState(initialRequirement)
  const [phase, setPhase] = useState<AnalysisPhase>({ name: 'idle' })
  const [decompPhase, setDecompPhase] = useState<DecompPhase>({ name: 'idle' })
  const [devTasks, setDevTasks] = useState<DevTask[]>([])
  const [subtasks, setSubtasks] = useState<Subtask[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const busy = phase.name === 'analyzing' || decompPhase.name === 'decomposing'

  async function loadApprovals() {
    try {
      const list = await listProjectApprovals(project.id)
      setApprovals(list)
    } catch {
      // non-critical
    }
  }

  async function handleAnalyze() {
    setPhase({ name: 'analyzing' })
    try {
      const result = await createRequirementAnalysisForRequirement(
        requirement.id,
        selectedProvider || undefined,
      )
      setRequirement(prev => ({ ...prev, status: 'analyzed' }))
      setPhase({ name: 'done', analysis: result.requirement_analysis })
    } catch (err) {
      setPhase({ name: 'error', message: (err as Error).message })
    }
  }

  async function handleDecompose() {
    setDecompPhase({ name: 'decomposing' })
    try {
      const result = await createTaskDecomposition(requirement.id, selectedProvider || undefined)
      setDevTasks(result.dev_tasks)
      setSubtasks(result.subtasks)
      setDecompPhase({ name: 'done' })
      await loadApprovals()
    } catch (err) {
      setDecompPhase({ name: 'error', message: (err as Error).message })
    }
  }

  function handleTaskUpdate(updated: DevTask) {
    setDevTasks(prev => prev.map(t => t.id === updated.id ? updated : t))
  }

  function handleSubtaskUpdate(updated: Subtask) {
    setSubtasks(prev => prev.map(s => s.id === updated.id ? updated : s))
  }

  return (
    <div>
      <button className="back-link" onClick={onBack}>← {project.name}</button>
      <h2>{requirement.title}</h2>
      <p>
        <span className={`status ${requirement.status === 'analyzed' ? 'done' : ''}`}>
          {requirement.status}
        </span>
      </p>

      {requirement.problem_statement && (
        <>
          <strong>Problem statement</strong>
          <p>{requirement.problem_statement}</p>
        </>
      )}
      {requirement.business_goal && (
        <>
          <strong>Business goal</strong>
          <p>{requirement.business_goal}</p>
        </>
      )}
      <RequirementBulletList label="Target users" items={requirement.target_users} />
      <RequirementBulletList label="Functional requirements" items={requirement.functional_requirements} />
      <RequirementBulletList label="Non-functional requirements" items={requirement.non_functional_requirements} />
      <RequirementBulletList label="Acceptance criteria" items={requirement.acceptance_criteria} />
      <RequirementBulletList label="Constraints" items={requirement.constraints} />
      <RequirementBulletList label="Non-goals" items={requirement.non_goals} />
      <RequirementBulletList label="Assumptions" items={requirement.assumptions} />

      {providers.length > 0 && (
        <div className="provider-select">
          <label htmlFor="req-provider">LLM provider</label>
          <select
            id="req-provider"
            value={selectedProvider}
            onChange={e => onProviderChange(e.target.value)}
            disabled={busy}
          >
            {providers.map(p => (
              <option key={p.name} value={p.name} disabled={!p.configured}>
                {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
              </option>
            ))}
          </select>
        </div>
      )}

      {phase.name === 'error' && <div className="error">{phase.message}</div>}
      {phase.name !== 'done' && (
        <button onClick={handleAnalyze} disabled={busy} style={{ marginRight: 8 }}>
          {phase.name === 'analyzing' ? 'Analyzing…' : 'Analyze requirement'}
        </button>
      )}
      {phase.name === 'done' && (
        <>
          <h3>Requirement Analysis</h3>
          <RequirementAnalysisPanel analysis={phase.analysis} />
        </>
      )}

      <hr style={{ margin: '18px 0', borderColor: '#333' }} />
      <h3>Dev Task Decomposition</h3>
      {decompPhase.name === 'error' && <div className="error">{decompPhase.message}</div>}
      {decompPhase.name !== 'done' && (
        <button onClick={handleDecompose} disabled={busy}>
          {decompPhase.name === 'decomposing' ? 'Decomposing…' : 'Decompose into dev tasks'}
        </button>
      )}
      {decompPhase.name === 'done' && (
        <>
          <p style={{ fontSize: 13, color: '#aaa' }}>
            {devTasks.length} task(s) generated
          </p>
          {devTasks.map(task => (
            <DevTaskCard
              key={task.id}
              task={task}
              allSubtasks={subtasks}
              taskApproval={approvals.find(a => a.target_type === 'dev_task' && a.target_id === task.id)}
              projectId={project.id}
              onTaskUpdate={handleTaskUpdate}
              onSubtaskUpdate={handleSubtaskUpdate}
              onApprovalChange={loadApprovals}
            />
          ))}
          <button onClick={handleDecompose} disabled={busy} style={{ marginTop: 8 }}>
            Re-run decomposition
          </button>
        </>
      )}
    </div>
  )
}
