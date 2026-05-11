import { useEffect, useState } from 'react'
import { createProject, listProjects } from '../api'
import type { Project } from '../types'

export function ProjectsView({
  onSelectProject,
}: {
  onSelectProject: (project: Project) => void
}) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loadError, setLoadError] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [techStack, setTechStack] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(err => setLoadError((err as Error).message))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const stack = techStack
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
      const project = await createProject({
        name: name.trim(),
        description: description.trim(),
        repo_url: repoUrl.trim() || null,
        tech_stack: stack,
      })
      setProjects(prev => [...prev, project])
      setName('')
      setDescription('')
      setRepoUrl('')
      setTechStack('')
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <h2>Projects</h2>
      {loadError && <div className="error">{loadError}</div>}

      {projects.length > 0 && (
        <div className="project-list">
          {projects.map(p => (
            <button
              key={p.id}
              className="project-card"
              onClick={() => onSelectProject(p)}
            >
              <strong>{p.name}</strong>
              <p>{p.description}</p>
              {p.tech_stack.length > 0 && (
                <div className="tech-stack">
                  {p.tech_stack.map(t => (
                    <span key={t} className="tech-badge">{t}</span>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      <h3>New project</h3>
      <form onSubmit={handleCreate}>
        <label htmlFor="proj-name">Name</label>
        <input
          id="proj-name"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. ForgeLoop API"
          required
          disabled={creating}
        />
        <label htmlFor="proj-desc">Description</label>
        <textarea
          id="proj-desc"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="What does this project do?"
          required
          disabled={creating}
        />
        <label htmlFor="proj-repo">Repo URL (optional)</label>
        <input
          id="proj-repo"
          value={repoUrl}
          onChange={e => setRepoUrl(e.target.value)}
          placeholder="https://github.com/org/repo"
          disabled={creating}
        />
        <label htmlFor="proj-stack">Tech stack (comma-separated, optional)</label>
        <input
          id="proj-stack"
          value={techStack}
          onChange={e => setTechStack(e.target.value)}
          placeholder="python, react, postgresql"
          disabled={creating}
        />
        {createError && <div className="error">{createError}</div>}
        <button type="submit" disabled={creating}>
          {creating ? 'Creating…' : 'Create project'}
        </button>
      </form>
    </div>
  )
}
