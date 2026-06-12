# SYNC — Voice AI Layer for Your CRM

> "Before every client meeting, your RM knows everything. Not because they read a CRM — because they made a 30-second phone call to SYNC."

SYNC is the **voice-AI integration layer** that plugs into the CRM your business already runs (HubSpot, Salesforce, Zoho, Microsoft Dynamics 365, Freshworks, or LeadSquared). Relationship Managers and Advisors — across financial services, real estate, wealth management, B2B sales, any business with a real customer book — call a Ringg AI phone number or click "Sync Now" on the dashboard and receive a crisp 45-second briefing: portfolio health, risk flags, open complaints, and a context-aware cross-sell pitch — narrated like a sharp colleague, not a CRM report.

**GrowthX Voice AI Buildathon — powered by Ringg AI.**

---

## What's new in v2 (the revamp)

| Before | After |
|--------|-------|
| 5 mock clients in memory | Real CRM connections via OAuth 2.0 (HubSpot, Salesforce, Zoho, Dynamics) |
| Mock CRM only | 7 CRM adapters: HubSpot, Salesforce, Zoho, Dynamics, Freshworks, LeadSquared, FakeLeadSquared (sandbox) |
| Env-var tokens | In-browser OAuth flow → encrypted token storage via Fernet |
| Manual field setup | Auto-provisioning: one-click creates missing custom fields in HubSpot; package.xml for Salesforce |
| No integration UI | Integrations page with provider grid, provisioning diff, field-mapping editor |
| Dashboard shows mock badge | ConnectionSwitcher: flip live between connected CRMs; Sandbox/Live banner |
| No CRM-native view | CRM Embed Panel: native contact view in a sandboxed iframe, side-by-side with SYNC |
| No post-meeting workflow | Voice command bar: say "log a note", "create a follow-up task" → executed in CRM via GPT-4o function calling |
| No PII protection | PII Scrub toggle: names and phones masked on screen for projector demos |
| No webhook visibility | Webhook Activity Panel: live received → processed animation |
| No call transcript | Briefing Transcript Drawer: ASR text + audio playback |

---

## What's new in v3 — The Live Co-Pilot (Ringg AI end-to-end)

| Capability | How it works |
|---|---|
| **🎧 Live whisper coaching** | Ringg transcribes the call in real time (in-call STT); SYNC reads the stream and murmurs one-line tactical nudges into the RM's earbud — hesitation, competitor mentions, buying signals |
| **✍️ Commitment → CRM, one tap** | SYNC hears *"Okay, Thursday at four works"* → proposes the action → RM approves → a real **timed calendar meeting** lands in Pipedrive (timezone-correct) |
| **📞 Coached Calls** | Twilio click-to-call bridge: both legs' audio forked → Ringg Parrot STT → coaching engine. Backup: Ringg's agent dials the client, warm-transfers the RM in, stays on as a silent transcriber |
| **▶ Live Simulations** | Three one-click in-app scenarios with natural voices: Coached Call, Morning Standup (SYNC answers from **live Pipedrive data**), Save Call with warm transfer. Nudges & actions are computed live by the real engine — never scripted |
| **🗣️ Ringg Parrot STT** | Dashboard-mic transcription runs Ringg-first (Whisper only as fallback) |
| **💰 ROI Ledger** | Hours saved, ₹ opportunity surfaced, complaints caught — counts up live on the dashboard |

**The Ringg stack inside SYNC:** outbound + inbound agents, in-call STT, mid-call function tools (`ask_crm` / `log_action`), warm transfer, knowledge bases, and Parrot STT for the dashboard mic. Voice is Ringg end-to-end — OpenAI only does text intelligence (briefing copy, post-call analysis, coaching language).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SYNC v2                                   │
├──────────────────┬──────────────────────┬───────────────────────────┤
│  Ringg AI        │  FastAPI Backend      │  React Dashboard          │
│  Voice Agent     │  (Python 3.11)        │  (Vite + shadcn/ui)       │
│  Inbound +       │                       │                           │
│  Outbound calls  │  CRM Adapters:        │  • ConnectionSwitcher     │
│                  │  • HubSpot (OAuth)    │  • IntegrationsIndex      │
│  13 custom       │  • Salesforce (OAuth) │  • CRM Embed Panel        │
│  variables →     │  • Zoho (OAuth)       │  • Voice Command Bar      │
│  briefing script │  • Dynamics (OAuth)   │  • WebhookActivityPanel   │
│                  │  • Freshworks (API)   │  • BriefingTranscript     │
│                  │  • LeadSquared (API)  │  • PII Scrub Toggle       │
│                  │  • FakeLSQ (sandbox)  │                           │
│                  │                       │  Real-time via WS         │
│                  │  • OAuth router       │  /ws/dashboard            │
│                  │  • Provisioning svc   │                           │
│                  │  • Voice cmd engine   │                           │
│                  │  • Embed resolver     │                           │
│                  │  • SQLite (sync.db)   │                           │
└──────────────────┴──────────────────────┴───────────────────────────┘
```

---

## Quick start

```bash
git clone <repo>
cp .env.example .env

# Backend
cd artifacts/sync-backend
python -m venv ../../.venv && source ../../.venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal:
```bash
pnpm install
VITE_API_URL=http://localhost:8000 VITE_WS_URL=ws://localhost:8000 \
  pnpm --filter @workspace/sync-dashboard dev
```

Open `http://localhost:3000`.

**No API keys required for the demo.** The LeadSquared Sandbox connection
(FakeLeadSquared + MockTransport) starts automatically and exercises the full
real adapter code path with the 5 sample clients.

---

## Ringg AI setup

```bash
# 1. Set RINGG_API_KEY in .env
# 2. Create the SYNC agent
python scripts/setup_ringg_agent.py

# 3. Upload the inbound knowledge base
python scripts/upload_knowledge_base.py

# 4. Test an outbound briefing call
python scripts/test_call.py --client "Rahul Mehta" --phone "+919876543210"
```

---

## Connecting a real CRM

### HubSpot (OAuth 2.0)

1. Create a HubSpot developer app at `developers.hubspot.com`
2. Set redirect URI to `{BACKEND_URL}/api/v1/oauth/callback/hubspot`
3. Set scopes: `crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.tickets.read crm.schemas.contacts.write`
4. Add to `.env`:
   ```
   HUBSPOT_CLIENT_ID=...
   HUBSPOT_CLIENT_SECRET=...
   ```
5. Open dashboard → Settings → Integrations → Connect HubSpot
6. One-click provision the 9 custom properties (risk score, EMI amounts, cross-sell, etc.)

### Salesforce

1. Create a Connected App in Salesforce Setup
2. Set callback URL to `{BACKEND_URL}/api/v1/oauth/callback/salesforce`
3. Add to `.env`: `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`
4. Connect via dashboard → download `sync-sf-package.zip` → import via Salesforce Setup

### Zoho CRM

1. Create a Zoho OAuth app at `api-console.zoho.in`
2. Add to `.env`: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_ACCOUNTS_BASE=https://accounts.zoho.in`
3. Connect via dashboard

### Microsoft Dynamics 365

1. Register an app in Azure AD → grant Dynamics CRM User Impersonation
2. Add to `.env`: `DYNAMICS_CLIENT_ID`, `DYNAMICS_CLIENT_SECRET`, `DYNAMICS_TENANT_ID`, `DYNAMICS_INSTANCE_URL`
3. Connect via dashboard

### Freshworks CRM

1. API Settings → Personal Settings → API Key
2. Add to `.env`: `FRESHWORKS_SUBDOMAIN`, `FRESHWORKS_API_KEY`
3. Connect via dashboard → Freshworks → Connect with API Key

### LeadSquared

1. My Profile → API & Webhooks → Access Key + Secret Key
2. Add to `.env`: `LEADSQUARED_ACCESS_KEY`, `LEADSQUARED_SECRET_KEY`
3. Connect via dashboard

---

## Voice commands (new in v2)

Hold the mic button in the header while viewing a client and say:

- *"Add a note that he's interested in the SIP pitch"*
- *"Create a follow-up task for next Tuesday at 10 AM"*
- *"Mark the complaint as resolved"*
- *"Schedule a branch visit next week"*
- *"Log the meeting outcome — client agreed to discuss the top-up loan"*
- *"Flag this account for manager review — revenue dip is worsening"*

SYNC parses your intent via GPT-4o function calling, shows you a preview
(**"Create task 'Follow-up call' for Rahul Mehta on Tue Jun 17 in HubSpot"**),
waits for your click to execute, then writes the action back to the CRM.

---

## API reference

| Endpoint | Description |
|----------|-------------|
| `GET /api/healthz` | Health check |
| `GET /api/v1/clients` | List all clients |
| `GET /api/v1/clients/search?name=` | Fuzzy name search |
| `GET /api/v1/clients/{id}` | Full client profile |
| `POST /api/v1/calls/sync-now` | Trigger Ringg outbound briefing call |
| `GET /api/v1/calls/sync-now/{call_id}` | Call detail + transcript |
| `GET /api/v1/integrations` | List CRM connections |
| `GET /api/v1/integrations/{id}` | Connection detail + provisioning status |
| `POST /api/v1/integrations/{id}/sync-now` | Warm connection cache |
| `POST /api/v1/integrations/{id}/provision` | Auto-create custom fields |
| `GET /api/v1/integrations/{id}/field-mappings` | View field overrides |
| `PUT /api/v1/integrations/{id}/field-mappings` | Update field overrides |
| `GET /api/v1/oauth/providers` | List providers + configured status |
| `GET /api/v1/oauth/{provider}/authorize` | Start OAuth dance |
| `GET /api/v1/oauth/callback/{provider}` | OAuth callback (set as redirect URI) |
| `POST /api/v1/oauth/{provider}/connect` | Connect API-key CRM |
| `GET /api/v1/embeds/{conn_id}/contact/{client_id}` | Embed spec for iframe |
| `GET /api/v1/embeds/sandbox/contact/{client_id}` | Sandbox contact HTML view |
| `POST /api/v1/voice/commands/parse` | Parse voice transcript → CRM action |
| `POST /api/v1/voice/commands/execute` | Execute confirmed CRM action |
| `GET /api/v1/voice/commands/history` | Voice command log |
| `POST /api/v1/webhooks/ringg` | Ringg webhook receiver |
| `WS /ws/dashboard` | Real-time event stream |

---

## Running tests

```bash
cd artifacts/sync-backend
pytest tests/ -v --asyncio-mode=auto
```

Test coverage includes:
- Adapter contract (mock + FakeLeadSquared, parametrized)
- SOQL injection safety (11 malicious inputs rejected)
- Provisioning service (FieldSpec structure + SF package zip)
- Voice command engine (parse + execute + error handling)
- End-to-end integration (13 API calls)

---

## Deploy

### Railway / Render (backend)

```bash
# Render: use render.yaml at repo root
render blueprint apply
```

### Vercel (dashboard)

```bash
cd artifacts/sync-dashboard
vercel --prod
# Set VITE_API_URL=https://sync-backend.onrender.com
# Set VITE_WS_URL=wss://sync-backend.onrender.com
```

### ngrok for OAuth callbacks in dev

```bash
ngrok http 8000
# Copy the HTTPS URL (e.g. https://abc123.ngrok.app)
# Set OAUTH_REDIRECT_BASE=https://abc123.ngrok.app in .env
# Register https://abc123.ngrok.app/api/v1/oauth/callback/hubspot
# as the OAuth redirect URI in your HubSpot developer app
```

---

## Tech stack

| Layer | Stack |
|-------|-------|
| Voice platform | Ringg AI (outbound + inbound, 13 custom variables) |
| Backend | Python 3.11, FastAPI, SQLModel, aiosqlite, Authlib, httpx, tenacity |
| AI | OpenAI GPT-4o (briefing generation + voice command parsing), Whisper (STT) |
| CRM SDKs | hubspot-api-client, simple-salesforce, httpx (Zoho/Dynamics/Freshworks/LSQ) |
| Frontend | React 19, Vite, Tailwind CSS v4, shadcn/ui, TanStack Query, Wouter, Lucide |
| Real-time | WebSocket (/ws/dashboard), SSE (/transcript/stream) |
| Testing | pytest, pytest-asyncio, httpx ASGI transport |
| Deploy | Render (backend), Vercel (dashboard), ngrok (dev OAuth) |

---

## Demo flow (3-minute version)

1. **Open dashboard** → Sandbox mode banner visible, 5 clients in sidebar
2. **Select Vikram Desai** (high risk) → SyncPanel shows risk badge, CC stress factors, open complaint
3. **Click "Sync Now"** → Call initiated (simulated or real), LiveFeed updates, WebhookActivityPanel shows received → processed
4. **View transcript** → drawer shows ASR text from the briefing
5. **Click "CRM View"** → embedded sandbox contact page slides in from right
6. **Hold mic button** → say *"Create a follow-up task for next Monday at 9 AM"* → confirmation modal → Execute → toast + WS event
7. **Navigate to Integrations** → connect HubSpot (real OAuth if key set, otherwise shows Sandbox badge)
8. **Provision** → one click creates the 9 missing HubSpot contact properties
9. **Repeat Sync Now** → briefing now written to HubSpot Note + `last_rm_interaction_date` updated live in HubSpot

**ROI story:** 15-20 min CRM prep → 30 seconds. Complaints: 0% flagged → 100%. CRM touchpoint: never logged → auto-logged. Cost: ~₹15/call.
