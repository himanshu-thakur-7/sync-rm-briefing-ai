import { useEffect, useState } from "react";
import { ChevronDown, Database, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CRMSourceBadge, providerFromConnectionId } from "./CRMSourceBadge";
import { useConnection } from "@/lib/connection-context";
import { useLocation } from "wouter";

interface Connection { id: string; provider: string; label: string; status: string; is_default: boolean; }

export function ConnectionSwitcher() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const { connectionId, setConnectionId, isSandbox } = useConnection();
  const [, navigate] = useLocation();

  useEffect(() => {
    fetch("/api/v1/integrations").then(r => r.json()).then(setConnections).catch(() => {});
  }, []);

  const active = connections.find(c => c.id === connectionId);
  const activeLabel = active?.label ?? "Sandbox";
  const activeProvider = active?.provider ?? providerFromConnectionId(connectionId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm"
          className="h-8 gap-2 border border-white/[0.06] bg-white/[0.03] text-slate-300 hover:bg-white/[0.06] hover:text-white text-xs">
          <Database className="h-3 w-3" />
          <span className="hidden max-w-[100px] truncate sm:block text-[11px]">{activeLabel}</span>
          <CRMSourceBadge provider={activeProvider} />
          <ChevronDown className="h-3 w-3 text-slate-600" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60 border-white/[0.08] bg-[#0d1117]">
        <DropdownMenuLabel className="text-[10px] uppercase tracking-widest text-slate-600">
          Switch CRM Source
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-white/[0.06]" />
        {connections.map(conn => (
          <DropdownMenuItem
            key={conn.id}
            onClick={() => setConnectionId(conn.id)}
            className="flex items-center justify-between gap-3 text-slate-300 focus:bg-white/[0.05]"
          >
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-xs font-medium">{conn.label}</span>
              <span className="text-[10px] capitalize text-slate-600">{conn.status}</span>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <CRMSourceBadge provider={conn.provider} />
              {conn.id === connectionId && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator className="bg-white/[0.06]" />
        <DropdownMenuItem onClick={() => navigate("/settings/integrations")} className="text-[11px] text-slate-500 focus:bg-white/[0.05] focus:text-slate-300">
          <Plug className="mr-2 h-3 w-3" />Manage integrations
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
