# ClipForge frontend

React + TypeScript + Vite + Tailwind UI for the ClipForge local clipping studio.

## Scripts

```bash
npm install
npm run dev      # http://127.0.0.1:5173 (proxies /api → backend :8000)
npm run build    # typecheck + production bundle
npm run lint     # oxlint
npm run preview  # serve dist/
```

## Pages

| Route        | Purpose                                      |
|--------------|----------------------------------------------|
| `/`          | Dashboard stats                              |
| `/library`   | Upload / list / delete videos                |
| `/editor`    | Timeline, detection, crop, render            |
| `/review`    | Approve / reject clips                       |
| `/schedule`  | Queue approved clips for YouTube Shorts      |
| `/settings`  | YouTube OAuth connect                        |

API client: `src/services/api.ts`. Shared types: `src/types/`. Job polling hook: `src/hooks/useJobPolling.ts`.
