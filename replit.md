# SYNC — RM Briefing Voice AI Co-Pilot

Before every client meeting, your RM knows everything. Not because they read a CRM — because SYNC called them 45 seconds ago.

## Run & Operate

- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- API server (Python): auto-started by the workflow using uvicorn at port 8080
- Dashboard (React): auto-started by the workflow at port 18929

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9 (frontend), Python 3.11 (backend)
- API: FastAPI + uvicorn
- CRM: in-memory mock (5 richly detailed Indian clients), HubSpot adapter, Salesforce adapter
- AI: OpenAI GPT-4o for briefing generation (template fallback when no key)
- Voice: Ringg AI for outbound calls (simulated when no key)
- Frontend: React + Vite + shadcn/ui + TanStack Query
- Real-time: WebSocket at `/ws/dashboard`
- API codegen: Orval (from OpenAPI spec at `lib/api-spec/openapi.yaml`)

## Where things live

- `lib/api-spec/openapi.yaml` — single source of truth for all API contracts
- `lib/api-client-react/src/generated/` — generated React hooks and Zod schemas (do not edit manually)
- `artifacts/sync-backend/` — Python FastAPI backend
  - `main.py` — FastAPI app entrypoint, CORS, router registration
  - `database.py` — 5 mock Indian clients + seeded briefing logs
  - `services/briefing_engine.py` — GPT-4o briefing generator + template fallback
  - `services/ringg_service.py` — Ringg AI API client (demo mode without key)
  - `adapters/mock_crm.py` — default in-memory CRM adapter
  - `adapters/hubspot.py` — HubSpot CRM adapter
  - `adapters/salesforce.py` — Salesforce CRM adapter
  - `routers/` — FastAPI routers (clients, briefings, calls, webhooks)
- `artifacts/sync-dashboard/src/` — React dashboard
  - `pages/Dashboard.tsx` — main dashboard page
  - `hooks/use-websocket.ts` — real-time WebSocket hook with auto-reconnect
  - `components/` — Header, MetricCards, SyncPanel, LiveFeed, Comparison, Footer
- `ringg/` — Ringg AI configuration
  - `agent-config.json` — agent setup config for Ringg dashboard
  - `system-prompt.md` — full system prompt for the SYNC voice agent
  - `setup-guide.md` — step-by-step Ringg setup instructions

## Architecture decisions

- **Python backend in api-server artifact slot** — FastAPI/uvicorn replaces Node/Express because Python is better for AI orchestration (OpenAI SDK, rapidfuzz, async httpx). The artifact.toml was updated to run uvicorn at port 8080.
- **Template briefing fallback** — briefing_engine generates a structured, narrated script without any API key so the demo works immediately.
- **Ringg demo mode** — ringg_service returns a `demo_call_xxxxx` call_id without a key, so the full flow can be tested end-to-end on the dashboard.
- **CRM adapter factory** — set `CRM_ADAPTER=hubspot` or `CRM_ADAPTER=salesforce` in env to switch away from mock without code changes.
- **WebSocket for live feed** — `/ws/dashboard` broadcasts every `sync_now` and Ringg webhook event so multiple dashboard tabs stay in sync.

## Product

SYNC gives bank/NBFC Relationship Managers a 45-second voice briefing before every client meeting. The RM either calls the SYNC number (inbound) or triggers a briefing from the dashboard (outbound). The voice AI delivers: client identity, portfolio snapshot, risk flags, relationship gap, open complaints, and a context-specific cross-sell play — narrated like a sharp colleague, not a CRM report.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Do not run `pnpm dev` at workspace root — use workflows.
- Python path for uvicorn is `/home/runner/workspace/artifacts/sync-backend` — set as PYTHONPATH in production.
- After editing `lib/api-spec/openapi.yaml`, always run codegen: `pnpm --filter @workspace/api-spec run codegen`.
- The `api-server` artifact now runs Python (not Node) — don't be confused by the Node build config remaining in artifact.toml.

## Pointers

- See `ringg/setup-guide.md` for full Ringg AI setup instructions
- See `pnpm-workspace` skill for workspace structure
