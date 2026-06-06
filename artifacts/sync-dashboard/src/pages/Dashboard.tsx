import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { 
  useGetBriefingStats, 
  useListBriefings, 
  getListBriefingsQueryKey,
  getGetBriefingStatsQueryKey,
  BriefingLog
} from "@workspace/api-client-react";
import { useWebSocket, WebSocketMessage } from "@/hooks/use-websocket";
import { Header } from "@/components/Header";
import { MetricCards } from "@/components/MetricCards";
import { SyncPanel } from "@/components/SyncPanel";
import { LiveFeed } from "@/components/LiveFeed";
import { Comparison } from "@/components/Comparison";
import { Footer } from "@/components/Footer";

export default function Dashboard() {
  const queryClient = useQueryClient();

  const { data: initialStats } = useGetBriefingStats({ 
    query: { refetchInterval: 10000 } 
  });
  
  const { data: initialBriefings } = useListBriefings(undefined, { 
    query: { refetchInterval: 15000 } 
  });

  const handleWsMessage = (message: WebSocketMessage) => {
    if (message.type === "history") {
      queryClient.setQueryData(getListBriefingsQueryKey(), message.data);
    } else if (message.type === "sync_completed") {
      queryClient.setQueryData<BriefingLog[]>(getListBriefingsQueryKey(), (old) => {
        if (!old) return [message.data];
        return [message.data, ...old];
      });
      // Invalidate stats to refresh them
      queryClient.invalidateQueries({ queryKey: getGetBriefingStatsQueryKey() });
    } else if (message.type === "call_started") {
      // Could show a toast or update some specific state here
    }
  };

  const { isConnected, latencyMs } = useWebSocket({ onMessage: handleWsMessage });

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans selection:bg-primary selection:text-primary-foreground dark">
      <Header isConnected={isConnected} latencyMs={latencyMs} />
      
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 lg:p-8 space-y-6 md:space-y-8">
        <MetricCards stats={initialStats} />
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8 items-start">
          <div className="lg:col-span-1 space-y-6 md:space-y-8">
            <SyncPanel />
            <Comparison />
          </div>
          
          <div className="lg:col-span-2">
            <LiveFeed briefings={initialBriefings || []} />
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
}