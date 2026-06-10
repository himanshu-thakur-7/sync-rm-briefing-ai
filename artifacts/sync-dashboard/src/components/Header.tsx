/**
 * Editorial dashboard masthead — like the running header of a newspaper.
 * "SYNC · The Briefing Desk · Vol. II No. 1 · LIVE"
 */
import { Settings, Radar, Sunrise, Headphones } from "lucide-react";
import { useLocation } from "wouter";
import { ConnectionSwitcher } from "./ConnectionSwitcher";
import { PiiScrubToggle } from "./PiiScrubToggle";
import { VoiceCommandBar } from "./VoiceCommandBar";
import { useConnection } from "@/lib/connection-context";
import { useEffect, useState } from "react";
import { isWhisperOn, setWhisperOn, speakArmed, whisperSupported } from "@/lib/whisper";

interface Props {
  isConnected: boolean;
  latencyMs: number | null;
  activeClientId?: string;
  rmName?: string;
}

export function Header({ isConnected, latencyMs, activeClientId, rmName }: Props) {
  const { isSandbox } = useConnection();
  const [, navigate] = useLocation();
  const [date, setDate] = useState("");

  useEffect(() => {
    const d = new Date();
    setDate(d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).toUpperCase());
  }, []);

  return (
    <div className="sticky top-0 z-50">
      {/* Date strip */}
      <div className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex h-7 max-w-[1400px] items-center justify-between px-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 md:px-6">
          <div className="flex items-center gap-3">
            <span className="hidden md:inline">{date}</span>
            <span className="hidden md:inline text-ink/30">·</span>
            <span>Vol. II · No. 1 · The Briefing Desk</span>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/radar")} className="inline-flex items-center gap-1 hover:text-ink">
              <Radar className="h-3 w-3" /> Watchlist
            </button>
            <span className="hidden sm:inline text-ink/30">·</span>
            <button onClick={() => navigate("/morning-brief")} className="inline-flex items-center gap-1 hover:text-ink">
              <Sunrise className="h-3 w-3" /> Standup
            </button>
            <span className="hidden sm:inline text-ink/30">·</span>
            <a href="/" className="hover:text-ink">← Home</a>
          </div>
        </div>
      </div>

      {/* Masthead */}
      <header className="border-b-2 border-double border-ink bg-paper">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between px-4 py-4 md:px-6">
          {/* Wordmark */}
          <div className="flex items-baseline gap-4">
            <a href="/" className="font-display text-4xl leading-none tracking-tight text-ink md:text-5xl">
              S<span className="italic">y</span>nc
            </a>
            <span className="hidden font-serif text-sm italic text-ink/70 md:inline">
              The Briefing Desk
            </span>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <LiveIndicator isConnected={isConnected} latencyMs={latencyMs} />
            <span className="hidden md:block h-6 w-px bg-ink/15" />
            <ConnectionSwitcher />
            <VoiceCommandBar clientId={activeClientId} rmName={rmName} />
            <WhisperToggle />
            <PiiScrubToggle />
            <button
              onClick={() => navigate("/settings/integrations")}
              className="inline-flex h-8 w-8 items-center justify-center border border-ink/30 bg-paper text-ink/70 transition-colors hover:bg-ink hover:text-cream"
              title="Integrations"
            >
              <Settings className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Sandbox ribbon */}
      {isSandbox && (
        <div className="border-b border-ink/15 bg-amber-50 px-4 py-1.5 text-center font-edit-mono text-[10px] uppercase tracking-widest text-amber-900 md:px-6">
          [ Sandbox Edition — Demo data via LeadSquared adapter on MockTransport. Switch source above to go live. ]
        </div>
      )}
    </div>
  );
}

function LiveIndicator({ isConnected, latencyMs }: { isConnected: boolean; latencyMs: number | null }) {
  return (
    <div className="hidden h-8 items-center gap-2 border border-ink/30 bg-paper px-2.5 font-edit-mono text-[10px] uppercase tracking-widest md:flex">
      {isConnected ? (
        <>
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-700 opacity-60" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-700" />
          </span>
          <span className="font-semibold text-emerald-800">Live</span>
          {latencyMs !== null && (
            <>
              <span className="text-ink/30">·</span>
              <span className="text-ink/60">{latencyMs}ms</span>
            </>
          )}
        </>
      ) : (
        <>
          <span className="h-1.5 w-1.5 rounded-full bg-red-700" />
          <span className="font-semibold text-red-800">Offline</span>
        </>
      )}
    </div>
  );
}

function WhisperToggle() {
  const [on, setOn] = useState(isWhisperOn());
  if (!whisperSupported()) return null;

  const flip = () => {
    const next = !on;
    setOn(next);
    setWhisperOn(next);
    if (next) speakArmed();
    else window.speechSynthesis.cancel();
  };

  return (
    <button
      onClick={flip}
      className={`inline-flex h-8 w-8 items-center justify-center border transition-colors ${
        on
          ? "border-amber-700 bg-amber-100 text-amber-900"
          : "border-ink/30 bg-paper text-ink/70 hover:bg-ink hover:text-cream"
      }`}
      title={on
        ? "Whisper Mode ON — coaching nudges are spoken into your earbud during live calls"
        : "Whisper Mode — speak coaching nudges into your earbud during live calls"}
    >
      <Headphones className="h-3.5 w-3.5" />
    </button>
  );
}
