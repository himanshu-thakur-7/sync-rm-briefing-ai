# Attaching the CRM tools to Ringg agents (dashboard — one-time, ~5 min)

**Why this is needed:** Ringg's public API has no operation for attaching
custom on-call tools (verified against their OpenAPI spec). The agent prompt
tells it to call `ask_crm` / `log_action`, but until the tools exist on the
agent, it says *"I can't do that."* Tools are added in the **Ringg dashboard**.

Do this for each conversational agent (Concierge — and optionally the
Morning Brief agent):

## Where

Ringg dashboard → **Assistants** → open the agent (e.g. `SYNC - Concierge`)
→ look for **Tools** / **Actions** / **Custom tools** (an "Add tool" or
"Custom API tool" option) → add the two tools below.

## Tool 1 — ask_crm

| Field | Value |
|---|---|
| Name | `ask_crm` |
| Description | `Look up a client by name in the CRM and get a spoken briefing: risk, portfolio, complaints, last contact, and the recommended pitch. Use for ANY information question about a client.` |
| Method | `POST` |
| URL | `https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/ask_crm` |
| Headers | `Content-Type: application/json` |

**Parameters (LLM-filled):**
- `question` · string · required — *The user's question, verbatim.*
- `client_hint` · string · optional — *Client first name if mentioned.*

**Response key to read back:** `spoken`
(The endpoint also returns `answer` / `response` / `message` — pick whichever
the UI offers.)

## Tool 2 — top_priority

| Field | Value |
|---|---|
| Name | `top_priority` |
| Description | `Find the single highest-urgency client RIGHT NOW from the live CRM (runs Risk Radar). Returns a one-paragraph spoken brief and the client_id.` |
| Method | `POST` |
| URL | `https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/top_priority` |
| Headers | `Content-Type: application/json` |

**Parameters:** none required.
**Response key to read back:** `spoken`

## Tool 3 — start_call_with

| Field | Value |
|---|---|
| Name | `start_call_with` |
| Description | `Dial the named client and bring them onto the line. The RM keeps talking; the client is brought into the call. ALWAYS call this when the RM agrees to be connected.` |
| Method | `POST` |
| URL | `https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/start_call_with` |
| Headers | `Content-Type: application/json` |

**Parameters:**
- `client_hint` · string · required — *Client first name (or "top" for current top priority).*
- `play_id` · string · optional — *Carry through from a prior top_priority result.*

**Response key to read back:** `spoken`

## Tool 4 — log_action

| Field | Value |
|---|---|
| Name | `log_action` |
| Description | `Execute a CRM action the user asked for: create a task, log a note, schedule a meeting or follow-up, mark a complaint resolved or escalated, update a field. Returns a spoken confirmation.` |
| Method | `POST` |
| URL | `https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/log_action` |
| Headers | `Content-Type: application/json` |

**Parameters (LLM-filled):**
- `intent` · string · required — *Short label: create_task, log_note, schedule_follow_up, mark_complaint_resolved, update_field.*
- `details` · string · required — *Full natural-language description, preserving dates, times and client names.*
- `client_hint` · string · optional — *Client first name.*

**Response key to read back:** `spoken`

## Verify before any call (curl)

```bash
curl -s -X POST https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/ask_crm \
  -H "Content-Type: application/json" \
  -d '{"question":"tell me about Vikram","client_hint":"Vikram"}' | python3 -m json.tool

curl -s -X POST https://sync-backend-u9rv.onrender.com/api/v1/ringg-tools/log_action \
  -H "Content-Type: application/json" \
  -d '{"intent":"create_task","details":"create a task to send Vikram the proposal tomorrow","client_hint":"Vikram"}' | python3 -m json.tool
```

Both must return `"status": "success"` with a `spoken` sentence — the second
one actually writes to Pipedrive (delete the test task after).

## Then test on a real call

Call the Concierge (or trigger any agent call) and say:
1. *"Tell me about Vikram."* → it should read the live briefing.
2. *"Create a task to send him the proposal tomorrow."* → spoken confirmation
   + the task appears in Pipedrive + the dashboard panels light up.

## Notes

- The endpoints accept any request shape (query params, flat JSON, or args
  nested under `arguments`/`parameters`) and ALWAYS return 200 with `spoken`,
  so the agent never dead-ends even on CRM errors.
- On buildathon day (agents re-created from scratch), re-attach both tools to
  the fresh agents — same values as above.
- If the tool builder requires a test call before saving, the curl above
  doubles as the expected result.
