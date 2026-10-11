import Fastify from 'fastify'
import { machines, seedWorkOrders, type Priority, type Status, type WorkOrder } from './data.js'

const STATUSES: Status[] = ['open', 'in_progress', 'done']
const PRIORITIES: Priority[] = ['low', 'medium', 'high']

/** Builds the API with its own in-memory copy of the data. */
export function buildApp() {
  const app = Fastify()
  const workOrders: WorkOrder[] = seedWorkOrders.map((w) => ({ ...w }))

  app.get('/machines', async () => machines)

  app.get<{ Params: { id: string } }>('/machines/:id', async (req, reply) => {
    const machine = machines.find((m) => m.id === req.params.id)
    return machine ?? reply.code(404).send({ error: 'Machine not found' })
  })

  app.get<{ Querystring: { status?: Status; page?: number; limit?: number } }>(
    '/work-orders',
    {
      schema: {
        querystring: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: STATUSES },
            page: { type: 'integer', minimum: 1, default: 1 },
            limit: { type: 'integer', minimum: 1, maximum: 100, default: 20 },
          },
        },
      },
    },
    async (req) => {
      const { status, page = 1, limit = 20 } = req.query
      const matching = workOrders.filter((w) => !status || w.status === status)
      const start = page * limit
      return { items: matching.slice(start, start + limit), page, limit, total: matching.length }
    },
  )

  app.post<{ Body: { machineId: string; title: string; priority: Priority } }>(
    '/work-orders',
    {
      schema: {
        body: {
          type: 'object',
          required: ['machineId', 'title', 'priority'],
          additionalProperties: false,
          properties: {
            machineId: { type: 'string' },
            title: { type: 'string', minLength: 1 },
            priority: { type: 'string', enum: PRIORITIES },
          },
        },
      },
    },
    async (req, reply) => {
      if (!machines.some((m) => m.id === req.body.machineId)) {
        return reply.code(400).send({ error: 'Unknown machine' })
      }
      const order: WorkOrder = {
        id: Math.max(0, ...workOrders.map((w) => w.id)) + 1,
        ...req.body,
        status: 'open',
        createdAt: new Date().toISOString().slice(0, 10),
      }
      workOrders.push(order)
      return reply.code(201).send(order)
    },
  )

  app.patch<{ Params: { id: string }; Body: { status: Status } }>(
    '/work-orders/:id',
    {
      schema: {
        body: {
          type: 'object',
          required: ['status'],
          additionalProperties: false,
          properties: { status: { type: 'string', enum: STATUSES } },
        },
      },
    },
    async (req, reply) => {
      const order = workOrders.find((w) => w.id === Number(req.params.id))
      if (!order) return reply.code(404).send({ error: 'Work order not found' })
      order.status = req.body.status
      return order
    },
  )

  return app
}
