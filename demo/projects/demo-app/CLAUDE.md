# demo-app

A small, searchable list of documents. React 19 + TypeScript + Vite.

## Structure

- `src/App.tsx`: the whole UI (search box and list).
- `src/data/documents.ts`: static document data and the `Doc` type. `createdAt` is a `YYYY-MM-DD` string.
- `src/index.css`: all styles. Do not add separate CSS files or CSS libraries.
- Tests live next to the source file: `src/X.test.tsx`.

## Conventions

- UI text is in English.
- Do not add dependencies: in the pipeline, setup runs before coding, so a package added later is never installed.
- `verbatimModuleSyntax` is on: type-only imports use `import type`.

## Tests

- Vitest + Testing Library. Vitest globals are off: import `describe`, `it` and `expect` from `vitest` in every test file.
- Find elements by role and accessible name, e.g. `getByRole('searchbox', { name: 'Search titles' })`. Do not use CSS classes or test ids.
- Use `@testing-library/user-event` for user interaction, not `fireEvent`.

## Commands

```sh
npm run lint
npm test
npm run build   # includes type checking with tsc -b
```
