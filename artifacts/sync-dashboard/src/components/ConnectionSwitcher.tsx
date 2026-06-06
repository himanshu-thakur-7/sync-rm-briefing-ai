/**
 * Editorial connection switcher — looks like a filing-cabinet selector.
 */
import { useEffect, useState } from "react";
import { ChevronDown, Database, Plug } from "lucide-react";
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
  const { connectionId, setConnectionId } = useConnection();
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
        <button className="inline-flex h-8 items-center gap-2 border border-ink/30 bg-paper px-2.5 font-edit-mono text-[10px] uppercase tracking-widest text-ink/80 transition-colors hover:bg-ink hover:text-cream">
          <Database className="h-3 w-3" />
          <span className="hidden max-w-[110px] truncate sm:inline">{activeLabel}</span>
          <CRMSourceBadge provider={activeProvider} className="hidden md:inline-flex" />
          <ChevronDown className="h-3 w-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 rounded-none border-ink/30 bg-paper">
        <DropdownMenuLabel className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
          Switch Source
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-ink/15" />
        {connections.map(conn => (
          <DropdownMenuItem
            key={conn.id}
            onClick={() => setConnectionId(conn.id)}
            className="flex items-center justify-between gap-3 focus:bg-ink/[0.05]"
          >
            <div className="flex min-w-0 flex-col">
              <span className="truncate font-serif text-sm text-ink">{conn.label}</span>
              <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">{conn.status}</span>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <CRMSourceBadge provider={conn.provider} />
              {conn.id === connectionId && <span className="h-1.5 w-1.5 rounded-full bg-emerald-700" />}
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator className="bg-ink/15" />
        <DropdownMenuItem
          onClick={() => navigate("/settings/integrations")}
          className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 focus:bg-ink/[0.05]"
        >
          <Plug className="mr-2 h-3 w-3" />Manage integrations
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
