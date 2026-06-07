/**
 * Editorial Integrations page — like a "Directory of Connected Services"
 * appendix at the back of an operations manual.
 */
import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import {
  ArrowLeft, CheckCircle2, AlertTriangle, XCircle, Loader2,
} from "lucide-react";
import { CRMSourceBadge } from "@/components/CRMSourceBadge";

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
  hubspot:         "OAuth 2.0 · Properties API for auto-provisioning · Note + Task writeback",
  salesforce:      "OAuth 2.0 · package.xml delivery · SOQL-injection safe queries",
  zoho:            "OAuth 2.0 · India region by default · Contacts, Deals, Cases, Tasks",
  dynamics:        "Azure AD OAuth · OData v9 · sync_* custom fields · Annotation writeback",
  freshworks:      "API key · Contacts, Deals, Notes · cf_* custom fields",
  leadsquared:     "Access + Secret key · Dominant in Indian NBFC + banking · Real LSQ adapter",
  fake_leadsquared:"Sandbox — same code path as real LeadSquared, in-process MockTransport",
  mock:            "Legacy in-memory dataset — left in for back-compat",
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
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      {/* Top strip */}
      <div className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex h-8 max-w-[1100px] items-center justify-between px-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 md:px-6">
          <button
            onClick={() => navigate("/dashboard")}
            className="inline-flex items-center gap-1.5 hover:text-ink"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to the Briefing Desk
          </button>
          <span>§ Appendix A</span>
        </div>
      </div>

      <main className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-14">
        {/* Title */}
        <header className="border-b border-ink/15 pb-8">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            § Directory of Connected Services
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[0.95] text-ink md:text-6xl">
            CRM <em className="italic">Integrations</em>.
          </h1>
          <p className="mt-3 max-w-2xl font-serif text-lg italic leading-snug text-ink/70">
            Sync is a layer. Pick which Customer Relationship Management system it sits on top of —
            your bank's actual book of record stays where it is.
          </p>
        </header>

        {err && (
          <p className="mt-6 border border-red-700/40 bg-red-50 px-4 py-3 font-serif text-sm italic text-red-800">
            Error loading directory: {err}
          </p>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
          </div>
        )}

        {!loading && !err && (
          <>
            {/* Provider directory */}
            <section className="mt-10">
              <h2 className="border-t border-ink py-3 font-edit-mono text-[11px] uppercase tracking-widest text-ink/70">
                § A.1 · Available Adapters
              </h2>
              <div className="grid grid-cols-1 divide-y divide-ink/15 border-y border-ink/15 sm:grid-cols-2 sm:divide-y-0 sm:[&>*:nth-child(even)]:border-l sm:[&>*:nth-child(even)]:border-ink/15 sm:[&>*:nth-child(n+3)]:border-t sm:[&>*:nth-child(n+3)]:border-ink/15">
                {providers.map(prov => {
                  const conns = byProvider(prov.provider);
                  return (
                    <ProviderRow
                      key={prov.provider}
                      provider={prov}
                      connections={conns}
                      onConnect={() => handleConnect(prov)}
                    />
                  );
                })}
              </div>
            </section>

            {/* Active connections */}
            {connections.length > 0 && (
              <section className="mt-12">
                <h2 className="border-t border-ink py-3 font-edit-mono text-[11px] uppercase tracking-widest text-ink/70">
                  § A.2 · Active Connections
                </h2>
                <div className="border-y border-ink/15 divide-y divide-ink/15">
                  {connections.map(conn => (
                    <div key={conn.id} className="grid grid-cols-12 gap-4 px-1 py-4">
                      <div className="col-span-12 md:col-span-4">
                        <div className="flex items-center gap-2">
                          <CRMSourceBadge provider={conn.provider} />
                          {conn.is_default && (
                            <span className="border border-ink/30 bg-ink text-cream px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest">
                              Default
                            </span>
                          )}
                        </div>
                        <p className="mt-1 font-serif text-base text-ink">{conn.label}</p>
                      </div>
                      <div className="col-span-6 md:col-span-3 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
                        <p className="text-ink/40">Status</p>
                        <p className="mt-0.5 text-ink/80">{conn.status}</p>
                      </div>
                      <div className="col-span-6 md:col-span-3 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
                        <p className="text-ink/40">Last sync</p>
                        <p className="mt-0.5 text-ink/80">
                          {conn.last_sync_at
                            ? new Date(conn.last_sync_at).toLocaleString("en-IN")
                            : "Never"}
                        </p>
                      </div>
                      <div className="col-span-12 md:col-span-2 font-edit-mono text-[10px] uppercase tracking-widest">
                        {conn.provisioning_missing > 0 ? (
                          <span className="text-amber-800">⚠ {conn.provisioning_missing} fields missing</span>
                        ) : (
                          <span className="text-emerald-800">✓ Provisioned</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        <p className="mt-12 border-t border-ink/15 pt-6 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          Set provider OAuth credentials in .env · Restart backend to register them
        </p>
      </main>
    </div>
  );
}

function ProviderRow({
  provider, connections, onConnect,
}: {
  provider: Provider; connections: Connection[]; onConnect: () => void;
}) {
  const hasConn = connections.length > 0;
  const missing = connections.reduce((s, c) => s + c.provisioning_missing, 0);

  return (
    <div className="flex flex-col gap-3 px-4 py-5">
      {/* Top row */}
      <div className="flex items-start justify-between">
        <CRMSourceBadge provider={provider.provider} />
        <StatusIcon hasConn={hasConn} configured={provider.configured} missing={missing} />
      </div>

      {/* Body */}
      <div className="flex-1">
        <h3 className="font-display text-xl leading-tight text-ink">{provider.display_name}</h3>
        <p className="mt-2 font-serif text-sm italic leading-snug text-ink/70">
          {PROVIDER_DESC[provider.provider]}
        </p>
        {!provider.configured && provider.auth_method !== "none" && (
          <p className="mt-2 font-edit-mono text-[10px] uppercase tracking-widest text-amber-800">
            Credentials not configured
          </p>
        )}
        {hasConn && (
          <p className="mt-2 font-edit-mono text-[10px] uppercase tracking-widest text-emerald-800">
            {connections.length} active{missing > 0 && <span className="ml-1 text-amber-800">· {missing} missing</span>}
          </p>
        )}
      </div>

      {/* Action */}
      <div>
        {hasConn ? (
          <button
            disabled
            className="w-full border-2 border-ink/40 bg-paper px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60"
          >
            ✓ Connected
          </button>
        ) : (
          <button
            onClick={onConnect}
            disabled={provider.auth_method === "none"}
            className="w-full border-2 border-ink bg-ink px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            {provider.auth_method === "none" ? "Built-in" : `Connect via ${provider.auth_method}`}
          </button>
        )}
      </div>
    </div>
  );
}

function StatusIcon({ hasConn, configured, missing }: { hasConn: boolean; configured: boolean; missing: number; }) {
  if (hasConn && missing === 0) return <CheckCircle2 className="h-4 w-4 text-emerald-700" />;
  if (hasConn && missing > 0) return <AlertTriangle className="h-4 w-4 text-amber-700" />;
  if (!configured) return <XCircle className="h-4 w-4 text-ink/30" />;
  return <div className="h-4 w-4 rounded-full border-2 border-ink/30" />;
}
