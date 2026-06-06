# Deploying SYNC — Free Tier

The whole thing fits in two free tiers:

| Layer | Where | Free quota |
|---|---|---|
| Backend (FastAPI + WebSocket) | **Render** Web Service | 750 hrs/month · 512 MB · sleeps after 15 min idle |
| Frontend (Vite + React) | **Vercel** Static + CDN | 100 GB bandwidth · unlimited builds |

Total cost: **₹0**. First cold start after sleep takes ~30 sec — fine for a demo.

---

## 0 · Pre-flight

You'll need:
- A **GitHub** account with this repo pushed up
- A **Render** account (sign in with GitHub)
- A **Vercel** account (sign in with GitHub)

Make sure your local changes are committed and pushed:

```bash
cd /path/to/sync-rm-briefing-ai
git status                       # confirm nothing important is uncommitted
git add -A
git commit -m "ready to deploy"
git push origin main
```

> **Heads up:** Render free tier has *no* persistent disk. The SQLite database (`sync.db`) is re-created and seeded with the LeadSquared sandbox + 5 demo clients on every cold boot. That's intentional and fine for the demo. If you do real OAuth connects on the deployed instance, they'll be wiped on the next restart.

---

## 1 · Deploy the backend to Render

### Option A — Blueprint (uses `render.yaml`, recommended)

1. Go to https://dashboard.render.com → **New +** → **Blueprint**
2. Connect the GitHub repo → click **Apply**
3. Render reads `render.yaml` and provisions a service called **sync-backend**
4. Wait 3–5 min for the build to finish
5. Copy your backend URL (looks like `https://sync-backend.onrender.com`)

### Option B — Manual web service

If Blueprint isn't your style:

1. Go to https://dashboard.render.com → **New +** → **Web Service**
2. Connect the GitHub repo
3. Fill in:
   - **Name:** `sync-backend`
   - **Region:** Singapore (best for India) or Oregon
   - **Branch:** `main`
   - **Root Directory:** *(leave blank)*
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r artifacts/sync-backend/requirements.txt`
   - **Start Command:** `cd artifacts/sync-backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
4. Click **Create Web Service**
5. Once live, copy the URL (e.g. `https://sync-backend.onrender.com`)

### After backend deploy — verify

```bash
curl https://sync-backend.onrender.com/api/healthz
# → {"status":"ok"}

curl https://sync-backend.onrender.com/api/v1/clients | head -c 200
# → [{"client_id":"lsq_001","name":"Rahul Mehta", ...
```

If you see the 5 clients, the backend is healthy.

---

## 2 · Deploy the frontend to Vercel

1. Go to https://vercel.com/new
2. Click **Import** next to the GitHub repo
3. Vercel will auto-detect Vite and may set **Root Directory** to `artifacts/sync-dashboard` — that's fine, we ship a `vercel.json` for both layouts:
   - Root Directory = `.` → uses repo-root `vercel.json`
   - Root Directory = `artifacts/sync-dashboard` → uses the sub-folder `vercel.json` that `cd ../..`'s to install workspace deps
   - **Don't touch** Build Command / Output Directory / Install Command in the wizard — let the file win
4. Expand **Environment Variables** and add (replace with your Render URL):

   | Name | Value |
   |---|---|
   | `VITE_API_URL`        | `https://sync-backend.onrender.com` |
   | `VITE_WS_URL`         | `wss://sync-backend.onrender.com` |
   | `VITE_DEMO_RM_NAME`   | `Himanshu` |
   | `VITE_DEMO_RM_PHONE`  | `+91 98765 43210` |

5. Click **Deploy**
6. Wait 1–2 min. Copy the URL (e.g. `https://sync-rm-briefing-ai.vercel.app`)

### After frontend deploy — verify

Open the URL in a browser:
- The landing page should render (cream paper + serif type)
- Click **Open Dashboard** in the masthead — should navigate to `/dashboard`
- The 5 LeadSquared sandbox clients should appear in the SyncPanel dropdown
- If the WebSocket badge says **Live** in green, everything is wired correctly

If clients don't load, check the browser DevTools Network tab — calls should hit `https://sync-backend.onrender.com/api/...`. If they hit `localhost:8000`, the env vars didn't apply — redeploy.

---

## 3 · Wire backend → frontend (CORS)

The backend already accepts any `*.vercel.app` and `*.onrender.com` origin via regex, so this usually just works. But you should still set `FRONTEND_URL` so the OAuth callbacks redirect back to your dashboard:

1. Render → **sync-backend** → **Environment**
2. Edit (or add):
   - `FRONTEND_URL` = `https://sync-rm-briefing-ai.vercel.app` (your Vercel URL)
   - `BACKEND_URL` = `https://sync-backend.onrender.com` (your Render URL)
   - `OAUTH_REDIRECT_BASE` = `https://sync-backend.onrender.com`
3. Save → Render triggers an auto-redeploy (~2 min)

---

## 4 · (Optional) Enable a real CRM integration

For the hackathon demo the FakeLeadSquared sandbox is enough. To connect a real HubSpot or Salesforce:

### HubSpot

1. Go to https://developers.hubspot.com → create an app
2. **Auth → Redirect URLs:** add `https://sync-backend.onrender.com/api/v1/oauth/callback/hubspot`
3. **Scopes:** `crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.tickets.read crm.schemas.contacts.write`
4. In Render, add env vars: `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`
5. Save → redeploy
6. Open the dashboard → **Manage Integrations** → **Connect HubSpot** → real OAuth dance

### Salesforce / Zoho / Dynamics / Freshworks / LeadSquared

Same pattern — see `README.md` for per-provider setup details.

---

## 5 · (Optional) Enable AI briefings + voice commands

To use GPT-4o briefings instead of the template fallback:

1. Render → env vars → add `OPENAI_API_KEY` (sk-…)
2. Save → redeploy

The voice command bar (post-meeting CRM actions) also uses the same key.

---

## 6 · Troubleshooting

### "Failed to fetch" / CORS error in browser console
- Check `FRONTEND_URL` in Render matches your Vercel URL exactly (no trailing slash)
- Vercel preview URLs (like `sync-rm-briefing-ai-git-feature-yourname.vercel.app`) are allowed via the regex — production should always work
- Hard-refresh the browser (Cmd+Shift+R) — Vite's HMR is local-only, prod is cached

### Render service won't start
- Check **Logs** in Render dashboard
- Common cause: requirements.txt install timed out — click **Manual Deploy** to retry

### Frontend builds locally but fails on Vercel
- Vercel uses the same Linux x64 platform our pnpm overrides keep installed — should always work
- If you see `ERR_PNPM_*`: ensure `pnpm-lock.yaml` is committed
- Check the Build Logs in Vercel for the actual error

### `Error: No Output Directory named "public" found after the Build completed`
This happens when Vercel auto-detects the Vite project at `artifacts/sync-dashboard` and sets the Project's **Root Directory** there — which makes the repo-root `vercel.json` invisible.

We ship a second `vercel.json` *inside* `artifacts/sync-dashboard/` to handle this case. Both layouts now work, but if you already created the project before this fix landed, you need to either redeploy or reset Build Settings.

**Quickest fix — redeploy with the new config in place:**
```bash
git pull && git push    # make sure the new artifacts/sync-dashboard/vercel.json is on main
```
Then on Vercel: **Deployments → ⋯ on the latest deploy → Redeploy → uncheck "Use existing build cache" → Redeploy**.

**If that still fails, reset the project's build settings:**
1. Vercel → your project → **Settings → Build & Development Settings**
2. For each of these, click the **OVERRIDE** toggle so it's **OFF** (greyed out — letting vercel.json win):
   - Build Command
   - Output Directory
   - Install Command
3. Save → **Deployments → Redeploy**

**Nuclear option — delete and re-import:**
1. Project → **Settings → bottom → Delete Project**
2. https://vercel.com/new → import the repo
3. **DO NOT touch** Root Directory, Build Command, Output Directory, or Install Command in the wizard
4. Only fill in the four `VITE_*` env vars
5. Click **Deploy**

### Backend deploy fails on `sqlmodel`/`pydantic` install
If pip resolves a bad combo, force the Python version: add env var `PYTHON_VERSION=3.11.9` in Render → restart deploy.

### Backend cold-starts are slow
- Render free tier sleeps after 15 min of no traffic. First request after sleep wakes it in ~30s
- For a demo, hit any URL 30 seconds before your stage time to wake it up
- Or upgrade to Render Starter ($7/mo) — no sleep

### WebSocket badge stuck on "Offline"
- Make sure `VITE_WS_URL` uses `wss://` (not `ws://`) for HTTPS deployments
- Render supports WebSockets natively — no extra config needed
- Check browser console for the actual error

---

## 7 · Update workflow

After deploy is set up, any `git push origin main` triggers:
- Render rebuilds the backend (~3 min)
- Vercel rebuilds the frontend (~1 min)

Both run automatically. Pull-request branches get preview URLs on Vercel.

---

## URLs cheatsheet

```
Production:
  Landing:   https://<your-vercel-app>.vercel.app
  Dashboard: https://<your-vercel-app>.vercel.app/dashboard
  Backend:   https://<your-render-service>.onrender.com
  API docs:  https://<your-render-service>.onrender.com/docs
```
