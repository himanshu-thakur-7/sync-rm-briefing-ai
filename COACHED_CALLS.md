# Coached Calls — live whisper coaching on a real RM ↔ client phone call

The dashboard's whisper coaching works on any call whose audio passes through
infrastructure we control. A plain cellphone call's audio is unreachable (by
OS design), so SYNC offers two routes:

| Route | How the audio reaches SYNC | Status |
|---|---|---|
| **Twilio bridge** (primary) | Twilio dials the RM, bridges in the client, and forks both legs' audio to our WebSocket via Media Streams | Built — needs Twilio creds |
| **Ringg chaperone** (backup) | Ringg's agent dials the client, transfers the RM in, stays on the line as a silent transcriber | Built — validate transfer behavior on a real call |

Both feed the same pipeline: transcript lines → coaching engine →
`coaching_nudge` over WebSocket → visual card + Whisper Mode audio in the
RM's earbud.

---

## Route A · Twilio bridge (primary)

### One-time setup (~15 min)

1. **Create a Twilio account** at https://www.twilio.com/try-twilio — trial
   gives ~$15 credit (plenty: India calls cost roughly $0.03–0.05/min/leg).
2. **Get a number**: Console → Phone Numbers → Buy a number (a US number is
   fine and cheapest; it can dial India).
3. **Trial-account caveat**: outbound calls only reach **verified** numbers.
   Console → Phone Numbers → Verified Caller IDs → add BOTH the RM phone and
   the client phone you'll demo with (each gets an OTP).
4. **Set env vars on Render** (sync-backend → Environment):
   ```
   TWILIO_ACCOUNT_SID  = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN   = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_FROM_NUMBER  = +1XXXXXXXXXX
   ```
   Also confirm `BACKEND_URL=https://sync-backend-u9rv.onrender.com` is set —
   Twilio fetches TwiML from it and streams media to `wss://…` on it.
5. Render redeploys automatically. Verify:
   ```bash
   curl https://sync-backend-u9rv.onrender.com/api/v1/coached-calls/status
   # → {"twilio": {"configured": true, ...}, "active_route": "twilio"}
   ```

### Using it

1. Dashboard → **Brief A Client** → pick the client, check RM phone.
2. Click **"Coached Call · SYNC listens live"**.
3. Your phone rings first. Answer → you hear *"Sync is on the line…"* → the
   client's phone rings and you're bridged.
4. Talk normally. Rolling ~3-second windows of both voices are transcribed
   (Ringg Parrot STT → Whisper fallback) and stream onto the dashboard;
   coaching nudges fire as cards + earbud whispers (🎧 toggle in masthead).
5. Hang up → post-call intelligence runs on the full transcript automatically.

### Call flow

```
RM phone ←── leg 1 ──→ Twilio ←── leg 2 ──→ Client phone
                          │
                          └── Media Stream (WSS, μ-law 8 kHz, both tracks)
                                  ↓
                 backend /api/v1/coached-calls/media/{key}
                                  ↓ 3 s windows + silence gate
                          STT (Ringg → Whisper)
                                  ↓
              emit_transcript_chunk → coaching engine
                                  ↓
        dashboard: live transcript + whisper cards + 🎧 audio
```

### Notes & limits

- The demo uses the request's `client_phone` if provided, else
  `DEMO_CLIENT_PHONE` from env. For the hackathon set
  `DEMO_CLIENT_PHONE=+91…` (the phone playing the "client").
- Whisper latency ≈ window size (3 s) + STT (~1 s) + GPT nudge (~1 s):
  expect tips ~4–5 s behind speech. Good enough to feel live on stage.
- Trial calls play a short "trial account" preamble — mention it or upgrade
  ($20) to remove.
- Twilio webhook signature validation is skipped (hackathon scope); add
  `X-Twilio-Signature` checks before production.

---

## Route B · Ringg silent chaperone (backup)

No new accounts needed — uses your existing Ringg outreach agent.

1. Dashboard → pick client → **Coached Call** (it auto-falls back to this
   route when Twilio isn't configured; or POST
   `/api/v1/coached-calls/start` with `"route": "ringg"`).
2. Ringg's agent dials the client: *"Hi! This is SYNC from Acme — I have
   Himanshu on the line for you, connecting you now."* and transfers in the
   RM's phone.
3. **The open question to validate on a real call:** does Ringg keep its
   agent (and its in-call transcription) on the line after the transfer?
   - If transfer is conference-style → `transcript_chunk` webhooks keep
     arriving → coaching stays live. ✅
   - If it's a blind transfer (agent drops) → transcripts stop at handoff;
     you still get the post-call summary from the pre-transfer segment. ⚠️

### 5-minute hackathon-morning test

1. Set `DEMO_CLIENT_PHONE` to phone #1, use phone #2 as RM phone.
2. POST `/api/v1/coached-calls/start` with `"route": "ringg"`.
3. Answer both phones; after the transfer connects you, say a trigger line
   on the client phone ("I'm a bit worried about the EMIs honestly").
4. Watch the dashboard: if a transcript line + whisper card appears →
   chaperone works; lead with it. If not → use the Twilio route.
