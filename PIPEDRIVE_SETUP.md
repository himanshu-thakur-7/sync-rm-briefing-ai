# Pipedrive — the demo CRM

3-minute setup. Pipedrive is the CRM SYNC demos against on stage. The
auth path is a personal API token, not OAuth — much faster to wire up.

## 1 · Create a Pipedrive account

If you don't have one: https://www.pipedrive.com → start a free trial.
The trial gives you full API access. No credit card needed.

## 2 · Get the API token + company domain

1. Top-right avatar → **Personal preferences**
2. Left nav → **API**
3. Copy **Your personal API token** (a 40-char hex string)
4. Note your **company domain** — it's the URL prefix: `https://<domain>.pipedrive.com` (e.g. `acmedemo`)

## 3 · Drop them into `.env`

Open `/Users/little_beast/Desktop/sync-rm-briefing-ai/.env` and set:

```bash
PIPEDRIVE_API_TOKEN=your_40_char_token_here
PIPEDRIVE_COMPANY_DOMAIN=acmedemo       # ← just the subdomain, no https://
```

## 4 · Seed the demo data

```bash
cd /Users/little_beast/Desktop/sync-rm-briefing-ai
source .venv/bin/activate
python scripts/seed_pipedrive.py
```

Idempotent. Creates:

- 9 custom Person fields + 6 custom Deal fields under your own labels
- 5 demo Persons (Rahul, Priya, Amit, Sneha, Vikram) with risk + cross-sell data populated
- A Deal per loan, linked to each Person
- Complaint Activities + a "last call" Activity so SYNC's `get_interactions()` finds something real

Expected output:

```text
✓ Authenticated to Pipedrive as <your name>

[1/4] Ensuring custom fields exist…
  + person.Risk Score  (key=a1b2c3d4…)
  + person.Risk Factors  (key=e5f6a7b8…)
  …

[2/4] Upserting 5 demo Persons…
  + Rahul Mehta (created · id=1)
  + Priya Sharma (created · id=2)
  …

[3/4] Creating loan Deals…
  + Rahul Mehta — Home Loan (id=1)
  …

[4/4] Creating Activities (complaints + recent calls)…
  + complaint (open) → Rahul Mehta
  …

✓ Done. Open https://<domain>.pipedrive.com/persons/list
```

## 5 · Make Pipedrive the default source

Edit `.env`:

```bash
CRM_ADAPTER=pipedrive
```

Restart the backend:

```bash
cd artifacts/sync-backend
source ../../.venv/bin/activate
pkill -f "uvicorn main:app"; sleep 1
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 6 · Verify

```bash
# Should return the 5 Persons you just seeded
curl -s http://localhost:8000/api/v1/clients | python3 -m json.tool | head -30
```

Open the dashboard → top-right source switcher → pick **Pipedrive**.
The SyncPanel client dropdown will list Rahul/Priya/Amit/Sneha/Vikram with their risk pills + brand badge.

## 7 · Trigger a briefing call

Same as any other CRM:

```bash
curl -X POST http://localhost:8000/api/v1/calls/sync-now \
  -H "Content-Type: application/json" \
  -d '{"client_id":"<pipedrive_person_id>","rm_phone":"+91YOUR_PHONE","rm_name":"Himanshu"}'
```

After the call:
- Open the Pipedrive Person record → **Notes** → you'll see `[SYNC Briefing] …`
- The `Last RM Interaction Date` custom field is updated to today

## How custom fields work in Pipedrive (the gotcha)

Unlike HubSpot, Pipedrive doesn't use snake_case field names in API
payloads. Every custom field is identified by a **40-char hex key** that
Pipedrive generates when you create the field. Example:

```json
{
  "name": "Rahul Mehta",
  "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0": "high"   ← Risk Score value
}
```

The seed script handles this for you. The PipedriveCRMAdapter resolves
LABELS (e.g. "Risk Score") → 40-char keys on first use via the
`/personFields` and `/dealFields` endpoints, and caches the mapping.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` | Token wrong or company domain wrong. Token is per-user; ensure it's the same Pipedrive workspace as the company domain. |
| Custom fields not appearing on Person records | Pipedrive UI caches schemas — hard-refresh, or open the Person in a new tab. The field group label is the custom-fields default group (you can rename in Pipedrive Settings). |
| `404` on `/persons/{id}` after seed | The seed script's "find by email" lookup uses `exact_match`. If you've previously created Rahul with a different email, the seed creates a duplicate. Delete duplicates in Pipedrive UI. |
| Dashboard says "EMPTY" for HubSpot but you only set Pipedrive | Expected — HubSpot is a different env var. The source switcher in the dashboard lets you pick which CRM SYNC reads from per session. |
