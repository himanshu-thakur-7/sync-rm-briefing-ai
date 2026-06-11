/**
 * Editorial Sync Panel — feels like a form filed on official stationery.
 * Section header in serif, mono labels, ruled inputs, ink-black CTA.
 */
import { useEffect, useState } from "react";
import {
  ClientFullProfile, ClientProfile, LoanProduct,
  useGetClient, useListClients, useSyncNow,
} from "@workspace/api-client-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  CheckCircle2, Loader2, ArrowRight, ShieldAlert, Sparkles, PanelRightOpen, Mic, Headphones,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { useConnection } from "@/lib/connection-context";
import { usePii } from "@/lib/pii-context";

interface Props {
  onClientSelect?: (clientId: string) => void;
  onRmNameChange?: (name: string) => void;
  onShowEmbed?: () => void;
  activeClientId?: string;
}

export function SyncPanel({ onClientSelect, onRmNameChange, onShowEmbed }: Props) {
  const { connectionId } = useConnection();
  const { scrub } = usePii();
  const { toast } = useToast();
  const { data: clients, isLoading } = useListClients();
  const [selectedClient, setSelectedClient] = useState("");
  const [rmPhone, setRmPhone] = useState(import.meta.env.VITE_DEMO_RM_PHONE ?? "+91 98765 43210");
  const [rmName, setRmName] = useState(import.meta.env.VITE_DEMO_RM_NAME ?? "Himanshu");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState("");
  const [coachedPending, setCoachedPending] = useState(false);
  const syncMutation = useSyncNow();
  const selectedSummary = clients?.find(c => c.client_id === selectedClient);
  const { data: selectedProfile } = useGetClient(selectedClient);

  useEffect(() => { if (selectedClient) onClientSelect?.(selectedClient); }, [selectedClient]);
  useEffect(() => { onRmNameChange?.(rmName); }, [rmName]);

  const handleSync = () => {
    if (!selectedClient || !rmPhone || !rmName) return;
    syncMutation.mutate(
      { data: { client_id: selectedClient, rm_phone: rmPhone, rm_name: rmName } },
      { onSuccess: d => { setPreviewText(d.briefing_preview); setPreviewOpen(true); } }
    );
  };

  const isPending = syncMutation.isPending;
  const isSuccess = syncMutation.isSuccess;
  const provider = providerFromConnectionId(connectionId);

  // Coached Call — a real RM ↔ client phone call with SYNC listening live
  // (Twilio bridge when configured, Ringg silent-chaperone otherwise) and
  // whisper coaching firing on the dashboard / earbud.
  const handleCoachedCall = async () => {
    if (!selectedClient || !rmPhone) return;
    setCoachedPending(true);
    try {
      const r = await fetch("/api/v1/coached-calls/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: selectedClient,
          client_name: selectedSummary?.name ?? "the client",
          rm_phone: rmPhone.replace(/\s/g, ""),
          rm_name: rmName,
          connection_id: connectionId,
          route: "auto",
        }),
      });
      if (!r.ok) {
        const detail = await r.text();
        throw new Error(`HTTP ${r.status}: ${detail.slice(0, 160)}`);
      }
      const d = await r.json();
      toast({
        title: d.route === "twilio" ? "Coached call — your phone is ringing" : "Coached call via SYNC line",
        description: `${d.message} Turn on Whisper Mode (🎧 in the masthead) to hear tips in your ear.`,
      });
    } catch (e: any) {
      toast({ title: "Coached call failed", description: e?.message ?? String(e), variant: "destructive" });
    } finally {
      setCoachedPending(false);
    }
  };

  return (
    <>
      <section className="border border-ink/15 bg-paper">
        {/* Section header */}
        <div className="flex items-baseline justify-between border-b border-ink/15 bg-ink/[0.02] px-4 py-2.5">
          <div className="flex items-baseline gap-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            <span className="text-ink/40">§</span>
            <span>02</span>
            <span className="text-ink/30">·</span>
            <span>Brief A Client</span>
          </div>
          <CRMSourceBadge provider={provider} />
        </div>

        <div className="space-y-4 p-5">
          {/* Client select */}
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
              Client
            </Label>
            <Select value={selectedClient} onValueChange={setSelectedClient} disabled={isLoading || isPending}>
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

          {/* RM Name */}
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
              RM Name
            </Label>
            <Input
              value={rmName}
              onChange={e => setRmName(e.target.value)}
              disabled={isPending}
              className="h-10 rounded-none border border-ink/30 bg-paper font-serif text-ink shadow-none focus-visible:border-ink focus-visible:ring-0"
            />
          </div>

          {/* RM Phone */}
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">
              RM Phone
            </Label>
            <Input
              value={rmPhone}
              onChange={e => setRmPhone(e.target.value)}
              disabled={isPending}
              className="h-10 rounded-none border border-ink/30 bg-paper font-edit-mono text-ink shadow-none focus-visible:border-ink focus-visible:ring-0"
            />
          </div>

          {/* Submit */}
          <button
            onClick={handleSync}
            disabled={!selectedClient || !rmPhone || !rmName || isPending}
            className={`group mt-2 inline-flex w-full items-center justify-center gap-2 border-2 px-5 py-3 font-edit-mono text-[11px] uppercase tracking-widest transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
              isSuccess && !isPending
                ? "border-emerald-800 bg-emerald-800 text-paper hover:bg-paper hover:text-emerald-800"
                : "border-ink bg-ink text-cream hover:bg-paper hover:text-ink"
            }`}
          >
            {isPending ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" />Calling…</>
            ) : isSuccess ? (
              <><CheckCircle2 className="h-3.5 w-3.5" />Sync Delivered</>
            ) : (
              <>Initiate Briefing Call<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" /></>
            )}
          </button>

          {/* Coached Call — live human↔human call with SYNC whispering */}
          <button
            onClick={handleCoachedCall}
            disabled={!selectedClient || !rmPhone || coachedPending}
            className="inline-flex w-full items-center justify-center gap-2 border-2 border-ink/40 bg-paper px-5 py-2.5 font-edit-mono text-[10px] uppercase tracking-widest text-ink/80 transition-colors hover:border-ink hover:bg-ink hover:text-cream disabled:cursor-not-allowed disabled:opacity-50"
            title="SYNC bridges you and the client on a real call, listens live, and whispers coaching"
          >
            {coachedPending
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Placing call…</>
              : <><Headphones className="h-3.5 w-3.5" />Coached Call · SYNC listens live</>}
          </button>

          {selectedClient && (
            <p className="border-t border-ink/15 pt-3 text-center font-serif text-[11px] italic text-ink/50">
              <Mic className="mr-1 inline h-3 w-3" />
              Hold the microphone in the masthead to dictate a CRM action
            </p>
          )}
        </div>
      </section>

      {/* Briefing preview */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="rounded-none border-ink bg-paper sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
              § Briefing Preview
            </DialogTitle>
            <DialogDescription className="mt-3 whitespace-pre-wrap border-l-2 border-ink pl-4 font-serif text-base italic leading-relaxed text-ink/90">
              {previewText}
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
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
