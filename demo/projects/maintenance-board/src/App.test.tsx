import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import { workOrders } from './data/workOrders'

const TODAY = '2026-10-12'

const column = (name: RegExp) => screen.getByRole('region', { name })

describe('App', () => {
  it('shows every work order in the column of its status', () => {
    render(<App today={TODAY} />)
    expect(within(column(/^Open/)).getAllByRole('listitem')).toHaveLength(6)
    expect(within(column(/^In progress/)).getAllByRole('listitem')).toHaveLength(3)
    expect(within(column(/^Done/)).getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getAllByRole('listitem')).toHaveLength(workOrders.length)
  })

  it('searches titles, case-insensitively', async () => {
    render(<App today={TODAY} />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search work orders' }), 'FILTER')
    const titles = screen.getAllByRole('listitem').map((li) => within(li).getByText(/filter/i).textContent)
    expect(titles).toEqual(['Replace hydraulic filter', 'Replace compressor intake filter'])
  })

  it('says so when a column has no matches', async () => {
    render(<App today={TODAY} />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search work orders' }), 'weld tip')
    expect(within(column(/^Done/)).getByText('No work orders.')).toBeInTheDocument()
  })

  it('shows the machine, priority, due date and assignee on a card', () => {
    render(<App today={TODAY} />)
    const card = screen.getByText('Oil leak at main cylinder').closest('li')!
    expect(within(card).getByText('Press 2')).toBeInTheDocument()
    expect(within(card).getByText('High')).toBeInTheDocument()
    expect(within(card).getByText('Due tomorrow')).toBeInTheDocument()
    expect(within(card).getByText('Tom Becker')).toBeInTheDocument()
  })
})
