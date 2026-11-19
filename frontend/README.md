# Frontend: review UI

Next.js (App Router), TypeScript, Tailwind and shadcn/ui. It talks to the FastAPI backend directly (`NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:8000`) and follows runs over server-sent events.

- `src/app/page.tsx`: case inbox. `src/app/cases/[caseId]/page.tsx`: case workspace.
- `src/components/workspace/`: documents with highlighted citations, findings, draft editor with versions and diff, run timeline.
- `src/hooks/use-run-stream.ts`: one stream for live runs, finished runs and paced replays.
- `src/lib/api-types.ts`: generated from the backend's OpenAPI schema (`npm run gen:api`). Don't edit by hand.
- `e2e/`: Playwright smoke test of the main flow (`npm run test:e2e`).

See the repo README for how to run it.
