import { describe, expect, it } from 'vitest'
import { daysUntil, dueBadge, localDate } from './due'

describe('daysUntil', () => {
  it('counts calendar days, across a month end', () => {
    expect(daysUntil('2026-11-02', '2026-10-30')).toBe(3)
    expect(daysUntil('2026-10-28', '2026-10-30')).toBe(-2)
  })
})

describe('dueBadge', () => {
  const today = '2026-10-12'

  it('shows past due dates as overdue', () => {
    expect(dueBadge('2026-10-09', today)).toEqual({ label: 'Overdue', tone: 'overdue' })
  })

  it('counts down the coming week', () => {
    expect(dueBadge('2026-10-13', today)).toEqual({ label: 'Due tomorrow', tone: 'soon' })
    expect(dueBadge('2026-10-17', today)).toEqual({ label: 'Due in 5 days', tone: 'soon' })
  })

  it('shows later due dates as a date', () => {
    expect(dueBadge('2026-10-30', today)).toEqual({ label: 'Due 2026-10-30', tone: 'later' })
  })
})

describe('localDate', () => {
  it('formats the local date with leading zeros', () => {
    expect(localDate(new Date(2026, 0, 5, 23, 30))).toBe('2026-01-05')
  })
})
