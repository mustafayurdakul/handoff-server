export type Machine = {
  id: string
  name: string
  line: string
}

export type Status = 'open' | 'in_progress' | 'done'
export type Priority = 'low' | 'medium' | 'high'

export type WorkOrder = {
  id: number
  machineId: string
  title: string
  priority: Priority
  status: Status
  createdAt: string // YYYY-MM-DD
}

export const machines: Machine[] = [
  { id: 'M-1', name: 'Press 1', line: 'Line A' },
  { id: 'M-2', name: 'Lathe 2', line: 'Line A' },
  { id: 'M-3', name: 'Welding robot 3', line: 'Line B' },
]

/** Starting data. The app copies it, so tests always start from the same state. */
export const seedWorkOrders: WorkOrder[] = [
  { id: 1, machineId: 'M-1', title: 'Replace hydraulic seal', priority: 'high', status: 'open', createdAt: '2026-09-01' },
  { id: 2, machineId: 'M-2', title: 'Calibrate spindle', priority: 'medium', status: 'in_progress', createdAt: '2026-09-03' },
  { id: 3, machineId: 'M-3', title: 'Check welding tip wear', priority: 'low', status: 'open', createdAt: '2026-09-04' },
  { id: 4, machineId: 'M-1', title: 'Inspect safety light curtain', priority: 'high', status: 'done', createdAt: '2026-09-07' },
  { id: 5, machineId: 'M-2', title: 'Clean coolant filter', priority: 'low', status: 'open', createdAt: '2026-09-10' },
]
