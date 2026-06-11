# SYNC — Hackathon Day Runbook

## 0. Night before
- [ ] Set up a free UptimeRobot monitor pinging `https://sync-backend-u9rv.onrender.com/api/healthz` every 5 min (Render free tier sleeps after 15 min idle; cold start ≈ 30–60 s).
- [ ] Create Twilio trial account → buy a number → **verify BOTH demo phone numbers** (Verified Caller IDs — trial only calls verified numbers).
- [ ] Charge both phones; pack one wired earbud.
- [ ] Queue the backup video locally (not a cloud link).

## 1. Env vars on Render (first 30 min — the deployed backend has NO Ringg creds today)
Copy from local `.env` → Render → sync-backend → Environment:
```
RINGG_API_KEY                  ← without this, all "real" calls silently simulate
RINGG_AGENT_ID
RINGG_FROM_NUMBER_ID
RINGG_OUTREACH_AGENT_ID
RINGG_MORNING_BRIEF_AGENT_ID
RINGG_CONCIERGE_AGENT_ID
OPENAI_API_KEY                 ← upgrades coaching/briefings/analysis to GPT-4o
TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER
DEMO_CLIENT_PHONE / DEMO_RM_PHONE   ← the two phones you actually have
```
Then register the webhook on each Ringg agent (dashboard → agent → Webhooks):
`https://sync-backend-u9rv.onrender.com/api/v1/webhooks/ringg`

### Verify (curl or browser)
- `/api/v1/voice/stt-status`        → `active_engine` ≠ "none"
- `/api/v1/coached-calls/status`    → twilio.configured: true
- `/api/v1/integrations`            → Pipedrive default ✓

## 2. Real-call testing order (hours 1–4)
1. Briefing call → own phone (Brief A Client → Initiate Briefing Call).
2. Risk Radar save-call → second phone as "client"; check warm transfer.
3. Morning Brief → Trigger Now.
4. **Chaperone test (5 min, decides the whisper story)**: COACHED_CALLS.md
   Route B — after the Ringg transfer connects both phones, say "I'm a bit
   worried about the EMIs" on the client phone. Whisper card on dashboard?
   → YES: live coaching works on real calls via Ringg alone.
   → NO: use the Twilio coached call (Route A) for the real-call story.
5. One Twilio coached call end-to-end.
6. Inbound concierge per INBOUND_SETUP.md (needs Ringg credits/number).

## 3. Stage demo (4 min)
1. Video (45 s).
2. "Seed demo day" → ROI ledger counts up live.
3. Pick **Priya** (RM name stays **Himanshu** — pre-generated voices) →
   **▶ Simulate Call** through laptop speakers: Eric/Sarah talk, whisper
   cards chime in, **approve the meeting card** → open Pipedrive → the
   Thursday 4:00 PM meeting is really on the calendar.
4. If Ringg is live: real briefing call on speakerphone.
5. Close on the ledger + integrations page ("8 CRMs, voice on top of all").

## 4. Gotchas
- Chrome only. Click the page once before the sim (browser audio gesture).
- Render restart wipes SQLite → re-run "Seed demo day" right before going on.
- PII scrub toggle (eye icon, header) if projecting real data.
- Trial Twilio plays a short preamble; $20 upgrade removes it.
- Judges ask "is the coaching scripted?" → No: every line streams through
  the live engine (same pipeline as real calls); the script is just the
  conversation, the nudges/actions are computed.

## 5. After the event
- Rotate the ElevenLabs key + Pipedrive token (both exposed during dev).
- Downgrade/cancel Twilio if upgraded.
