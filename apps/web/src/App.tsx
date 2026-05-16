import { useEffect, useState } from 'react'
import { listProviders } from './api'
import { clearToken, getToken } from './auth'
import './App.css'
import type {
  Project,
  ProviderInfo,
  Requirement,
  Ticket,
} from './types'
import { LoginScreen } from './components/LoginScreen'
import { ProjectsView } from './components/ProjectsView'
import { ProjectView } from './components/ProjectView'
import { TicketView } from './components/TicketView'
import { RequirementView } from './components/RequirementView'
import { WorkflowStages } from './components/WorkflowStages'

type View =
  | { view: 'projects' }
  | { view: 'project'; project: Project }
  | { view: 'ticket'; project: Project; ticket: Ticket }
  | { view: 'requirement'; project: Project; requirement: Requirement }

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => Boolean(getToken()))
  const [currentView, setCurrentView] = useState<View>({ view: 'projects' })
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
        if ((err as Error).message.startsWith('401')) setAuthed(false)
        setProviders([])
        setSelectedProvider('')
      })
  }, [authed])

  function handleLogout() {
    clearToken()
    setAuthed(false)
    setCurrentView({ view: 'projects' })
    setProviders([])
    setSelectedProvider('')
  }

  if (!authed) {
    return <LoginScreen onLogin={() => setAuthed(true)} />
  }

  return (
    <>
      <div className="app-header">
        <h1>ForgeLoop</h1>
        <button className="logout" onClick={handleLogout}>Sign out</button>
      </div>

      <WorkflowStages />

      {currentView.view === 'projects' && (
        <ProjectsView
          onSelectProject={project => setCurrentView({ view: 'project', project })}
        />
      )}

      {currentView.view === 'project' && (
        <ProjectView
          project={currentView.project}
          onBack={() => setCurrentView({ view: 'projects' })}
          onSelectTicket={ticket =>
            setCurrentView({ view: 'ticket', project: currentView.project, ticket })
          }
          onSelectRequirement={requirement =>
            setCurrentView({ view: 'requirement', project: currentView.project, requirement })
          }
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}

      {currentView.view === 'ticket' && (
        <TicketView
          ticket={currentView.ticket}
          project={currentView.project}
          onBack={_updatedTicket =>
            setCurrentView({ view: 'project', project: currentView.project })
          }
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}

      {currentView.view === 'requirement' && (
        <RequirementView
          requirement={currentView.requirement}
          project={currentView.project}
          onBack={() => setCurrentView({ view: 'project', project: currentView.project })}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}
    </>
  )
}
