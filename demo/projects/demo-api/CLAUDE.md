# demo-api

A small REST API for machine maintenance work orders. Node 22+, TypeScript, Fastify. Data lives in memory.

## Structure

- `src/data.ts`: types (`Machine`, `WorkOrder`, `Status`, `Priority`) and the seed data.
- `src/app.ts`: `buildApp()` creates the Fastify app with all routes. Each call gets its own copy of the data.
- `src/server.ts`: starts the server (`npm start` after `npm run build`).
- Tests live next to the source file: `src/X.test.ts`.

## Conventions

- Validate input with Fastify JSON schemas on the route, not by hand.
- Errors are JSON: `{ "error": "<message>" }` with a fitting status code (400, 404).
- List endpoints return `{ items, page, limit, total }`. `page` starts at 1.
- Do not add dependencies: in the pipeline, setup runs before coding, so a package added later is never installed.
- ESM with `verbatimModuleSyntax`: import local files with the `.js` extension, and type-only imports use `import type`.

## Tests

- Vitest. Import `describe`, `it` and `expect` from `vitest`.
- Test routes with `buildApp().inject(...)`; never start a real server in tests.
- Commands: `npm run lint`, `npm test`, `npm run build`.
