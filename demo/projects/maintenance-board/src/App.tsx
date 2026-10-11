import { useState } from 'react'
import { machines, workOrders, type Priority, type Status, type WorkOrder } from './data/workOrders'
import { dueBadge } from './lib/due'

const COLUMNS: { status: Status; title: string }[] = [
  { status: 'open', title: 'Open' },
  { status: 'in_progress', title: 'In progress' },
  { status: 'done', title: 'Done' },
]

const PRIORITY: Record<Priority, string> = { high: 'High', medium: 'Medium', low: 'Low' }

/** `today` is a YYYY-MM-DD date. It is a prop so that tests can fix it. */
export default function App({ today }: { today: string }) {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const visible = workOrders.filter((w) => w.title.toLowerCase().includes(q))

  return (
    <main>
      <header>
        <h1>Maintenance board</h1>
        <p>Line 3 · {today}</p>
      </header>
      <input
        type="search"
        aria-label="Search work orders"
        placeholder="Search work orders"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="board">
        {COLUMNS.map((column) => {
          const items = visible.filter((w) => w.status === column.status)
          return (
            <section key={column.status} aria-labelledby={`column-${column.status}`}>
              <h2 id={`column-${column.status}`}>
                {column.title} <span className="count">{items.length}</span>
              </h2>
              {items.length === 0 ? (
                <p className="empty">No work orders.</p>
              ) : (
                <ul>
                  {items.map((w) => (
                    <Card key={w.id} workOrder={w} today={today} />
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </div>
    </main>
  )
}

function Card({ workOrder: w, today }: { workOrder: WorkOrder; today: string }) {
  const machine = machines.find((m) => m.id === w.machineId)
  const due = w.status === 'done' ? null : dueBadge(w.due, today)
  return (
    <li className="card">
      <div className="card-row">
        <span className="id">{w.id}</span>
        <span className={`priority ${w.priority}`}>{PRIORITY[w.priority]}</span>
      </div>
      <strong>{w.title}</strong>
      <span className="machine">{machine?.name ?? w.machineId}</span>
      <div className="card-row">
        {due ? <span className={`due ${due.tone}`}>{due.label}</span> : <span className="due">Done</span>}
        <span className="assignee">{w.assignee ?? 'Unassigned'}</span>
      </div>
    </li>
  )
}
