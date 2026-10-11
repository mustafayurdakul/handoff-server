import { useState } from 'react'
import { documents } from './data/documents'

export default function App() {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const visible = documents.filter((d) => d.title.toLowerCase().includes(q))

  return (
    <main>
      <h1>Documents</h1>
      <input
        type="search"
        aria-label="Search titles"
        placeholder="Search titles"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {visible.length === 0 ? (
        <p>No results.</p>
      ) : (
        <ul>
          {visible.map((d) => (
            <li key={d.id}>
              <strong>{d.title}</strong>
              <span>
                {d.author} · {d.createdAt}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
