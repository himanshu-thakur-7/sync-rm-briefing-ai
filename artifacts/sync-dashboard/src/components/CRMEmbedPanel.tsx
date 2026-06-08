/**
 * CRMEmbedPanel — renders the native CRM contact view in a sandboxed iframe.
 * Editorial chrome around it. Uses relative URLs for Vite proxy.
 */
import { useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, RefreshCw, X } from "lucide-react";
import { CRMSourceBadge } from "./CRMSourceBadge";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";

interface EmbedSpec {
  url: string; provider: string; label: string;
  sandbox_attrs: string; may_block_frame: boolean;
  external_url?: string | null;
}

interface Props {
  connectionId: string;
  clientId: string;
  provider: string;
  onClose?: () => void;
}

export function CRMEmbedPanel({ connectionId, clientId, provider, onClose }: Props) {
  const [spec, setSpec] = useState<EmbedSpec | null>(null);
  const [loading, setLoading] = useState(true);
  // Bump this counter to force the iframe to reload (e.g. after a voice
  // command logged a note / created a task in the live CRM).
  const [refreshKey, setRefreshKey] = useState(0);
  const [justRefreshed, setJustRefreshed] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!connectionId || !clientId) return;
    setLoading(true); setSpec(null);

    const isSandbox = connectionId.includes("lsq_sandbox") || connectionId.includes("mock");
    const url = isSandbox
      ? `/api/v1/embeds/sandbox/contact/${clientId}`
      : `/api/v1/embeds/${connectionId}/contact/${clientId}`;

    fetch(url, { headers: { "Accept": "application/json" } })
      .then(async r => {
        const ct = r.headers.get("content-type") || "";
        if (ct.includes("application/json")) return r.json() as Promise<EmbedSpec>;
        return {
          url, provider, label: "LeadSquared (Sandbox)",
          sandbox_attrs: "allow-scripts allow-same-origin", may_block_frame: false,
        } as EmbedSpec;
      })
      .then(data => {
        setSpec({
          ...data,
          url: data.url.startsWith("http") ? data.url : (data.url.startsWith("/") ? data.url : `/${data.url}`),
        });
        setLoading(false);
      })
      .catch(() => {
        setSpec({
          url: `/api/v1/embeds/sandbox/contact/${clientId}`,
          provider, label: provider,
          sandbox_attrs: "allow-scripts allow-same-origin", may_block_frame: false,
        });
        setLoading(false);
      });
  }, [connectionId, clientId, provider]);

  // Live-refresh: when a voice-driven CRM action lands for THIS client
  // (note logged / task created / complaint updated etc.), bump the iframe
  // src cache-buster so the panel re-fetches and renders the new state.
  useWebSocket({
    onMessage: (msg: WebSocketMessage) => {
      const REFRESH_EVENTS = new Set([
        "command_executed",
        "concierge_action_executed",
        "morning_brief_action_executed",
        "connection_synced",
      ]);
      if (!REFRESH_EVENTS.has(msg.type)) return;
      // Refresh if the event mentions this client OR if it's a broad
      // connection-level sync (then we re-pull regardless).
      const eventClientId = msg.data?.client_id;
      if (eventClientId && eventClientId !== clientId) return;
      setRefreshKey(k => k + 1);
      setJustRefreshed(true);
      setTimeout(() => setJustRefreshed(false), 1800);
    },
  });

  const manualRefresh = () => {
    setRefreshKey(k => k + 1);
    setJustRefreshed(true);
    setTimeout(() => setJustRefreshed(false), 1200);
  };

  // Append refreshKey as cache-buster so iframe actually re-fetches.
  const iframeSrc = spec
    ? spec.url + (spec.url.includes("?") ? "&" : "?") + `_=${refreshKey}`
    : "";

  return (
    <div className="flex h-full flex-col">
      {/* Sub-header with provider */}
      <div className="flex items-center justify-between gap-2 border-b border-ink/15 bg-ink/[0.01] px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <CRMSourceBadge provider={spec?.provider ?? provider} />
          <span className="truncate font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            Contact ID · {clientId}
          </span>
          {justRefreshed && (
            <span className="inline-flex items-center gap-1 border border-emerald-700/40 bg-emerald-50 px-1.5 py-0.5 font-edit-mono text-[9px] font-bold uppercase tracking-widest text-emerald-800">
              ● Live
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {spec && (spec.external_url || (!spec.may_block_frame && spec.url.startsWith("http"))) && (
            <a
              href={spec.external_url ?? spec.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 border border-ink/30 bg-paper px-2 py-1 font-edit-mono text-[10px] font-semibold uppercase tracking-widest text-ink/80 hover:bg-ink hover:text-paper"
              title={`Open in ${spec.label}`}
            >
              Open in {spec.label}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            onClick={manualRefresh}
            title="Refresh contact data"
            className="flex h-6 w-6 items-center justify-center border border-ink/30 text-ink/60 hover:bg-ink hover:text-paper"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              title="Close panel"
              className="flex h-6 w-6 items-center justify-center border border-ink/30 text-ink/60 hover:bg-ink hover:text-paper"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      <div className="relative flex-1 bg-paper">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
          </div>
        )}

        {/* Backend always returns a SYNC-hosted iframe-friendly URL now — for
            providers whose real web app blocks framing, we render their data
            through our own native view. may_block_frame should only ever be
            true for unknown/unhandled providers. */}
        {spec && spec.may_block_frame && (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <CRMSourceBadge provider={spec.provider} />
            <p className="font-serif text-sm italic text-ink/60">
              No embed view configured for {spec.label} yet.
            </p>
            {spec.external_url && (
              <a href={spec.external_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 border-2 border-ink bg-paper px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink hover:bg-ink hover:text-cream">
                <ExternalLink className="h-3 w-3" />
                Open in {spec.label}
              </a>
            )}
          </div>
        )}

        {spec && !spec.may_block_frame && (
          <iframe
            ref={iframeRef}
            key={`${spec.url}-${refreshKey}`}
            src={iframeSrc}
            sandbox={spec.sandbox_attrs}
            className="h-full w-full border-0"
            title={`${spec.label} Contact View`}
          />
        )}
      </div>
    </div>
  );
}

export function CRMEmbedRail({ connections, clientId, defaultProvider, onClose }: {
  connections: Array<{ id: string; provider: string; label: string }>;
  clientId: string;
  defaultProvider: string;
  onClose: () => void;
}) {
  const [idx, setIdx] = useState(0);
  const active = connections[idx];
  if (!active) return null;

  return (
    <div className="flex h-full flex-col">
      {connections.length > 1 && (
        <div className="flex gap-1 border-b border-ink/15 px-2 pt-2">
          {connections.map((c, i) => (
            <button key={c.id} onClick={() => setIdx(i)}
              className={`px-3 py-1.5 font-edit-mono text-[10px] uppercase tracking-widest transition-colors ${
                i === idx ? "border-x border-t border-ink bg-paper text-ink" : "text-ink/50 hover:text-ink"
              }`}>
              <CRMSourceBadge provider={c.provider} />
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        <CRMEmbedPanel
          connectionId={active.id}
          clientId={clientId}
          provider={active.provider}
          onClose={onClose}
        />
      </div>
    </div>
  );
}
