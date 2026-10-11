# maintenance-board

The maintenance board of Line 3: planners and technicians see the work orders of the line's machines in three
columns (Open, In progress, Done). React 19 + TypeScript + Vite. The data is static for now.

## Structure

- `src/App.tsx`: the board: search box, the three columns and the work order cards.
- `src/data/workOrders.ts`: the `Machine` and `WorkOrder` types and the data. Dates are `YYYY-MM-DD` strings.
- `src/lib/due.ts`: date logic: days until a due date and the due badge of a card.
- `src/index.css`: all styles. Do not add separate CSS files or CSS libraries.
- Tests live next to the source file: `src/X.test.ts(x)`.

## Conventions

- UI text is in English.
- `App` takes `today` (`YYYY-MM-DD`) as a prop; only `main.tsx` reads the clock. Code that needs the date gets it
  passed in, so tests can fix it.
- Do not add dependencies: in the pipeline, setup runs before coding, so a package added later is never installed.
- `verbatimModuleSyntax` is on: type-only imports use `import type`.

## Tests

- Vitest + Testing Library. Vitest globals are off: import `describe`, `it` and `expect` from `vitest` in every
  test file.
- Render with a fixed date: `render(<App today="2026-10-12" />)`.
- Find elements by role and accessible name, e.g. `getByRole('searchbox', { name: 'Search work orders' })`, and a
  column with `getByRole('region', { name: /^Open/ })`. Do not use CSS classes or test ids.
- Use `@testing-library/user-event` for user interaction, not `fireEvent`.
- Put pure logic in `src/lib/` and test it there directly.

## Commands

```sh
npm run lint
npm test
npm run build   # includes type checking with tsc -b
```
