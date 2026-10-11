import { buildApp } from './app.js'

const port = Number(process.env.PORT ?? 3000)
await buildApp().listen({ port, host: '127.0.0.1' })
console.log(`demo-api listening on http://127.0.0.1:${port}`)
