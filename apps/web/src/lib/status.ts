import type {
  CheckRunConclusion,
  CIEventConclusion,
  IncidentSeverity,
  IncidentStatus,
  MemoryCandidateStatus,
  ToolRunConclusion,
} from '../types'

// Dark-pill text-color-only badges (CheckBadge / ToolRunBadge)

export function conclusionColor(c: CheckRunConclusion | null | undefined): string {
  if (c === 'success') return '#4caf50'
  if (c === 'failure') return '#f44336'
  if (c === 'neutral') return '#aaa'
  if (c === 'skipped') return '#888'
  if (c === 'cancelled') return '#ff9800'
  return '#666'
}

export function toolRunConclusionColor(c: ToolRunConclusion | null | undefined): string {
  if (c === 'success') return '#4caf50'
  if (c === 'failure') return '#f44336'
  if (c === 'neutral') return '#aaa'
  if (c === 'skipped') return '#888'
  if (c === 'requires_human_action') return '#ff9800'
  return '#666'
}

// Light-pill background+border badges (CI, Incident, Memory)

function lightPillStyle(palette: [string, string, string]): React.CSSProperties {
  const [color, background, border] = palette
  return {
    display: 'inline-block',
    padding: '1px 6px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    color,
    background,
    border: `1px solid ${border}`,
  }
}

export function ciConclusionStyle(c: CIEventConclusion | null | undefined): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    success:    ['#155724', '#d4edda', '#c3e6cb'],
    failure:    ['#721c24', '#f8d7da', '#f5c6cb'],
    timed_out:  ['#856404', '#fff3cd', '#ffeeba'],
    cancelled:  ['#383d41', '#e2e3e5', '#d6d8db'],
    skipped:    ['#383d41', '#e2e3e5', '#d6d8db'],
    neutral:    ['#383d41', '#e2e3e5', '#d6d8db'],
    unknown:    ['#856404', '#fff3cd', '#ffeeba'],
  }
  return lightPillStyle(map[c || 'unknown'] || map.unknown)
}

export function incidentSeverityStyle(s: IncidentSeverity | null | undefined): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    sev1:    ['#721c24', '#f8d7da', '#f5c6cb'],
    sev2:    ['#856404', '#fff3cd', '#ffeeba'],
    sev3:    ['#0c5460', '#d1ecf1', '#bee5eb'],
    sev4:    ['#383d41', '#e2e3e5', '#d6d8db'],
    unknown: ['#383d41', '#e2e3e5', '#d6d8db'],
  }
  return lightPillStyle(map[s || 'unknown'] || map.unknown)
}

export function incidentStatusStyle(s: IncidentStatus | null | undefined): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    reported:             ['#856404', '#fff3cd', '#ffeeba'],
    triaging:             ['#0c5460', '#d1ecf1', '#bee5eb'],
    remediation_planned:  ['#0c5460', '#d1ecf1', '#bee5eb'],
    remediation_approved: ['#155724', '#d4edda', '#c3e6cb'],
    resolved:             ['#155724', '#d4edda', '#c3e6cb'],
    closed:               ['#383d41', '#e2e3e5', '#d6d8db'],
    cancelled:            ['#383d41', '#e2e3e5', '#d6d8db'],
  }
  return lightPillStyle(map[s || 'reported'] || map.reported)
}

export function memoryCandidateStatusStyle(s: MemoryCandidateStatus): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    proposed:   ['#856404', '#fff3cd', '#ffeeba'],
    approved:   ['#155724', '#d4edda', '#c3e6cb'],
    rejected:   ['#721c24', '#f8d7da', '#f5c6cb'],
    superseded: ['#383d41', '#e2e3e5', '#d6d8db'],
  }
  return lightPillStyle(map[s] || map.proposed)
}
