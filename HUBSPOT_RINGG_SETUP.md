# Setting up Ringg AI + HubSpot

Step-by-step to go from zero to a real demo with **real Ringg phone calls** and **real HubSpot data**. Plan for ~20 minutes start to finish.

> Already done locally? Skip to **§ Part 5 · Verify**. Already deployed? Mirror the same env vars into Render.

---

## Part 1 · Ringg AI

### 1.1 Create the account and get the API key

1. Go to **https://www.ringg.ai** → sign up (Google/email).
2. Open the dashboard. In the left nav, find **Settings → API Keys** (the exact label varies — look for "Workspace API Key" or "Developer").
3. Click **Generate / Reveal API Key** → copy it. It looks like `rngg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.

### 1.2 Get the `from_number_id` (the phone Ringg dials *from*)

1. In Ringg dashboard: **Phone Numbers** → **Buy/Provision Number**.
2. Pick an Indian DID (or US, depending on what you'll demo to). The hackathon usually gives free credits — confirm in their #buildathon channel.
3. Once provisioned, open the number's detail page and copy the **Number ID** (a UUID-ish string). This is `RINGG_FROM_NUMBER_ID`.

### 1.3 Drop the credentials into `.env`

```bash
cd /Users/little_beast/Desktop/sync-rm-briefing-ai
```

Edit `.env` (create from `.env.example` if needed) and set:

```bash
RINGG_API_KEY=rngg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RINGG_BASE_URL=https://prod-api.ringg.ai/ca/api/v0
RINGG_FROM_NUMBER_ID=<your number id from step 1.2>
BACKEND_URL=http://localhost:8000     # use your ngrok / Render URL for webhooks
```

### 1.4 Provision the three SYNC agents on Ringg

This creates the **Briefing Agent**, the **Outreach Agent** (for Risk Radar save calls), and the **Morning Brief Agent** (the conversational standup), and registers webhook callbacks.

```bash
source .venv/bin/activate
python scripts/setup_ringg_agent.py
```

Expected output:

```text
Found N en-IN voices
RINGG_AGENT_ID=agt_xxxxxxxxxxxx
Webhooks configured for briefing agent
RINGG_OUTREACH_AGENT_ID=agt_yyyyyyyyyyyy
Webhooks configured for outreach agent
RINGG_MORNING_BRIEF_AGENT_ID=agt_zzzzzzzzzzzz
Webhooks configured for morning brief agent

NOTE: The Morning Brief agent uses mid-call function tools (ask_crm, log_action). …
```

Copy all three agent IDs into `.env`:

```bash
RINGG_AGENT_ID=agt_xxxxxxxxxxxx
RINGG_OUTREACH_AGENT_ID=agt_yyyyyyyyyyyy
RINGG_MORNING_BRIEF_AGENT_ID=agt_zzzzzzzzzzzz
```

### 1.5 (Important for OAuth + webhooks) Expose the backend over HTTPS

Ringg's webhooks need a public HTTPS URL. For local dev, use ngrok:

```bash
# in a fresh terminal
ngrok http 8000
```

Copy the `https://….ngrok-free.app` URL and update `.env`:

```bash
BACKEND_URL=https://abc123.ngrok-free.app
OAUTH_REDIRECT_BASE=https://abc123.ngrok-free.app
```

Re-run `python scripts/setup_ringg_agent.py` to refresh the webhook URLs on the agents.

---

## Part 2 · HubSpot — fastest path (Private App)

Use this path for the demo. It takes 3 minutes and works for both reading and writing CRM data. (OAuth path is in §3 — only needed if you want the "Connect HubSpot" button to do the real OAuth dance on stage.)

### 2.1 Create a HubSpot account (free)

1. Go to **https://app.hubspot.com/signup** → sign up. Free Hub Cloud account is fine.
2. Skip the onboarding wizard if it appears.

### 2.2 Create a Private App and get the access token

1. Top-right gear icon → **Settings**.
2. Left nav: **Integrations → Private Apps**.
3. Click **Create a private app**.
4. **Basic Info tab**: name it `SYNC Demo`, drop in any description.
5. **Scopes tab** — enable these (paste into the search box):

   **CRM:**
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `crm.objects.tickets.read`
   - `crm.objects.tickets.write`
   - `crm.objects.notes.write`
   - `crm.schemas.contacts.read`
   - `crm.schemas.contacts.write`
   - `crm.schemas.deals.read`
   - `crm.schemas.deals.write`

6. Click **Create app** → confirm.
7. On the next screen click the **Access token** field → **Show token** → **Copy**. Looks like `pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

### 2.3 Put the token into `.env`

```bash
HUBSPOT_API_KEY=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

(The SYNC backend treats this as the "legacy" private-app fallback — the HubSpot adapter uses it whenever no OAuth token is stored.)

---

## Part 3 · HubSpot — production path (OAuth Developer App)

Skip if you're only doing the Private App route. Do this **in addition** if you want the dashboard's **Connect HubSpot** button to do a real OAuth dance during the demo.

### 3.1 Create a developer account + dev app

1. **https://developers.hubspot.com** → sign up (separate from the regular account).
2. **Apps → Create app**.
3. **Auth tab**:
   - **Redirect URL:** `https://abc123.ngrok-free.app/api/v1/oauth/callback/hubspot` (use your ngrok URL exactly; HubSpot rejects `localhost`).
   - **Scopes:** add the same ones from §2.2.
4. **App Info tab**: fill in any name and description; you don't need to submit it for the marketplace.
5. Copy from the **Auth** tab:
   - **Client ID** → `HUBSPOT_CLIENT_ID`
   - **Client secret** → `HUBSPOT_CLIENT_SECRET`

### 3.2 Put them into `.env`

```bash
HUBSPOT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
HUBSPOT_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
OAUTH_REDIRECT_BASE=https://abc123.ngrok-free.app
```

### 3.3 Use the test account

In developers.hubspot.com → **Test accounts** → **Create test account**. This is the HubSpot you'll OAuth into. Switch into it (top-right account picker on app.hubspot.com).

---

## Part 4 · Seed HubSpot with the SYNC demo data

This creates **9 custom Contact properties + 6 custom Deal properties + 5 demo contacts + their loans + complaint tickets**.

```bash
cd /Users/little_beast/Desktop/sync-rm-briefing-ai
source .venv/bin/activate
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxx... python scripts/seed_hubspot.py
```

(`HUBSPOT_ACCESS_TOKEN` and `HUBSPOT_API_KEY` are interchangeable here.)

Expected:

```text
✓ Authenticated to HubSpot

[1/4] Ensuring custom properties exist…
  + group 'sync_rm_briefing' on contacts
  + group 'sync_rm_briefing' on deals
  + risk_score on contacts
  + risk_factors on contacts
  + last_rm_interaction_date on contacts
  + cross_sell_product_1 on contacts
  …
  + product_type on deals
  + emi_amount on deals
  …

[2/4] Upserting 5 demo contacts…
  + Rahul Mehta (created · id=12345)
  + Priya Sharma (created · id=12346)
  + Amit Kulkarni (created · id=12347)
  + Sneha Reddy (created · id=12348)
  + Vikram Desai (created · id=12349)

[3/4] Creating loan deals…
  + Rahul Mehta — Home Loan (id=…)
  + Priya Sharma — Car Loan (id=…)
  …

[4/4] Creating complaint tickets…
  + Branch Experience (open) → Rahul Mehta (id=…)
  + Loan Restructuring (escalated) → Amit Kulkarni (id=…)
  + Late Payment Charges (open) → Vikram Desai (id=…)

✓ Done. Open HubSpot → Contacts to see Rahul, Priya, Amit, Sneha, Vikram.
```

The script is **idempotent** — re-running it skips properties that already exist and updates the contacts in place.

---

## Part 5 · Verify

### 5.1 Restart the backend

```bash
cd artifacts/sync-backend
source ../../.venv/bin/activate
pkill -f "uvicorn main:app"; sleep 1
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5.2 Sanity-check Ringg

```bash
# Should print three agent IDs
grep RINGG .env
```

### 5.3 Sanity-check HubSpot via SYNC's own adapter

```bash
curl -s http://localhost:8000/api/v1/integrations | python3 -m json.tool
```

If you've only done §2 (Private App, no OAuth), you'll see the FakeLeadSquared sandbox + Mock CRM. To use HubSpot from the dashboard:

**Option A · Connect via the OAuth Connect button (you did §3):**
1. Open `http://localhost:3001/settings/integrations`
2. Click **Connect HubSpot** → real OAuth consent → redirect back.
3. The new connection appears in the list; click **Connect** in the dashboard's source switcher.

**Option B · Use the Private App fallback (you did only §2):**
- The HubSpot adapter falls back to `HUBSPOT_API_KEY` automatically. To make it the active source, in `.env`:
  ```bash
  CRM_ADAPTER=hubspot
  ```
  Restart the backend. The default `legacy_hubspot` connection now points at your private app.

### 5.4 Trigger a real briefing

In the dashboard:

1. **Sync Now** panel → pick **Rahul Mehta** → enter your phone → **Initiate Briefing Call**.
2. Your phone rings within ~5 seconds. SYNC narrates Rahul's profile in 45 seconds.
3. Open the HubSpot contact → **Activities** tab → you should see a new Note logged by SYNC, and `last_rm_interaction_date` updated to today.

### 5.5 Trigger an autonomous save call

1. Open `http://localhost:3001/radar`.
2. Click **Run Radar Scan**. Vikram Desai should appear with `CRITICAL · npa_risk`.
3. Click **Place Save Call** on his row → SYNC outbound-dials the number you configured for the *client* (set `DEMO_CLIENT_PHONE` in `.env` if you want it to dial your second phone).

### 5.6 Trigger a conversational morning standup

1. Open `http://localhost:3001/morning-brief`.
2. **Schedule a brief** → name, your phone, 07:45 IST, Mon-Fri, Hinglish.
3. **Trigger Now** → SYNC dials you and walks today's agenda. Ask "tell me about Vikram" or "create a follow-up task for tomorrow 4 PM" — SYNC will call into `/ask` and `/act` mid-call.

---

## Common gotchas

| Symptom | Fix |
|---|---|
| "OAuth redirect not allowed" on HubSpot OAuth | The redirect URL on the HubSpot dev app must match `OAUTH_REDIRECT_BASE` exactly (including trailing slashes — there are none). HubSpot blocks `localhost` — use ngrok. |
| Ringg call never arrives but the dashboard shows "calling" | `RINGG_FROM_NUMBER_ID` is wrong, or that number isn't approved to dial your destination. Check Ringg dashboard → Phone Numbers → outbound-capability. |
| Ringg webhook never fires (no live updates) | `BACKEND_URL` must be public HTTPS (your ngrok or Render URL). Re-run `setup_ringg_agent.py` after changing it. |
| Seeder errors "PROPERTY_DOESNT_EXIST" on a deal | Re-run `seed_hubspot.py` — step [1/4] creates the properties first, then step [3/4] uses them. If the run was interrupted between steps, re-run from scratch. |
| Contacts created but no Risk Score visible | HubSpot UI caches schemas. Refresh the page; the property appears under "SYNC RM Briefing" group on the contact. |
| Seeder fails with `401` | Token is wrong or copied with a trailing space. Re-copy from HubSpot → Private Apps. |
| Backend error: `'NoneType' object has no attribute 'access_token'` | You ran the OAuth flow but `SECRET_KEY` changed between then and now → the encrypted token can't be decrypted. Disconnect the connection in `/settings/integrations` and re-OAuth. |

---

## Reference — required `.env` block

```bash
# Ringg
RINGG_API_KEY=rngg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RINGG_BASE_URL=https://prod-api.ringg.ai/ca/api/v0
RINGG_FROM_NUMBER_ID=<from-number id>
RINGG_AGENT_ID=agt_xxxxxxxxxxxx
RINGG_OUTREACH_AGENT_ID=agt_yyyyyyyyyyyy
RINGG_MORNING_BRIEF_AGENT_ID=agt_zzzzzzzzzzzz

# HubSpot — Private App (Path A, simpler)
HUBSPOT_API_KEY=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CRM_ADAPTER=hubspot                    # makes HubSpot the default source

# HubSpot — OAuth (Path B, optional, for the Connect button demo)
HUBSPOT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
HUBSPOT_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
OAUTH_REDIRECT_BASE=https://abc123.ngrok-free.app

# Public HTTPS for webhooks
BACKEND_URL=https://abc123.ngrok-free.app

# Demo extras
DEMO_RM_NAME=Himanshu
DEMO_RM_PHONE=+91...                   # your phone — receives briefing + standup calls
DEMO_CLIENT_PHONE=+91...               # your *second* phone — receives Save Calls
DEMO_COMPANY_NAME=Acme

# AI (optional but makes everything sound better)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
