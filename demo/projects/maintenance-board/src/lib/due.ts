export type DueBadge = {
  label: string
  tone: 'overdue' | 'soon' | 'later'
}

const DAY = 24 * 60 * 60 * 1000

/** The local calendar date of `date` as YYYY-MM-DD. */
export function localDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Calendar days from `today` until `due`, both YYYY-MM-DD. Negative when the due date has passed. */
export function daysUntil(due: string, today: string): number {
  return Math.round((Date.parse(due) - Date.parse(today)) / DAY)
}

/** The badge an open or in-progress work order shows for its due date. */
export function dueBadge(due: string, today: string): DueBadge {
  const days = daysUntil(due, today)
  if (days <= 0) return { label: 'Overdue', tone: 'overdue' }
  if (days === 1) return { label: 'Due tomorrow', tone: 'soon' }
  if (days <= 7) return { label: `Due in ${days} days`, tone: 'soon' }
  return { label: `Due ${due}`, tone: 'later' }
}
