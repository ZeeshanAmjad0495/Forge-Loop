import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { createPlanningRun, createTicket } from './api'
import './App.css'
import type { Ticket } from './types'

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

export default function App() {
  const [phase, setPhase] = useState<Phase>({ name: 'idle' })
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setPhase({ name: 'creating' })
    try {
      const ticket = await createTicket(title.trim(), description.trim())
      setPhase({ name: 'created', ticket })
    } catch (err) {
      setPhase({ name: 'error', message: (err as Error).message })
    }
  }

  async function handleGenerateBrief(ticket: Ticket) {
    setPhase({ name: 'generating', ticket })
    try {
      const result = await createPlanningRun(ticket.id)
      const updatedTicket = { ...ticket, status: 'brief_generated' as const }
      setPhase({ name: 'done', ticket: updatedTicket, brief: result.artifact.content })
    } catch (err) {
      setPhase({ name: 'error', message: (err as Error).message, ticket })
    }
  }

  function reset() {
    setTitle('')
    setDescription('')
    setPhase({ name: 'idle' })
  }

  return (
    <>
      <h1>IncidentPilot</h1>

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
