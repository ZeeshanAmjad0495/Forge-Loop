export interface Ticket {
  id: string
  title: string
  description: string
  status: 'created' | 'brief_generated'
  created_at: string
  updated_at: string
  project_id: string | null
}

export interface ProjectCreate {
  name: string
  description: string
  repo_url?: string | null
  tech_stack?: string[]
}

export interface Project {
  id: string
  name: string
  description: string
  repo_url: string | null
  tech_stack: string[]
  status: 'active'
  created_at: string
  updated_at: string
}

export interface ProjectContext {
  project_id: string
  architecture_notes: string
  coding_standards: string
  test_commands: string
  deployment_commands: string
  domain_rules: string
  safety_rules: string
  updated_at: string | null
}
