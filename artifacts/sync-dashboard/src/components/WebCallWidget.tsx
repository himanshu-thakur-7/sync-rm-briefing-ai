/**
 * WebCallWidget — Ringg's browser-call widget, embedded in the dashboard.
 *
 * This is the inbound story WITHOUT buying a phone number: anyone (read:
 * buildathon mentors) opens the dashboard and talks to the Concierge agent
 * from the browser. The widget injects its own floating call button.
 *
 * Lights up only when both env vars are set on Vercel:
 *   VITE_RINGG_WIDGET_AGENT_ID  — the agent to load (Concierge)
 *   VITE_RINGG_WIDGET_KEY       — widget API key from Ringg's embed page
 *
 * Remember: the dashboard domain must be in the agent's Whitelist Domains
 * (Ringg → agent → WebCall settings, or the edit_agent_whitelisted_domains
 * API operation).
 */
import { useEffect } from "react";

declare global {
  interface Window {
    loadAgent?: (cfg: Record<string, unknown>) => void;
    __ringgWidgetLoaded?: boolean;
  }
}

// Pin to the version Ringg's embed page hands out — avoids surprise CDN bumps.
const VERSION = "1.0.21-alpha.11";
const CDN = `https://cdn.jsdelivr.net/npm/@desivocal/agents-cdn@${VERSION}/dist`;

export function WebCallWidget() {
  useEffect(() => {
    const agentId = import.meta.env.VITE_RINGG_WIDGET_AGENT_ID;
    const xApiKey = import.meta.env.VITE_RINGG_WIDGET_KEY;

    // Surface what's happening — open devtools console once to confirm.
    // (Build inlines env vars at build time, so missing here = env not set on
    //  Vercel at last build, or build wasn't redeployed after setting them.)
    if (!agentId || !xApiKey) {
      console.warn(
        "[SYNC] Ringg web-call widget not loaded — env vars missing.",
        { hasAgentId: !!agentId, hasKey: !!xApiKey },
      );
      return;
    }
    if (window.__ringgWidgetLoaded) return;
    window.__ringgWidgetLoaded = true;
    console.info("[SYNC] Loading Ringg web-call widget", { agentId, version: VERSION });

    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.type = "text/css";
    stylesheet.href = `${CDN}/style.css`;

    const script = document.createElement("script");
    script.type = "module";
    script.src = `${CDN}/dv-agent.es.js`;
    script.onload = () => {
      if (typeof window.loadAgent !== "function") {
        console.error("[SYNC] loadAgent missing on the CDN bundle — version mismatch?");
        return;
      }
      window.loadAgent({
        agentId,
        xApiKey,
        defaultTab: "audio",
        hideTabSelector: true,
        title: "Call SYNC",
        description: "Talk to your CRM — briefings, tasks, meetings, by voice.",
        variables: {
          company_name: "Acme",
          rm_name: "Himanshu",
        },
        buttons: {},
      });
      console.info("[SYNC] Ringg widget loaded — look bottom-right for the floating call button.");
    };
    script.onerror = (e) => console.error("[SYNC] Ringg CDN script failed to load", e);

    document.head.appendChild(stylesheet);
    document.head.appendChild(script);
  }, []);

  return null; // the CDN injects its own floating UI
}
