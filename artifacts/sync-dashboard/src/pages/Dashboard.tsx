/**
 * SYNC — The Briefing Desk.
 * Editorial dashboard: cream paper, ink type, ruled grid.
 */
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
import { useConnection } from "@/lib/connection-context";
import { providerFromConnectionId } from "@/components/CRMSourceBadge";
import { PanelRightOpen, X } from "lucide-react";

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
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      <Header
        isConnected={isConnected}
        latencyMs={latencyMs}
        activeClientId={activeClientId || undefined}
        rmName={rmName}
      />

      <main className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 md:py-8">
        {/* Page kicker */}
        <div className="mb-6 flex flex-col items-baseline gap-3 border-b border-ink/15 pb-5 md:flex-row md:justify-between">
          <div>
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              § Front Page · The Relationship Desk
            </p>
            <h2 className="mt-1 font-display text-3xl leading-[1.05] text-ink md:text-4xl">
              <em className="italic">Live</em> briefings, dispatched as they happen.
            </h2>
          </div>
          <p className="hidden font-serif text-sm italic text-ink/60 md:block">
            All times IST · All data via the active CRM connection.
          </p>
        </div>

        {/* KPI strip */}
        <MetricCards stats={initialStats} />

        {/* Main grid */}
        <div className="mt-6 grid grid-cols-1 items-start gap-5 lg:grid-cols-12">
          {/* Left column — Sync controls + Comparison */}
          <div className="space-y-5 lg:col-span-4">
            <SyncPanel
              onClientSelect={setActiveClientId}
              onRmNameChange={setRmName}
              onShowEmbed={() => setEmbedOpen(true)}
              activeClientId={activeClientId}
            />
            <Comparison />
          </div>

          {/* Center — Live feed (the front page) */}
          <div className="lg:col-span-5">
            <LiveFeed briefings={initialBriefings || []} />
          </div>

          {/* Right — Webhook log */}
          <div className="lg:col-span-3">
            <WebhookActivityPanel events={webhookEvents} />
          </div>
        </div>
      </main>

      <Footer />

      {/* CRM embed rail */}
      {embedOpen && activeClientId && activeConnections.length > 0 && (
        <div className="fixed inset-y-0 right-0 z-40 w-[440px] border-l-2 border-ink bg-paper shadow-2xl">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-ink bg-ink/[0.02] px-4 py-3">
              <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/70">
                § CRM Contact View
              </span>
              <button
                onClick={() => setEmbedOpen(false)}
                className="flex h-6 w-6 items-center justify-center border border-ink/30 text-ink/60 hover:bg-ink hover:text-paper"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <CRMEmbedRail
                connections={activeConnections}
                clientId={activeClientId}
                defaultProvider={provider}
                onClose={() => setEmbedOpen(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Floating "Open CRM view" button */}
      {!embedOpen && activeClientId && (
        <div className="fixed bottom-6 right-6 z-30">
          <button
            onClick={() => setEmbedOpen(true)}
            className="inline-flex items-center gap-2 border-2 border-ink bg-paper px-4 py-2.5 font-edit-mono text-[10px] uppercase tracking-widest text-ink shadow-lg transition-colors hover:bg-ink hover:text-cream"
          >
            <PanelRightOpen className="h-3 w-3" />
            CRM Contact View
          </button>
        </div>
      )}
    </div>
  );
}
