import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { clearToken, getToken, setToken } from './auth'
import { createPlanningRun, createTicket, listProviders, login } from './api'
import './App.css'
import type { ProviderInfo, Ticket } from './types'

type Phase =
  | { name: 'idle' }
  | { name: 'creating' }
  | { name: 'created'; ticket: Ticket }
  | { name: 'generating'; ticket: Ticket }
  | { name: 'done'; ticket: Ticket; brief: string }
  | { name: 'error'; message: string; ticket?: Ticket }

function TicketCard({ ticket }: { ticket: Ticket }) {
  const done = ticket.status === 'brief_generated'
  return (
    <div className="ticket-meta">
      <strong>{ticket.title}</strong>
      <p>{ticket.description}</p>
      <span className={`status ${done ? 'done' : ''}`}>
        {done ? 'Brief generated' : 'Created'}
      </span>
    </div>
  )
}

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email.trim(), password)
      setToken(res.access_token)
      onLogin()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>IncidentPilot</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="admin@example.com"
          required
          disabled={loading}
        />
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          disabled={loading}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => Boolean(getToken()))
  const [phase, setPhase] = useState<Phase>({ name: 'idle' })
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('')

  useEffect(() => {
    if (!authed) return
    listProviders()
      .then(res => {
        setProviders(res.providers)
        setSelectedProvider(res.default_provider)
      })
      .catch(err => {
        if ((err as Error).message.startsWith('401')) {
          setAuthed(false)
        }
        setProviders([])
        setSelectedProvider('')
      })
  }, [authed])

  function handleLogin() {
    setAuthed(true)
  }

  function handleLogout() {
    clearToken()
    setAuthed(false)
    setPhase({ name: 'idle' })
    setTitle('')
    setDescription('')
    setProviders([])
    setSelectedProvider('')
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setPhase({ name: 'creating' })
    try {
      const ticket = await createTicket(title.trim(), description.trim())
      setPhase({ name: 'created', ticket })
    } catch (err) {
      const msg = (err as Error).message
      if (msg.startsWith('401')) { setAuthed(false); return }
      setPhase({ name: 'error', message: msg })
    }
  }

  async function handleGenerateBrief(ticket: Ticket) {
    setPhase({ name: 'generating', ticket })
    try {
      const result = await createPlanningRun(ticket.id, selectedProvider || undefined)
      const updatedTicket = { ...ticket, status: 'brief_generated' as const }
      setPhase({ name: 'done', ticket: updatedTicket, brief: result.artifact.content })
    } catch (err) {
      const msg = (err as Error).message
      if (msg.startsWith('401')) { setAuthed(false); return }
      setPhase({ name: 'error', message: msg, ticket })
    }
  }

  function reset() {
    setTitle('')
    setDescription('')
    setPhase({ name: 'idle' })
  }

  function ProviderSelect({ disabled }: { disabled: boolean }) {
    if (providers.length === 0) return null
    return (
      <div className="provider-select">
        <label htmlFor="provider">LLM provider</label>
        <select
          id="provider"
          value={selectedProvider}
          onChange={e => setSelectedProvider(e.target.value)}
          disabled={disabled}
        >
          {providers.map(p => (
            <option key={p.name} value={p.name} disabled={!p.configured}>
              {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
            </option>
          ))}
        </select>
      </div>
    )
  }

  if (!authed) {
    return <LoginScreen onLogin={handleLogin} />
  }

  return (
    <>
      <div className="app-header">
        <h1>IncidentPilot</h1>
        <button className="logout" onClick={handleLogout}>Sign out</button>
      </div>

      {phase.name === 'idle' || phase.name === 'creating' ? (
        <form onSubmit={handleCreate}>
          <label htmlFor="title">Title</label>
          <input
            id="title"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Short description of the work"
            required
            disabled={phase.name === 'creating'}
          />

          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Provide enough context for the planning agent"
            required
            disabled={phase.name === 'creating'}
          />

          <button type="submit" disabled={phase.name === 'creating'}>
            {phase.name === 'creating' ? 'Creating…' : 'Create ticket'}
          </button>
        </form>
      ) : null}

      {phase.name === 'error' && (
        <>
          <div className="error">{phase.message}</div>
          {phase.ticket ? (
            <>
              <TicketCard ticket={phase.ticket} />
              <ProviderSelect disabled={false} />
              <button onClick={() => handleGenerateBrief(phase.ticket!)}>
                Retry generate brief
              </button>
            </>
          ) : null}
          <br />
          <button className="start-over" onClick={reset}>
            Start over
          </button>
        </>
      )}

      {(phase.name === 'created' || phase.name === 'generating') && (
        <>
          <TicketCard ticket={phase.ticket} />
          <ProviderSelect disabled={phase.name === 'generating'} />
          <button
            onClick={() => handleGenerateBrief(phase.ticket)}
            disabled={phase.name === 'generating'}
          >
            {phase.name === 'generating' ? 'Generating brief…' : 'Generate planning brief'}
          </button>
        </>
      )}

      {phase.name === 'done' && (
        <>
          <TicketCard ticket={phase.ticket} />
          <h2>Implementation Brief</h2>
          <div className="brief">
            <ReactMarkdown>{phase.brief}</ReactMarkdown>
          </div>
          <button className="start-over" onClick={reset}>
            Start over
          </button>
        </>
      )}
    </>
  )
}
