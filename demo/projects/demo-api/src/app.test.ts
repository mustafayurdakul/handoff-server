import { describe, expect, it } from 'vitest'
import { buildApp } from './app.js'

describe('machines', () => {
  it('lists all machines', async () => {
    const res = await buildApp().inject({ method: 'GET', url: '/machines' })
    expect(res.statusCode).toBe(200)
    expect(res.json()).toHaveLength(3)
  })

  it('returns 404 for an unknown machine', async () => {
    const res = await buildApp().inject({ method: 'GET', url: '/machines/M-9' })
    expect(res.statusCode).toBe(404)
  })
})

describe('work orders', () => {
  it('filters by status', async () => {
    const res = await buildApp().inject({ method: 'GET', url: '/work-orders?status=open&limit=100' })
    expect(res.json().total).toBe(3)
  })

  it('creates a work order', async () => {
    const app = buildApp()
    const res = await app.inject({
      method: 'POST',
      url: '/work-orders',
      payload: { machineId: 'M-3', title: 'Replace nozzle', priority: 'medium' },
    })
    expect(res.statusCode).toBe(201)
    expect(res.json()).toMatchObject({ id: 6, status: 'open' })
  })

  it('rejects an unknown machine', async () => {
    const res = await buildApp().inject({
      method: 'POST',
      url: '/work-orders',
      payload: { machineId: 'M-9', title: 'x', priority: 'low' },
    })
    expect(res.statusCode).toBe(400)
  })

  it('updates the status', async () => {
    const res = await buildApp().inject({ method: 'PATCH', url: '/work-orders/1', payload: { status: 'done' } })
    expect(res.json().status).toBe('done')
  })
})
