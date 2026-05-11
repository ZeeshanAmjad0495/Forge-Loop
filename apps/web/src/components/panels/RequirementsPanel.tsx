import { useEffect, useState } from 'react'
import {
  createProjectRequirement,
  createProjectRequirementGeneration,
  listProjectRequirements,
} from '../../api'
import type { ProviderInfo, Requirement } from '../../types'
import { splitLines } from '../../lib/formatting'

export function RequirementsPanel({
  projectId,
  providers,
  selectedProvider,
  onProviderChange,
  onSelectRequirement,
  onAfterGenerate,
}: {
  projectId: string
  providers: ProviderInfo[]
  selectedProvider: string
  onProviderChange: (name: string) => void
  onSelectRequirement: (r: Requirement) => void
  onAfterGenerate: () => void
}) {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [reqLoadError, setReqLoadError] = useState('')

  const [reqTitle, setReqTitle] = useState('')
  const [reqProblem, setReqProblem] = useState('')
  const [reqGoal, setReqGoal] = useState('')
  const [reqUsers, setReqUsers] = useState('')
  const [reqFunc, setReqFunc] = useState('')
  const [reqNonFunc, setReqNonFunc] = useState('')
  const [reqAccept, setReqAccept] = useState('')
  const [reqConstraints, setReqConstraints] = useState('')
  const [reqNonGoals, setReqNonGoals] = useState('')
  const [reqAssumptions, setReqAssumptions] = useState('')
  const [reqCreating, setReqCreating] = useState(false)
  const [reqCreateError, setReqCreateError] = useState('')

  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genStatus, setGenStatus] = useState('')

  useEffect(() => {
    listProjectRequirements(projectId)
      .then(setRequirements)
      .catch(err => setReqLoadError((err as Error).message))
  }, [projectId])

  async function handleCreateRequirement(e: React.FormEvent) {
    e.preventDefault()
    setReqCreateError('')
    setReqCreating(true)
    try {
      const created = await createProjectRequirement(projectId, {
        title: reqTitle.trim(),
        problem_statement: reqProblem.trim(),
        business_goal: reqGoal.trim(),
        target_users: splitLines(reqUsers),
        functional_requirements: splitLines(reqFunc),
        non_functional_requirements: splitLines(reqNonFunc),
        acceptance_criteria: splitLines(reqAccept),
        constraints: splitLines(reqConstraints),
        non_goals: splitLines(reqNonGoals),
        assumptions: splitLines(reqAssumptions),
      })
      setRequirements(prev => [...prev, created])
      setReqTitle('')
      setReqProblem('')
      setReqGoal('')
      setReqUsers('')
      setReqFunc('')
      setReqNonFunc('')
      setReqAccept('')
      setReqConstraints('')
      setReqNonGoals('')
      setReqAssumptions('')
    } catch (err) {
      setReqCreateError((err as Error).message)
    } finally {
      setReqCreating(false)
    }
  }

  async function handleGenerateRequirements() {
    setGenBusy(true)
    setGenError('')
    setGenStatus('')
    try {
      const result = await createProjectRequirementGeneration(
        projectId,
        selectedProvider || undefined,
      )
      const refreshed = await listProjectRequirements(projectId)
      setRequirements(refreshed)
      setGenStatus(
        `Generated ${result.requirements.length} requirement(s) using ${result.agent_run.provider}.`,
      )
      onAfterGenerate()
    } catch (err) {
      setGenError((err as Error).message)
    } finally {
      setGenBusy(false)
    }
  }

  return (
    <section className="requirements-section">
      <h3>Requirements</h3>
      <p className="section-hint">
        Structured requirements capture richer intake (problem, goal, criteria, constraints).
      </p>
      {reqLoadError && <div className="error">{reqLoadError}</div>}
      {requirements.length > 0 && (
        <div className="ticket-list">
          {requirements.map(r => (
            <button
              key={r.id}
              className={`ticket-row ${r.status === 'analyzed' ? 'done' : ''}`}
              onClick={() => onSelectRequirement(r)}
            >
              <span className="ticket-row-title">{r.title}</span>
              <span className="ticket-row-status">{r.status}</span>
            </button>
          ))}
        </div>
      )}

      <div className="generate-requirements" style={{ margin: '12px 0' }}>
        <h4>Generate requirements from project details</h4>
        <p className="section-hint">
          The requirement generator uses the project's name, description, and context to draft requirements.
          Generated requirements are saved as drafts so you can review and edit them before analysis.
        </p>
        {providers.length > 0 && (
          <div className="provider-select">
            <label htmlFor="gen-provider">LLM provider</label>
            <select
              id="gen-provider"
              value={selectedProvider}
              onChange={e => onProviderChange(e.target.value)}
              disabled={genBusy}
            >
              {providers.map(p => (
                <option key={p.name} value={p.name} disabled={!p.configured}>
                  {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
                </option>
              ))}
            </select>
          </div>
        )}
        {genError && <div className="error">{genError}</div>}
        {genStatus && <div className="ctx-saved">{genStatus}</div>}
        <button type="button" onClick={handleGenerateRequirements} disabled={genBusy}>
          {genBusy ? 'Generating…' : 'Generate requirements'}
        </button>
      </div>

      <h4>New requirement</h4>
      <form onSubmit={handleCreateRequirement}>
        <label htmlFor="req-title">Title</label>
        <input
          id="req-title"
          value={reqTitle}
          onChange={e => setReqTitle(e.target.value)}
          placeholder="Short name for the requirement"
          required
          disabled={reqCreating}
        />
        <label htmlFor="req-problem">Problem statement</label>
        <textarea
          id="req-problem"
          value={reqProblem}
          onChange={e => setReqProblem(e.target.value)}
          placeholder="What problem are we solving?"
          disabled={reqCreating}
        />
        <label htmlFor="req-goal">Business goal</label>
        <textarea
          id="req-goal"
          value={reqGoal}
          onChange={e => setReqGoal(e.target.value)}
          placeholder="Why does this matter?"
          disabled={reqCreating}
        />
        {(
          [
            ['req-users', 'Target users (one per line)', reqUsers, setReqUsers],
            ['req-func', 'Functional requirements (one per line)', reqFunc, setReqFunc],
            ['req-nonfunc', 'Non-functional requirements (one per line)', reqNonFunc, setReqNonFunc],
            ['req-accept', 'Acceptance criteria (one per line)', reqAccept, setReqAccept],
            ['req-constraints', 'Constraints (one per line)', reqConstraints, setReqConstraints],
            ['req-nongoals', 'Non-goals (one per line)', reqNonGoals, setReqNonGoals],
            ['req-assumptions', 'Assumptions (one per line)', reqAssumptions, setReqAssumptions],
          ] as const
        ).map(([id, label, value, setter]) => (
          <div key={id}>
            <label htmlFor={id}>{label}</label>
            <textarea
              id={id}
              value={value}
              onChange={e => setter(e.target.value)}
              disabled={reqCreating}
            />
          </div>
        ))}
        {reqCreateError && <div className="error">{reqCreateError}</div>}
        <button type="submit" disabled={reqCreating}>
          {reqCreating ? 'Creating…' : 'Create requirement'}
        </button>
      </form>
    </section>
  )
}
