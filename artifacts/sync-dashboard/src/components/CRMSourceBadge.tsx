/**
 * CRMSourceBadge — small coloured badge showing which CRM a client comes from.
 * Provider colour palette matches the real brand colours.
 */
import { cn } from "@/lib/utils";

const PROVIDER_META: Record<string, { label: string; bg: string; text: string }> = {
  hubspot:         { label: "HubSpot",      bg: "bg-orange-100 dark:bg-orange-500/15",  text: "text-orange-700 dark:text-orange-300" },
  salesforce:      { label: "Salesforce",   bg: "bg-blue-100 dark:bg-blue-500/15",      text: "text-blue-700 dark:text-blue-300" },
  zoho:            { label: "Zoho",         bg: "bg-red-100 dark:bg-red-500/15",        text: "text-red-700 dark:text-red-300" },
  dynamics:        { label: "Dynamics",     bg: "bg-indigo-100 dark:bg-indigo-500/15",  text: "text-indigo-700 dark:text-indigo-300" },
  freshworks:      { label: "Freshworks",   bg: "bg-green-100 dark:bg-green-500/15",    text: "text-green-700 dark:text-green-300" },
  leadsquared:     { label: "LeadSquared",  bg: "bg-purple-100 dark:bg-purple-500/15",  text: "text-purple-700 dark:text-purple-300" },
  fake_leadsquared:{ label: "LSQ Sandbox",  bg: "bg-slate-100 dark:bg-slate-500/15",    text: "text-slate-600 dark:text-slate-400" },
  mock:            { label: "Demo",         bg: "bg-slate-100 dark:bg-slate-500/15",    text: "text-slate-500 dark:text-slate-400" },
};

export function CRMSourceBadge({ provider, className }: { provider: string; className?: string }) {
  const meta = PROVIDER_META[provider] ?? { label: provider, bg: "bg-muted", text: "text-muted-foreground" };
  return (
    <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", meta.bg, meta.text, className)}>
      {meta.label}
    </span>
  );
}

export function providerFromConnectionId(connectionId: string): string {
  // Heuristic from the id prefix — override with real provider data when available.
  for (const key of Object.keys(PROVIDER_META)) {
    if (connectionId.includes(key)) return key;
  }
  return "mock";
}
