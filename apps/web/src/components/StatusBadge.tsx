import type {
  CheckRunConclusion,
  CheckRunStatus,
  ToolRunConclusion,
  ToolRunStatus,
} from '../types'
import { conclusionColor, toolRunConclusionColor } from '../lib/status'

export function StatusBadge({
  label,
  color,
}: {
  label: string
  color: string
}) {
  return (
    <span style={{
      fontSize: 11,
      padding: '1px 6px',
      borderRadius: 10,
      background: '#222',
      color,
      border: `1px solid ${color}`,
    }}>
      {label}
    </span>
  )
}

export function CheckBadge({
  conclusion,
  status,
}: {
  conclusion: CheckRunConclusion | null
  status: CheckRunStatus
}) {
  const label = conclusion ?? status
  return <StatusBadge label={label} color={conclusionColor(conclusion)} />
}

export function ToolRunBadge({
  conclusion,
  status,
}: {
  conclusion: ToolRunConclusion | null
  status: ToolRunStatus
}) {
  const label = conclusion ?? status
  return <StatusBadge label={label} color={toolRunConclusionColor(conclusion)} />
}
