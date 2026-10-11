import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'
import { documents } from './data/documents'

describe('App', () => {
  it('lists all documents', () => {
    render(<App />)
    expect(screen.getAllByRole('listitem')).toHaveLength(documents.length)
  })

  it('filters by title, case-insensitively', async () => {
    render(<App />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search titles' }), 'GUIDE')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('shows a message when nothing matches', async () => {
    render(<App />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search titles' }), 'no such document')
    expect(screen.getByText('No results.')).toBeInTheDocument()
  })
})
