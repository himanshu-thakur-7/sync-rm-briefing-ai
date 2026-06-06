/**
 * CRMEmbedPanel — renders the native CRM contact view in a sandboxed iframe.
 * Uses RELATIVE paths so Vite dev proxy works and prod just works.
 */
import { useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, PanelRightClose } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CRMSourceBadge } from "./CRMSourceBadge";

interface EmbedSpec {
  url: string;
  provider: string;
  label: string;
  sandbox_attrs: string;
  may_block_frame: boolean;
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
        if (ct.includes("application/json")) {
          return r.json() as Promise<EmbedSpec>;
        }
        // Sandbox returns HTML directly — wrap into an EmbedSpec
        return {
          url,
          provider,
          label: "LeadSquared (Sandbox)",
          sandbox_attrs: "allow-scripts allow-same-origin",
          may_block_frame: false,
        } as EmbedSpec;
      })
      .then(data => {
        setSpec({
          ...data,
          url: data.url.startsWith("http")
            ? data.url
            : (data.url.startsWith("/") ? data.url : `/${data.url}`),
        });
        setLoading(false);
      })
      .catch(() => {
        setSpec({
          url: `/api/v1/embeds/sandbox/contact/${clientId}`,
          provider, label: provider,
          sandbox_attrs: "allow-scripts allow-same-origin",
          may_block_frame: false,
        });
        setLoading(false);
      });
  }, [connectionId, clientId, provider]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2">
          <CRMSourceBadge provider={spec?.provider ?? provider} />
          <span className="text-xs font-semibold text-slate-300">Contact View</span>
        </div>
        <div className="flex items-center gap-1">
          {spec && !spec.may_block_frame && (
            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-500 hover:text-slate-300" asChild>
              <a href={spec.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
          )}
          {onClose && (
            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-500 hover:text-slate-300" onClick={onClose}>
              <PanelRightClose className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="relative flex-1 bg-white">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]">
            <Loader2 className="h-5 w-5 animate-spin text-slate-600" />
          </div>
        )}

        {spec && spec.may_block_frame && (
          <div className="flex h-full flex-col items-center justify-center gap-3 bg-[#0d1117] p-6 text-center">
            <CRMSourceBadge provider={spec.provider} />
            <p className="text-sm text-slate-400">
              {spec.label} restricts third-party embedding.
              <br />
              <span className="text-[11px] text-slate-600">
                In production, this would use the {spec.label} UI Extension SDK.
              </span>
            </p>
            <Button variant="outline" size="sm" className="border-white/[0.08] bg-white/[0.02] text-slate-300 hover:bg-white/[0.06]" asChild>
              <a href={spec.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-3 w-3" />Open in {spec.label}
              </a>
            </Button>
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
        <div className="flex gap-1 border-b border-white/[0.06] px-2 pt-2">
          {connections.map((c, i) => (
            <button key={c.id} onClick={() => setIdx(i)}
              className={`rounded-t px-3 py-1.5 text-xs font-medium transition-colors ${
                i === idx ? "border border-b-0 border-white/[0.06] bg-[#0d1117]" : "text-slate-500 hover:text-slate-300"
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
