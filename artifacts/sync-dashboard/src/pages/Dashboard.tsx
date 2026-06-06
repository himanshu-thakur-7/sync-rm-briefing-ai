import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetBriefingStats, useListBriefings,
  getListBriefingsQueryKey, getGetBriefingStatsQueryKey, BriefingLog,
} from "@workspace/api-client-react";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { Header } from "@/components/Header";
import { MetricCards } from "@/components/MetricCards";
import { SyncPanel } from "@/components/SyncPanel";
import { LiveFeed } from "@/components/LiveFeed";
import { Comparison } from "@/components/Comparison";
import { Footer } from "@/components/Footer";
import { WebhookActivityPanel, WebhookEventEntry } from "@/components/WebhookActivityPanel";
import { CRMEmbedRail } from "@/components/CRMEmbedPanel";
import { BackgroundBeams } from "@/components/aceternity/background-beams";
import { GridPattern } from "@/components/aceternity/grid-pattern";
import { useConnection } from "@/lib/connection-context";
import { providerFromConnectionId } from "@/components/CRMSourceBadge";
import { PanelRightOpen } from "lucide-react";

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { connectionId } = useConnection();
  const [activeClientId, setActiveClientId] = useState("");
  const [rmName, setRmName] = useState(import.meta.env.VITE_DEMO_RM_NAME ?? "Himanshu");
  const [embedOpen, setEmbedOpen] = useState(false);
  const [webhookEvents, setWebhookEvents] = useState<WebhookEventEntry[]>([]);

  const { data: initialStats } = useGetBriefingStats({ query: { refetchInterval: 10000 } as any });
  const { data: initialBriefings } = useListBriefings(undefined, { query: { refetchInterval: 15000 } as any });

  const handleWsMessage = (msg: WebSocketMessage) => {
    if (msg.type === "history") {
      queryClient.setQueryData(getListBriefingsQueryKey(), msg.data);
    } else if (msg.type === "sync_completed") {
      queryClient.setQueryData<BriefingLog[]>(getListBriefingsQueryKey(), old => old ? [msg.data, ...old] : [msg.data]);
      queryClient.invalidateQueries({ queryKey: getGetBriefingStatsQueryKey() });
    } else if (msg.type === "webhook_event") {
      setWebhookEvents(prev => [{ id: Date.now(), ...msg.data } as WebhookEventEntry, ...prev.slice(0, 19)]);
    }
  };

  const { isConnected, latencyMs } = useWebSocket({ onMessage: handleWsMessage });
  const provider = providerFromConnectionId(connectionId);
  const activeConnections = activeClientId
    ? [{ id: connectionId, provider, label: connectionId }]
    : [];

  return (
    <div className="relative min-h-screen bg-[#020817] text-white selection:bg-indigo-500/30 selection:text-white">
      {/* Full-page atmospheric layers */}
      <GridPattern />
      <BackgroundBeams />
      {/* Radial glow from top */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-indigo-500/10 blur-3xl" />
        <div className="absolute top-20 right-1/4 h-64 w-64 rounded-full bg-violet-500/8 blur-3xl" />
      </div>

      <div className="relative z-10">
        <Header
          isConnected={isConnected}
          latencyMs={latencyMs}
          activeClientId={activeClientId || undefined}
          rmName={rmName}
        />

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-5 p-4 md:p-6">
          {/* Hero text */}
          <div className="pt-2 pb-4 border-b border-white/[0.04]">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-indigo-400/70">
              Relationship Manager Desk
            </p>
            <h2 className="mt-1.5 text-xl font-semibold tracking-tight text-slate-100">
              Pre-meeting briefings. Live telemetry. CRM outcomes.
            </h2>
          </div>

          <MetricCards stats={initialStats} />

          {/* Main grid */}
          <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-12">
            {/* Left col */}
            <div className="space-y-4 lg:col-span-4">
              <SyncPanel
                onClientSelect={setActiveClientId}
                onRmNameChange={setRmName}
                onShowEmbed={() => setEmbedOpen(true)}
                activeClientId={activeClientId}
              />
              <Comparison />
            </div>

            {/* Center: live feed */}
            <div className="lg:col-span-5">
              <LiveFeed briefings={initialBriefings || []} />
            </div>

            {/* Right: webhook activity */}
            <div className="lg:col-span-3">
              <WebhookActivityPanel events={webhookEvents} />
            </div>
          </div>
        </main>

        <Footer />
      </div>

      {/* CRM embed rail */}
      {embedOpen && activeClientId && activeConnections.length > 0 && (
        <div className="fixed inset-y-0 right-0 z-40 w-[420px] border-l border-white/[0.06] bg-[#020817]/95 shadow-2xl backdrop-blur-xl">
          <CRMEmbedRail
            connections={activeConnections}
            clientId={activeClientId}
            defaultProvider={provider}
            onClose={() => setEmbedOpen(false)}
          />
        </div>
      )}

      {/* Floating CRM view button */}
      {!embedOpen && activeClientId && (
        <div className="fixed bottom-6 right-6 z-30">
          <button
            onClick={() => setEmbedOpen(true)}
            className="flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-xs font-medium text-slate-300 shadow-xl backdrop-blur-xl transition-all hover:bg-white/[0.08] hover:text-white"
          >
            <PanelRightOpen className="h-3.5 w-3.5" />
            CRM View
          </button>
        </div>
      )}
    </div>
  );
}
