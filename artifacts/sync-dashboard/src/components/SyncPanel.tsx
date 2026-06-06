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
  CheckCircle2, Loader2, PhoneCall, ShieldAlert, Sparkles, PanelRightOpen, Mic,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { ShimmerButton } from "./aceternity/shimmer-button";
import { GlowCard } from "./aceternity/glow-card";
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
  const { data: clients, isLoading } = useListClients();
  const [selectedClient, setSelectedClient] = useState("");
  const [rmPhone, setRmPhone] = useState(import.meta.env.VITE_DEMO_RM_PHONE ?? "+91 98765 43210");
  const [rmName, setRmName] = useState(import.meta.env.VITE_DEMO_RM_NAME ?? "Himanshu");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState("");
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

  return (
    <>
      <GlowCard glowColor="rgba(99,102,241,0.25)" className="p-5">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">Sync A Client</span>
              <CRMSourceBadge provider={provider} />
            </div>
            <p className="mt-1 text-xs text-slate-500">Trigger a Ringg briefing call to the RM.</p>
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
            <PhoneCall className="h-3.5 w-3.5 text-indigo-400" />
          </div>
        </div>

        <div className="space-y-3">
          {/* Client select */}
          <div className="space-y-1.5">
            <Label className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Client</Label>
            <Select value={selectedClient} onValueChange={setSelectedClient} disabled={isLoading || isPending}>
              <SelectTrigger className="h-10 border-white/[0.08] bg-white/[0.02] text-white placeholder:text-slate-600 focus:ring-1 focus:ring-indigo-500/50">
                <SelectValue placeholder={isLoading ? "Loading…" : "Select client…"} />
              </SelectTrigger>
              <SelectContent className="border-white/[0.08] bg-[#0d1117]">
                {clients?.map(c => (
                  <SelectItem key={c.client_id} value={c.client_id} className="text-slate-200 focus:bg-white/[0.06]">
                    <div className="flex items-center gap-2">
                      <RiskDot score={c.risk_score} />
                      <span>{scrub(c.name, "name")}</span>
                      <span className="text-[10px] text-slate-500">{c.company}</span>
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
            <Label className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">RM Name</Label>
            <Input value={rmName} onChange={e => setRmName(e.target.value)} disabled={isPending}
              className="h-10 border-white/[0.08] bg-white/[0.02] text-white placeholder:text-slate-600 focus-visible:ring-indigo-500/50" />
          </div>

          {/* RM Phone */}
          <div className="space-y-1.5">
            <Label className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">RM Phone</Label>
            <Input value={rmPhone} onChange={e => setRmPhone(e.target.value)} disabled={isPending}
              className="h-10 border-white/[0.08] bg-white/[0.02] font-mono text-white placeholder:text-slate-600 focus-visible:ring-indigo-500/50" />
          </div>

          {/* Sync button */}
          <ShimmerButton
            className={`mt-1 w-full text-sm font-semibold ${isSuccess && !isPending ? "opacity-80" : ""}`}
            onClick={handleSync}
            disabled={!selectedClient || !rmPhone || !rmName || isPending}
            background={isSuccess && !isPending
              ? "radial-gradient(ellipse 80% 50% at 50% 120%, #14532d, #0f172a)"
              : "radial-gradient(ellipse 80% 50% at 50% 120%, #1e1b4b, #0f172a)"
            }
            shimmerColor={isSuccess && !isPending ? "#10b981" : "#6366f1"}
          >
            {isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" />Calling…</>
              : isSuccess
                ? <><CheckCircle2 className="h-4 w-4 text-emerald-400" />Sync Delivered</>
                : <><PhoneCall className="h-4 w-4" />Sync Now</>
            }
          </ShimmerButton>

          {selectedClient && (
            <p className="text-center text-[10px] text-slate-600">
              <Mic className="mr-1 inline h-3 w-3" />
              Hold the mic in the header to log notes via voice
            </p>
          )}
        </div>
      </GlowCard>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="border-white/[0.08] bg-[#0d1117] sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle className="text-xs font-semibold uppercase tracking-widest text-slate-400">Briefing Preview</DialogTitle>
            <DialogDescription className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
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
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-white">{scrub(summary.name, "name")}</span>
            <RiskPill score={summary.risk_score} />
          </div>
          <p className="mt-0.5 truncate text-[11px] text-slate-500">{summary.occupation} · {summary.company}</p>
        </div>
        {onShowEmbed && (
          <button onClick={onShowEmbed} className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-slate-500 hover:bg-white/[0.06] hover:text-slate-300">
            <PanelRightOpen className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {profile && (
        <div className="mt-2 space-y-1.5">
          <InfoRow label="Portfolio" value={formatProduct(prod)} />
          <InfoRow label="Last contact" value={`${profile.last_rm_interaction_days_ago} days ago`} />
          <div className="flex items-start gap-2 rounded-md bg-white/[0.02] px-2.5 py-2 text-[11px]">
            {open ? <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" /> : <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" />}
            <span className="line-clamp-2 text-slate-400">{open ? `${open.category}: ${open.summary}` : (cs?.product ?? "No active complaint")}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
      <span className="text-slate-500">{label}</span>
      <span className="truncate font-medium text-slate-300">{value}</span>
    </div>
  );
}

function RiskDot({ score }: { score: string }) {
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${riskDotColor(score)}`} />;
}

function RiskPill({ score }: { score: string }) {
  const { bg, text } = riskPillColor(score);
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${bg} ${text}`}>{score.replace("_", " ")}</span>;
}

function riskDotColor(score: string) {
  const m: Record<string, string> = { very_low: "bg-emerald-500", low: "bg-blue-500", medium: "bg-amber-500", watch: "bg-orange-500", high: "bg-red-500" };
  return m[score] ?? "bg-slate-500";
}

function riskPillColor(score: string): { bg: string; text: string } {
  const m: Record<string, { bg: string; text: string }> = {
    very_low: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
    low:      { bg: "bg-blue-500/15",    text: "text-blue-400" },
    medium:   { bg: "bg-amber-500/15",   text: "text-amber-400" },
    watch:    { bg: "bg-orange-500/15",  text: "text-orange-400" },
    high:     { bg: "bg-red-500/15",     text: "text-red-400" },
  };
  return m[score] ?? { bg: "bg-slate-500/15", text: "text-slate-400" };
}

function formatProduct(p?: LoanProduct) {
  if (!p) return "No active product";
  const amt = p.principal >= 100000 ? `₹${Math.round(p.principal / 100000)}L` : `₹${p.principal.toLocaleString("en-IN")}`;
  const emi = p.emi ? `, EMI ₹${p.emi.toLocaleString("en-IN")}` : "";
  return `${p.product_type.replaceAll("_", " ")} ${amt}${emi}`;
}
