import { Moon, Sun, Wifi, WifiOff, Settings } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { ConnectionSwitcher } from "./ConnectionSwitcher";
import { PiiScrubToggle } from "./PiiScrubToggle";
import { VoiceCommandBar } from "./VoiceCommandBar";
import { useConnection } from "@/lib/connection-context";
import { useLocation } from "wouter";

interface Props {
  isConnected: boolean;
  latencyMs: number | null;
  activeClientId?: string;
  rmName?: string;
}

export function Header({ isConnected, latencyMs, activeClientId, rmName }: Props) {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { isSandbox } = useConnection();
  const [, navigate] = useLocation();

  return (
    <div className="sticky top-0 z-50">
      <header className="relative border-b border-white/[0.06] bg-[#020817]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-6 lg:px-8">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg">
              <div className="absolute inset-0 rounded-lg bg-indigo-500/20 ring-1 ring-indigo-500/40" />
              <div className="absolute inset-0 rounded-lg opacity-60"
                style={{ background: "radial-gradient(circle, rgba(99,102,241,0.4) 0%, transparent 70%)" }} />
              <span className="relative text-sm font-bold text-indigo-300">S</span>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white leading-none">SYNC</h1>
              <span className="text-[10px] text-slate-500">Voice AI for your CRM</span>
            </div>
          </div>

          {/* Right cluster */}
          <div className="flex items-center gap-2">
            {/* Live indicator */}
            <div className="hidden h-8 items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 text-xs sm:flex">
              {isConnected
                ? <><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" /></span><span className="text-emerald-400 font-medium">Live</span></>
                : <><WifiOff className="h-3 w-3 text-red-400" /><span className="text-red-400 font-medium">Offline</span></>
              }
            </div>

            {latencyMs !== null && isConnected && (
              <div className="hidden h-8 items-center rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 font-mono text-xs text-slate-400 sm:flex">
                {latencyMs}ms
              </div>
            )}

            <ConnectionSwitcher />

            {activeClientId && (
              <VoiceCommandBar clientId={activeClientId} rmName={rmName} />
            )}

            <PiiScrubToggle />

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 border border-white/[0.06] bg-white/[0.03] text-slate-400 hover:bg-white/[0.06] hover:text-white"
              onClick={() => navigate("/settings/integrations")}
              title="Integrations"
            >
              <Settings className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 border border-white/[0.06] bg-white/[0.03] text-slate-400 hover:bg-white/[0.06] hover:text-white"
              onClick={() => setTheme(isDark ? "light" : "dark")}
            >
              {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>

        {/* Sandbox ribbon */}
        {isSandbox && (
          <div className="border-t border-amber-500/20 bg-amber-500/5 px-4 py-1 text-center text-[10px] font-medium tracking-wide text-amber-400/80 uppercase">
            Sandbox — LeadSquared MockTransport · Switch source in the selector above
          </div>
        )}
      </header>
    </div>
  );
}
