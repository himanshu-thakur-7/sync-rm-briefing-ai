import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { ArrowLeft, CheckCircle2, AlertTriangle, XCircle, Plug, Settings2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CRMSourceBadge } from "@/components/CRMSourceBadge";
import { GlowCard } from "@/components/aceternity/glow-card";
import { BackgroundBeams } from "@/components/aceternity/background-beams";
import { GridPattern } from "@/components/aceternity/grid-pattern";

interface Connection {
  id: string; provider: string; label: string; status: string;
  auth_method: string; is_default: boolean;
  last_sync_at: string | null; provisioning_missing: number;
}

interface Provider {
  provider: string; display_name: string; auth_method: string; configured: boolean;
}

const PROVIDER_ORDER = [
  "fake_leadsquared", "hubspot", "salesforce", "zoho",
  "dynamics", "freshworks", "leadsquared", "mock",
];

const PROVIDER_DESC: Record<string, string> = {
  hubspot:         "OAuth 2.0 · Most popular for SMB banks",
  salesforce:      "OAuth 2.0 · Enterprise gold standard",
  zoho:            "OAuth 2.0 · Strong in Indian SMB segment",
  dynamics:        "Azure AD OAuth · Microsoft enterprise stack",
  freshworks:      "API key · Lightweight, growing fast",
  leadsquared:     "API key · #1 in Indian NBFC/banking",
  fake_leadsquared:"Sandbox · Same code as real LeadSquared",
  mock:            "Built-in · Legacy in-memory dataset",
};

export default function IntegrationsIndex() {
  const [, navigate] = useLocation();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/v1/integrations").then(r => { if (!r.ok) throw new Error("integrations failed"); return r.json(); }),
      fetch("/api/v1/oauth/providers").then(r => { if (!r.ok) throw new Error("providers failed"); return r.json(); }),
    ])
      .then(([conns, provs]) => {
        setConnections(conns);
        setProviders(provs.sort((a: Provider, b: Provider) =>
          PROVIDER_ORDER.indexOf(a.provider) - PROVIDER_ORDER.indexOf(b.provider)
        ));
      })
      .catch(e => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const byProvider = (p: string) => connections.filter(c => c.provider === p);

  const handleConnect = (prov: Provider) => {
    if (!prov.configured) {
      alert(`Set ${prov.provider.toUpperCase()}_CLIENT_ID and _CLIENT_SECRET in .env, then restart backend.`);
      return;
    }
    if (prov.auth_method === "oauth2") {
      window.location.href = `/api/v1/oauth/${prov.provider}/authorize?label=${encodeURIComponent(prov.display_name)}`;
    }
  };

  return (
    <div className="relative min-h-screen bg-[#020817] text-white">
      <GridPattern />
      <BackgroundBeams />
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-indigo-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl space-y-6 p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon"
            className="h-9 w-9 border border-white/[0.06] bg-white/[0.03] text-slate-400 hover:bg-white/[0.06] hover:text-white"
            onClick={() => navigate("/")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-indigo-400/70">Settings</p>
            <h1 className="text-2xl font-bold tracking-tight text-white">CRM Integrations</h1>
            <p className="mt-1 text-sm text-slate-500">
              Connect your bank's CRM — SYNC becomes the voice layer on top of it.
            </p>
          </div>
        </div>

        {err && (
          <GlowCard className="p-4">
            <p className="text-sm text-red-400">Error loading integrations: {err}</p>
          </GlowCard>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-slate-600" />
          </div>
        )}

        {!loading && !err && (
          <>
            {/* Provider grid */}
            <div>
              <h2 className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Available Providers
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {providers.map(prov => {
                  const conns = byProvider(prov.provider);
                  return (
                    <ProviderCard
                      key={prov.provider}
                      provider={prov}
                      connections={conns}
                      onConnect={() => handleConnect(prov)}
                      onManage={(id) => navigate(`/settings/integrations`)}
                    />
                  );
                })}
              </div>
            </div>

            {/* Connected list */}
            {connections.length > 0 && (
              <div>
                <h2 className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  Active Connections
                </h2>
                <div className="space-y-2">
                  {connections.map(conn => (
                    <GlowCard key={conn.id} className="p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <CRMSourceBadge provider={conn.provider} />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white">{conn.label}</span>
                              {conn.is_default && (
                                <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase text-indigo-400">
                                  Default
                                </span>
                              )}
                            </div>
                            <div className="mt-0.5 text-[11px] text-slate-600">
                              {conn.last_sync_at
                                ? `Last sync ${new Date(conn.last_sync_at).toLocaleString("en-IN")}`
                                : "Never synced"}
                              {conn.provisioning_missing > 0 && (
                                <span className="ml-2 text-amber-400">⚠ {conn.provisioning_missing} missing</span>
                              )}
                            </div>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm"
                          className="border border-white/[0.06] bg-white/[0.02] text-slate-300 hover:bg-white/[0.06] hover:text-white"
                          onClick={() => navigate(`/settings/integrations`)}>
                          <Settings2 className="mr-1.5 h-3 w-3" />Manage
                        </Button>
                      </div>
                    </GlowCard>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ProviderCard({ provider, connections, onConnect, onManage }: {
  provider: Provider; connections: Connection[];
  onConnect: () => void; onManage: (id: string) => void;
}) {
  const hasConn = connections.length > 0;
  const missing = connections.reduce((s, c) => s + c.provisioning_missing, 0);

  return (
    <GlowCard className="flex flex-col gap-3 p-5" glowColor={hasConn ? "rgba(16,185,129,0.2)" : "rgba(99,102,241,0.15)"}>
      <div className="flex items-start justify-between">
        <CRMSourceBadge provider={provider.provider} />
        <StatusIcon hasConn={hasConn} configured={provider.configured} missing={missing} />
      </div>

      <div className="flex-1">
        <h3 className="font-semibold text-white">{provider.display_name}</h3>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{PROVIDER_DESC[provider.provider]}</p>
        {!provider.configured && provider.auth_method !== "none" && (
          <p className="mt-1.5 text-[10px] text-amber-400/70">Credentials not configured</p>
        )}
        {hasConn && (
          <p className="mt-1.5 text-[10px] text-emerald-400/80">
            {connections.length} active{missing > 0 && <span className="ml-1 text-amber-400/80">· {missing} fields missing</span>}
          </p>
        )}
      </div>

      <div className="mt-auto">
        {hasConn ? (
          <Button variant="ghost" size="sm" className="w-full border border-white/[0.06] bg-white/[0.02] text-xs text-slate-300 hover:bg-white/[0.06] hover:text-white"
            onClick={() => onManage(connections[0].id)}>
            Manage
          </Button>
        ) : (
          <Button
            size="sm"
            className="w-full bg-indigo-600/90 text-xs hover:bg-indigo-600"
            onClick={onConnect}
            disabled={provider.auth_method === "none"}
          >
            <Plug className="mr-1.5 h-3 w-3" />
            {provider.auth_method === "none" ? "Built-in" : "Connect"}
          </Button>
        )}
      </div>
    </GlowCard>
  );
}

function StatusIcon({ hasConn, configured, missing }: { hasConn: boolean; configured: boolean; missing: number; }) {
  if (hasConn && missing === 0) return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  if (hasConn && missing > 0) return <AlertTriangle className="h-4 w-4 text-amber-400" />;
  if (!configured) return <XCircle className="h-4 w-4 text-slate-700" />;
  return <div className="h-4 w-4 rounded-full border-2 border-slate-700" />;
}
