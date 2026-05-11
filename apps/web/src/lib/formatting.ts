export function splitLines(value: string): string[] {
  return value
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
}
