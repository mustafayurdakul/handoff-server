import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { localDate } from './lib/due'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App today={localDate(new Date())} />
  </StrictMode>,
)
