/**
 * CRMEmbedPanel — renders the native CRM contact view in a sandboxed iframe.
 * Editorial chrome around it. Uses relative URLs for Vite proxy.
 */
import { useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { CRMSourceBadge } from "./CRMSourceBadge";

interface EmbedSpec {
  url: string; provider: string; label: string;
  sandbox_attrs: string; may_block_frame: boolean;
}

interface Props {
  connectionId: string;
  clientId: string;
  provider: string;
  onClose?: () => void;
}

export function CRMEmbedPanel({ connectionId, clientId, provider }: Props) {
  const [spec, setSpec] = useState<EmbedSpec | null>(null);
  const [loading, setLoading] = useState(true);
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

  return (
    <div className="flex h-full flex-col">
      {/* Sub-header with provider */}
      <div className="flex items-center justify-between border-b border-ink/15 bg-ink/[0.01] px-3 py-2">
        <div className="flex items-center gap-2">
          <CRMSourceBadge provider={spec?.provider ?? provider} />
          <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            Contact ID · {clientId}
          </span>
        </div>
        {spec && !spec.may_block_frame && (
          <a href={spec.url} target="_blank" rel="noopener noreferrer"
            className="text-ink/50 hover:text-ink">
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      <div className="relative flex-1 bg-paper">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
          </div>
        )}

        {spec && spec.may_block_frame && (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <CRMSourceBadge provider={spec.provider} />
            <p className="font-serif text-sm italic text-ink/60">
              {spec.label} restricts third-party embedding.<br />
              <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
                Production would use the {spec.label} UI Extension SDK.
              </span>
            </p>
            <a href={spec.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 border-2 border-ink bg-paper px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink hover:bg-ink hover:text-cream">
              <ExternalLink className="h-3 w-3" />
              Open in {spec.label}
            </a>
          </div>
        )}

        {spec && !spec.may_block_frame && (
          <iframe
            ref={iframeRef}
            src={spec.url}
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
          onClose={connections.length === 1 ? onClose : undefined}
        />
      </div>
    </div>
  );
}
