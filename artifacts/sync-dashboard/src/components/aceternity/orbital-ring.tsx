/**
 * Concentric animated rings with floating CRM logos orbiting around a center node.
 * The visual centerpiece of the hero — shows SYNC at the center with all CRMs revolving around it.
 */
import { cn } from "@/lib/utils";

// Evenly spaced — 360 / 7 ≈ 51.4°
const PROVIDERS = [
  { name: "Pipedrive",   color: "#017737", angle:   0 },
  { name: "HubSpot",     color: "#ff7a59", angle:  51 },
  { name: "Salesforce",  color: "#00a1e0", angle: 103 },
  { name: "Zoho",        color: "#e74c3c", angle: 154 },
  { name: "Dynamics",    color: "#0078d4", angle: 206 },
  { name: "Freshworks",  color: "#10b981", angle: 257 },
  { name: "LeadSquared", color: "#8b5cf6", angle: 309 },
];

export function OrbitalRing({ className }: { className?: string }) {
  return (
    <div className={cn("relative aspect-square w-full max-w-[480px]", className)}>
      {/* Outer atmospheric glow */}
      <div className="absolute inset-0 rounded-full opacity-30"
        style={{ background: "radial-gradient(circle, rgba(99,102,241,0.4) 0%, transparent 60%)" }}
      />

      {/* Animated rings */}
      {[1, 0.75, 0.5].map((scale, i) => (
        <div
          key={i}
          className="absolute inset-0 rounded-full border border-white/[0.06]"
          style={{
            transform: `scale(${scale})`,
            animation: `ring-spin ${30 + i * 15}s linear infinite ${i % 2 ? "reverse" : ""}`,
          }}
        >
          <div
            className="absolute h-2 w-2 rounded-full"
            style={{
              top: 0, left: "50%", transform: "translate(-50%, -50%)",
              background: ["#6366f1", "#8b5cf6", "#06b6d4"][i],
              boxShadow: `0 0 12px ${["#6366f1", "#8b5cf6", "#06b6d4"][i]}`,
            }}
          />
        </div>
      ))}

      {/* Outer ring with CRM logos */}
      <div className="absolute inset-0">
        {PROVIDERS.map((p, i) => {
          const rad = (p.angle * Math.PI) / 180;
          const x = 50 + 50 * Math.cos(rad);
          const y = 50 + 50 * Math.sin(rad);
          return (
            <div
              key={p.name}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${x}%`, top: `${y}%`,
                animation: `orbit-float 6s ease-in-out infinite`,
                animationDelay: `${i * 0.5}s`,
              }}
            >
              <div
                className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] backdrop-blur-md text-[10px] font-bold text-white shadow-xl"
                style={{ boxShadow: `0 0 24px ${p.color}40` }}
              >
                <span style={{ color: p.color }}>{p.name[0]}</span>
              </div>
              <div className="mt-1 text-center text-[9px] font-medium uppercase tracking-wider text-slate-500">
                {p.name}
              </div>
            </div>
          );
        })}
      </div>

      {/* Center: SYNC node */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="relative">
          {/* Outer pulse */}
          <div className="absolute inset-0 -m-4 rounded-full bg-indigo-500/20 blur-2xl animate-pulse" />
          <div className="absolute inset-0 -m-2 rounded-full ring-2 ring-indigo-500/30"
            style={{ animation: "ping-slow 3s ease-in-out infinite" }}
          />
          {/* Core */}
          <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl"
            style={{
              background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%)",
              boxShadow: "0 0 40px rgba(99,102,241,0.6), inset 0 0 20px rgba(255,255,255,0.1)",
            }}
          >
            <span className="text-2xl font-bold text-white tracking-tight">S</span>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes ring-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes orbit-float { 0%, 100% { transform: translate(-50%, -50%) translateY(0); } 50% { transform: translate(-50%, -50%) translateY(-4px); } }
        @keyframes ping-slow { 0% { transform: scale(1); opacity: 0.6; } 100% { transform: scale(1.6); opacity: 0; } }
      `}</style>
    </div>
  );
}
