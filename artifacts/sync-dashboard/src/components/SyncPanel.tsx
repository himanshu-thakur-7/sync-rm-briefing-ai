/**
 * Editorial Sync Panel — feels like a form filed on official stationery.
 * Section header in serif, mono labels, ruled inputs, ink-black CTA.
 */
import { useEffect, useState } from "react";
import {
  ClientFullProfile, ClientProfile, LoanProduct,
  useGetClient, useListClients,
} from "@workspace/api-client-react";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ShieldAlert, Sparkles, PanelRightOpen } from "lucide-react";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { useConnection } from "@/lib/connection-context";
import { usePii } from "@/lib/pii-context";

interface Props {
  onClientSelect?: (clientId: string) => void;
  onShowEmbed?: () => void;
  activeClientId?: string;
}

export function SyncPanel({ onClientSelect, onShowEmbed }: Props) {
  const { connectionId } = useConnection();
  const { scrub } = usePii();
  const { data: clients, isLoading } = useListClients();
  const [selectedClient, setSelectedClient] = useState("");
  const selectedSummary = clients?.find(c => c.client_id === selectedClient);
  const { data: selectedProfile } = useGetClient(selectedClient);

  useEffect(() => { if (selectedClient) onClientSelect?.(selectedClient); }, [selectedClient]);

  const provider = providerFromConnectionId(connectionId);

  return (
    <>
      <section className="border border-ink/15 bg-paper">
        {/* Section header */}
        <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
          <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            <span className="text-ink/40">§</span>
            <span>02</span>
            <span className="text-ink/30">·</span>
            <span>Browse Clients · Open CRM</span>
          </div>
          <CRMSourceBadge provider={provider} />
        </div>

        <div className="space-y-4 p-5">
          {/* Client select */}
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
              Client
            </Label>
            <Select value={selectedClient} onValueChange={setSelectedClient} disabled={isLoading}>
              <SelectTrigger className="h-10 rounded-none border border-ink/30 bg-paper font-serif text-ink shadow-none focus:border-ink focus:ring-0">
                <SelectValue placeholder={isLoading ? "Loading…" : "Select client…"} />
              </SelectTrigger>
              <SelectContent className="rounded-none border-ink/30 bg-paper">
                {clients?.map(c => (
                  <SelectItem key={c.client_id} value={c.client_id} className="font-serif text-ink focus:bg-ink/[0.05]">
                    <div className="flex items-center gap-2">
                      <RiskDot score={c.risk_score} />
                      <span>{scrub(c.name, "name")}</span>
                      <span className="font-edit-mono text-[10px] text-ink/50">· {c.company}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Client preview */}
          {selectedSummary && (
            <ClientPreview summary={selectedSummary} profile={selectedProfile} onShowEmbed={onShowEmbed} />
          )}

          {selectedClient && (
            <p className="border-t border-ink/15 pt-3 text-center font-serif text-[11px] italic text-ink/50">
              Use the web-call widget to connect — say the client's name to begin.
            </p>
          )}
        </div>
      </section>
    </>
  );
}

function ClientPreview({ summary, profile, onShowEmbed }: { summary: ClientProfile; profile?: ClientFullProfile; onShowEmbed?: () => void; }) {
  const { scrub } = usePii();
  const open = profile?.complaints.find(c => c.status === "open" || c.status === "escalated");
  const prod = profile?.products[0];
  const cs = profile?.cross_sell[0];

  return (
    <div className="border border-ink/15 bg-ink/[0.015] p-3">
      <div className="flex items-start justify-between gap-2 border-b border-ink/10 pb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate font-serif text-base font-semibold text-ink">
              {scrub(summary.name, "name")}
            </span>
            <RiskPill score={summary.risk_score} />
          </div>
          <p className="mt-0.5 truncate font-edit-mono text-[10px] text-ink/50">
            {summary.occupation} · {summary.company}
          </p>
        </div>
        {onShowEmbed && (
          <button
            onClick={onShowEmbed}
            className="flex h-7 w-7 shrink-0 items-center justify-center border border-ink/20 text-ink/60 hover:bg-ink hover:text-paper"
            title="Open CRM contact view"
          >
            <PanelRightOpen className="h-3 w-3" />
          </button>
        )}
      </div>
      {profile && (
        <div className="mt-2 space-y-0.5">
          <InfoRow label="Portfolio" value={formatProduct(prod)} />
          <InfoRow label="Last contact" value={`${profile.last_rm_interaction_days_ago} days ago`} />
          <div className="flex items-start gap-2 border-t border-ink/10 pt-2 mt-1.5 text-[11px]">
            {open ? (
              <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-700" />
            ) : (
              <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" />
            )}
            <span className="line-clamp-2 font-serif italic text-ink/70">
              {open ? `${open.category}: ${open.summary}` : (cs?.product ?? "No active complaint")}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 font-edit-mono text-[10px]">
      <span className="uppercase tracking-widest text-ink/40">{label}</span>
      <span className="truncate text-right text-ink/80">{value}</span>
    </div>
  );
}

function RiskDot({ score }: { score: string }) {
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${riskDotColor(score)}`} />;
}

function RiskPill({ score }: { score: string }) {
  const { bg, text } = riskPillColor(score);
  return (
    <span className={`border px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest ${bg} ${text}`}>
      {score.replace("_", " ")}
    </span>
  );
}

function riskDotColor(score: string) {
  const m: Record<string, string> = {
    very_low: "bg-emerald-700", low: "bg-blue-700",
    medium: "bg-amber-600", watch: "bg-orange-700", high: "bg-red-700",
  };
  return m[score] ?? "bg-ink/40";
}

function riskPillColor(score: string): { bg: string; text: string } {
  const m: Record<string, { bg: string; text: string }> = {
    very_low: { bg: "border-emerald-700/40 bg-emerald-50", text: "text-emerald-800" },
    low:      { bg: "border-blue-700/40 bg-blue-50",       text: "text-blue-800" },
    medium:   { bg: "border-amber-600/40 bg-amber-50",     text: "text-amber-800" },
    watch:    { bg: "border-orange-700/40 bg-orange-50",   text: "text-orange-800" },
    high:     { bg: "border-red-700/40 bg-red-50",         text: "text-red-800" },
  };
  return m[score] ?? { bg: "border-ink/30 bg-ink/[0.02]", text: "text-ink/70" };
}

function formatProduct(p?: LoanProduct) {
  if (!p) return "No active product";
  const amt = p.principal >= 100000 ? `₹${Math.round(p.principal / 100000)}L` : `₹${p.principal.toLocaleString("en-IN")}`;
  const emi = p.emi ? `, EMI ₹${p.emi.toLocaleString("en-IN")}` : "";
  return `${p.product_type.replaceAll("_", " ")} ${amt}${emi}`;
}
