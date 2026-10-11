export type Status = 'open' | 'in_progress' | 'done'
export type Priority = 'high' | 'medium' | 'low'

export type Machine = {
  id: string
  name: string
}

export type WorkOrder = {
  id: string
  title: string
  machineId: string
  status: Status
  priority: Priority
  due: string // YYYY-MM-DD
  assignee?: string
}

export const machines: Machine[] = [
  { id: 'P-01', name: 'Press 1' },
  { id: 'P-02', name: 'Press 2' },
  { id: 'C-01', name: 'Conveyor 1' },
  { id: 'R-04', name: 'Robot cell 4' },
  { id: 'W-02', name: 'Welding station 2' },
  { id: 'K-01', name: 'Compressor 1' },
]

export const workOrders: WorkOrder[] = [
  { id: 'WO-1001', title: 'Replace hydraulic filter', machineId: 'P-01', status: 'open', priority: 'medium', due: '2026-10-16', assignee: 'Ana Silva' },
  { id: 'WO-1002', title: 'Inspect conveyor belt tension', machineId: 'C-01', status: 'open', priority: 'low', due: '2026-10-23' },
  { id: 'WO-1003', title: 'Oil leak at main cylinder', machineId: 'P-02', status: 'open', priority: 'high', due: '2026-10-13', assignee: 'Tom Becker' },
  { id: 'WO-1004', title: 'Calibrate torque sensor', machineId: 'R-04', status: 'open', priority: 'medium', due: '2026-10-14' },
  { id: 'WO-1005', title: 'Weld tip worn, replace', machineId: 'W-02', status: 'open', priority: 'high', due: '2026-10-10', assignee: 'Lena Wolf' },
  { id: 'WO-1006', title: 'Check air dryer drain', machineId: 'K-01', status: 'open', priority: 'low', due: '2026-10-30' },
  { id: 'WO-1007', title: 'Belt wear on return roller', machineId: 'C-01', status: 'in_progress', priority: 'medium', due: '2026-10-12', assignee: 'Ana Silva' },
  { id: 'WO-1008', title: 'Gripper loses vacuum', machineId: 'R-04', status: 'in_progress', priority: 'high', due: '2026-10-11', assignee: 'Tom Becker' },
  { id: 'WO-1009', title: 'Safety light curtain test', machineId: 'P-01', status: 'in_progress', priority: 'low', due: '2026-10-20', assignee: 'Lena Wolf' },
  { id: 'WO-1010', title: 'Replace compressor intake filter', machineId: 'K-01', status: 'done', priority: 'medium', due: '2026-10-08', assignee: 'Ana Silva' },
  { id: 'WO-1011', title: 'Tighten press frame bolts', machineId: 'P-02', status: 'done', priority: 'low', due: '2026-10-07', assignee: 'Tom Becker' },
  { id: 'WO-1012', title: 'Clean welding fume extractor', machineId: 'W-02', status: 'done', priority: 'medium', due: '2026-10-09', assignee: 'Lena Wolf' },
]
