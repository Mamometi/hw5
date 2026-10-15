# Campus Customs Operations Desk: dashboard

React 19 + Vite + TypeScript dashboard for the Campus Customs agent team. It uses React Compiler, Actions with `useOptimistic`, motion, and lucide-react. Design notes are in `../output/design.md`.

## Run

1. Start the backend from `../backend`:

   ```bash
   ../.venv/bin/uvicorn main:app --reload --port 8000
   ```

2. Start the dashboard from this folder:

   ```bash
   npm install
   npm run dev
   ```

3. Open http://localhost:5173.

The dashboard calls the FastAPI backend at `http://localhost:8000`. Set `VITE_API_URL` in `.env.local` to change it. The backend allows CORS from `http://localhost:5173`.

## Layout

- `src/api.ts`: API client, including the live run stream (`POST /api/tickets/{id}/run/stream`, Server-Sent Events over fetch)
- `src/hooks/useDesk.ts`: all desk state and actions (tickets, cash, approvals, live runs, toasts)
- `src/feed.ts`: turns audit events into the activity feed, agent states, hand-off edges and per-agent contributions
- `src/agents.tsx`: the agents' colors, emblems and roles
- `src/components/`: tickets, ticket detail, team graph, activity feed, contributions, cash panel, approvals, toasts
