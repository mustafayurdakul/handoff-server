export type Doc = {
  id: number
  title: string
  author: string
  createdAt: string // YYYY-MM-DD
  tags: string[]
}

export const documents: Doc[] = [
  { id: 1, title: 'Installation Guide', author: 'Alice Morgan', createdAt: '2026-03-12', tags: ['guide'] },
  { id: 2, title: 'API Reference', author: 'Ben Carter', createdAt: '2026-05-02', tags: ['api', 'reference'] },
  { id: 3, title: 'Release Notes 2.4', author: 'Chloe Evans', createdAt: '2026-08-20', tags: ['release'] },
  { id: 4, title: 'Security Policy', author: 'Daniel Hughes', createdAt: '2025-11-30', tags: ['security', 'policy'] },
  { id: 5, title: 'User Guide', author: 'Alice Morgan', createdAt: '2026-01-15', tags: ['guide'] },
  { id: 6, title: 'Architecture Overview', author: 'Emma Price', createdAt: '2026-06-08', tags: ['architecture'] },
]
