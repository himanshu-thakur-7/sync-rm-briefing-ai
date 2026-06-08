# Enabling Inbound on the Concierge Agent

The Concierge agent (`50b061c7-ca97-43b1-8b72-16c7f59419e3`) is provisioned, has the prompt, voice, and outbound from-number attached. The only step left is enabling **inbound** on a phone number and binding it to the agent.

The Ringg API for this requires a `number_id` that already has inbound enabled. Your current DID (`ffc7dd03-3a4d-46ef-9aab-5aba0699ad36`) is outbound-only — Ringg returned `"Inbound is not enabled for this number."` when we tried to attach it.

You have two paths.

## Path A · Enable inbound on your existing DID (one toggle, ~30 seconds)

This is what you want if you have one phone number and want it to do both directions.

1. Sign in to **https://app.ringg.ai** (or wherever your Ringg dashboard lives).
2. Left nav → **Phone Numbers** (sometimes under **Calling** or **Telephony**).
3. Find the number whose ID is `ffc7dd03-3a4d-46ef-9aab-5aba0699ad36` (it's the one wired to outbound right now).
4. Open it. Look for one of these toggles:
   - **"Enable Inbound"** / **"Allow inbound calls"** / **"Bidirectional"**
   - Or under a **Capabilities** section: tick the **Inbound** / **Receive** box.
5. Save. (Ringg may take ~30 seconds to provision the inbound route.)
6. Then either:
   - **In the same UI**, scroll to **"Attached Agent"** / **"Inbound agent"** → pick **`SYNC - Concierge`** from the dropdown, OR
   - Come back to the terminal and run:
     ```bash
     curl -X PATCH "https://prod-api.ringg.ai/ca/api/v0/agent/v1/" \
       -H "X-API-KEY: $(grep ^RINGG_API_KEY= .env | cut -d= -f2)" \
       -H "Content-Type: application/json" \
       -d '{
         "operation": "attach_inbound_number",
         "agent_id": "50b061c7-ca97-43b1-8b72-16c7f59419e3",
         "number_id": "ffc7dd03-3a4d-46ef-9aab-5aba0699ad36"
       }'
     ```
     You should see `{"message":"Agent updated successfully!", ...}` — no more "Inbound is not enabled".

7. Update `.env` with the human-readable number so the dashboard widget displays it:
   ```bash
   RINGG_INBOUND_NUMBER=+91XXXXXXXXXX     # e.g. +918073456789
   ```
8. Restart the backend. The "§ The Concierge Line" widget on the dashboard will now show the number to dial.

## Path B · Provision a separate inbound number (~2 minutes)

This is what you want if your provider doesn't allow bidirectional on the same DID, OR you want a dedicated "concierge line" number that's visually distinct from outbound caller-ID.

1. Ringg dashboard → **Phone Numbers** → **Buy/Provision number** (or **Add number**).
2. Pick **Inbound** capability (some UIs ask "Inbound only / Outbound only / Both" — pick **Both** or **Inbound**).
3. Pick the country/region you want the RM to dial.
4. Once provisioned, copy the new number's **UUID** (not the phone number itself — the GUID in the URL or detail page).
5. Run:
   ```bash
   curl -X PATCH "https://prod-api.ringg.ai/ca/api/v0/agent/v1/" \
     -H "X-API-KEY: $(grep ^RINGG_API_KEY= .env | cut -d= -f2)" \
     -H "Content-Type: application/json" \
     -d '{
       "operation": "attach_inbound_number",
       "agent_id": "50b061c7-ca97-43b1-8b72-16c7f59419e3",
       "number_id": "<paste the new UUID here>"
     }'
   ```
6. Set the human-readable number in `.env`:
   ```bash
   RINGG_INBOUND_NUMBER=+91XXXXXXXXXX
   ```
7. Restart the backend.

## Verify

```bash
curl -s http://localhost:8000/api/v1/concierge/info | python3 -m json.tool
```

Should print `{"configured": true, ...}`. Refresh `/dashboard` → the "§ The Concierge Line" widget shows the number.

Now dial it from any phone. SYNC will answer: *"Hi! This is SYNC. Who do you need a sync on?"*
- Say **"Tell me about Vikram"** → SYNC pulls Vikram from Pipedrive and briefs you.
- Say **"Create a follow-up task with Vikram for tomorrow 3 PM"** → SYNC creates the task in Pipedrive and confirms.
- Say **"Add a note that he was interested in the SIP pitch"** → SYNC adds the note.
- Say **"Mark the complaint as resolved"** → SYNC updates the ticket status.
- Say **"Schedule a meeting with Priya for Thursday at 10"** → SYNC schedules it.

(Anything the voice-command engine can parse — see `services/voice_command_engine.py` tool schema.)

## Webhook (so the inbound call's transcript reaches the dashboard)

In the Ringg dashboard, on the Concierge agent → **Webhooks** or **Events**:
- Add a webhook URL: `${BACKEND_URL}/api/v1/webhooks/ringg`
- Subscribe to: `call_started`, `call_completed`, `all_processing_completed`, `transcript_chunk`

If `BACKEND_URL` is `http://localhost:8000`, Ringg can't reach you — run **ngrok** and point `BACKEND_URL` at the ngrok HTTPS URL first.
