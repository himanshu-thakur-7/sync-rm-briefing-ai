# Ringg AI Setup Guide for SYNC

## Prerequisites
- Ringg AI account and workspace API key
- A provisioned phone number in Ringg dashboard

## Step 1: Get your API key
1. Log in to https://prod-api.ringg.ai
2. Go to Settings → API Keys
3. Copy your workspace API key

## Step 2: Set environment variables
Add to your `.env` file:
```bash
RINGG_API_KEY=your_key_here
RINGG_BASE_URL=https://prod-api.ringg.ai/ca/api/v0
```

## Step 3: Create the SYNC agent
Run the setup script:
```bash
RINGG_API_KEY=xxx python scripts/setup_ringg_agent.py
```

This will:
1. List available en-IN voices and pick the best one
2. Create the SYNC agent with the full system prompt
3. Print your AGENT_ID — add it to .env as RINGG_AGENT_ID

## Step 4: Get your phone number ID
In the Ringg dashboard, go to Phone Numbers and copy the ID of your provisioned number.
Add to .env:
```bash
RINGG_FROM_NUMBER_ID=your_number_id
```

## Step 5: Upload the knowledge base (for inbound calls)
```bash
RINGG_API_KEY=xxx python scripts/upload_knowledge_base.py
```

This uploads all 5 client profiles so the agent can answer inbound calls
where the RM says "I'm about to meet Rahul Mehta".

## Step 6: Test with an outbound call
```bash
RINGG_API_KEY=xxx python scripts/test_call.py --client "Rahul Mehta" --phone "+919876543210"
```

## Step 7: Configure webhook (for dashboard live feed)
The backend automatically registers the webhook URL when you call /api/v1/calls/sync-now.
Make sure BACKEND_URL is set to your public HTTPS URL (Ringg requires HTTPS).

## Inbound call setup
1. In Ringg dashboard, assign the SYNC agent to your inbound number
2. When RM calls the number, agent greets and asks for client name
3. Agent looks up from knowledge base and delivers briefing

## Outbound call setup (dashboard mode)
1. RM opens dashboard at your FRONTEND_URL
2. Selects client from dropdown
3. Types their phone number
4. Clicks "Sync Now"
5. Backend generates briefing, calls Ringg API, Ringg calls RM's phone
6. RM receives briefing before walking into meeting
