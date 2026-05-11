import { useEffect, useState } from 'react'
import { getProjectContext, updateProjectContext } from '../../api'
import type { ProjectContext } from '../../types'

export function ProjectContextPanel({ projectId }: { projectId: string }) {
  const [ctx, setCtx] = useState<ProjectContext | null>(null)
  const [ctxSaving, setCtxSaving] = useState(false)
  const [ctxError, setCtxError] = useState('')
  const [ctxSaved, setCtxSaved] = useState(false)

  useEffect(() => {
    getProjectContext(projectId)
      .then(setCtx)
      .catch(err => setCtxError((err as Error).message))
  }, [projectId])

  function updateCtxField(field: keyof Omit<ProjectContext, 'project_id' | 'updated_at'>, value: string) {
    setCtx(prev =>
      prev
        ? { ...prev, [field]: value }
        : {
            project_id: projectId,
            architecture_notes: '',
            coding_standards: '',
            test_commands: '',
            deployment_commands: '',
            domain_rules: '',
            safety_rules: '',
            updated_at: null,
            [field]: value,
          },
    )
    setCtxSaved(false)
  }

  async function handleSaveContext(e: React.FormEvent) {
    e.preventDefault()
    if (!ctx) return
    setCtxSaving(true)
    setCtxError('')
    setCtxSaved(false)
    try {
      const saved = await updateProjectContext(projectId, {
        architecture_notes: ctx.architecture_notes,
        coding_standards: ctx.coding_standards,
        test_commands: ctx.test_commands,
        deployment_commands: ctx.deployment_commands,
        domain_rules: ctx.domain_rules,
        safety_rules: ctx.safety_rules,
      })
      setCtx(saved)
      setCtxSaved(true)
    } catch (err) {
      setCtxError((err as Error).message)
    } finally {
      setCtxSaving(false)
    }
  }

  return (
    <section className="context-section">
      <h3>Project context</h3>
      <p className="section-hint">
        This context is injected into planning prompts for every ticket in this project.
      </p>
      {ctxError && <div className="error">{ctxError}</div>}
      <form onSubmit={handleSaveContext}>
        {(
          [
            ['architecture_notes', 'Architecture notes'],
            ['coding_standards', 'Coding standards'],
            ['test_commands', 'Test commands'],
            ['deployment_commands', 'Deployment commands'],
            ['domain_rules', 'Domain rules'],
            ['safety_rules', 'Safety rules'],
          ] as const
        ).map(([field, label]) => (
          <div key={field}>
            <label htmlFor={`ctx-${field}`}>{label}</label>
            <textarea
              id={`ctx-${field}`}
              className="ctx-textarea"
              value={ctx?.[field] ?? ''}
              onChange={e => updateCtxField(field, e.target.value)}
              disabled={ctxSaving}
              placeholder="Leave blank if not applicable"
            />
          </div>
        ))}
        <div className="ctx-actions">
          <button type="submit" disabled={ctxSaving}>
            {ctxSaving ? 'Saving…' : 'Save context'}
          </button>
          {ctxSaved && <span className="ctx-saved">Saved</span>}
        </div>
      </form>
    </section>
  )
}
