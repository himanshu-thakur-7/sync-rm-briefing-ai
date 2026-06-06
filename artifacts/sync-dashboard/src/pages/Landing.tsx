import { useLocation } from "wouter";
import {
  PhoneCall, Mic, Zap, Shield, Sparkles, Layers,
  ArrowRight, CheckCircle2, Play, Github,
} from "lucide-react";
import { BackgroundBeams } from "@/components/aceternity/background-beams";
import { GridPattern } from "@/components/aceternity/grid-pattern";
import { Spotlight } from "@/components/aceternity/spotlight";
import { AuroraText } from "@/components/aceternity/aurora-text";
import { TypewriterText } from "@/components/aceternity/typewriter";
import { OrbitalRing } from "@/components/aceternity/orbital-ring";
import { Marquee } from "@/components/aceternity/marquee";
import { BentoGrid, BentoItem } from "@/components/aceternity/bento-grid";
import { ShimmerButton } from "@/components/aceternity/shimmer-button";
import { GlowCard } from "@/components/aceternity/glow-card";
import { AnimatedCounter } from "@/components/aceternity/animated-counter";

const CRM_LOGOS = [
  { name: "HubSpot", color: "#ff7a59" },
  { name: "Salesforce", color: "#00a1e0" },
  { name: "Zoho CRM", color: "#e74c3c" },
  { name: "Microsoft Dynamics 365", color: "#0078d4" },
  { name: "Freshworks", color: "#10b981" },
  { name: "LeadSquared", color: "#8b5cf6" },
];

export default function Landing() {
  const [, navigate] = useLocation();

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#020817] text-white antialiased">
      {/* Atmospheric layers */}
      <GridPattern />
      <BackgroundBeams />

      {/* Nav */}
      <Nav onCta={() => navigate("/dashboard")} />

      {/* Hero */}
      <Hero onCta={() => navigate("/dashboard")} />

      {/* CRM marquee */}
      <CrmStrip />

      {/* Live demo preview */}
      <DemoSection onCta={() => navigate("/dashboard")} />

      {/* Three-pillar story */}
      <PillarsSection />

      {/* Bento features */}
      <FeaturesSection />

      {/* Numbers */}
      <StatsSection />

      {/* How it works */}
      <HowItWorks />

      {/* Final CTA */}
      <FinalCta onCta={() => navigate("/dashboard")} />

      {/* Footer */}
      <LandingFooter />
    </div>
  );
}

/* ─────────────────────────────── Nav ─────────────────────────────── */

function Nav({ onCta }: { onCta: () => void }) {
  return (
    <nav className="relative z-50 border-b border-white/[0.05] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-8">
        <div className="flex items-center gap-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-lg">
            <div className="absolute inset-0 rounded-lg bg-indigo-500/20 ring-1 ring-indigo-500/40" />
            <span className="relative text-sm font-bold text-indigo-300">S</span>
          </div>
          <div>
            <div className="text-base font-bold tracking-tight leading-none">SYNC</div>
            <div className="text-[10px] text-slate-500">Voice AI for your CRM</div>
          </div>
        </div>

        <div className="hidden items-center gap-6 text-sm text-slate-400 md:flex">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how" className="hover:text-white transition-colors">How it works</a>
          <a href="#integrations" className="hover:text-white transition-colors">Integrations</a>
          <a href="#numbers" className="hover:text-white transition-colors">Numbers</a>
        </div>

        <div className="flex items-center gap-2">
          <a href="https://github.com" target="_blank" rel="noopener noreferrer"
            className="hidden h-9 w-9 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.03] text-slate-400 transition-colors hover:bg-white/[0.06] hover:text-white sm:flex">
            <Github className="h-4 w-4" />
          </a>
          <button onClick={onCta}
            className="rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-4 py-2 text-xs font-semibold text-indigo-300 transition-all hover:bg-indigo-500/25 hover:text-white">
            Open Dashboard →
          </button>
        </div>
      </div>
    </nav>
  );
}

/* ─────────────────────────────── Hero ─────────────────────────────── */

function Hero({ onCta }: { onCta: () => void }) {
  return (
    <section className="relative isolate overflow-hidden">
      <Spotlight className="-top-40 left-0 md:-top-20 md:left-60" fill="rgba(99,102,241,0.4)" />

      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-indigo-500/15 blur-3xl" />
        <div className="absolute top-20 right-1/4 h-72 w-72 rounded-full bg-violet-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-4 pt-16 pb-20 md:grid-cols-2 md:px-8 md:pt-24 md:pb-32">
        {/* Left: copy */}
        <div className="text-center md:text-left">
          {/* Eyebrow chip */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[11px] backdrop-blur-sm">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </span>
            <span className="text-slate-300">Live demo · GrowthX Voice AI Buildathon</span>
            <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-indigo-300">Powered by Ringg</span>
          </div>

          <h1 className="font-bold tracking-tight text-white leading-[1.05]">
            <span className="block text-4xl md:text-5xl lg:text-6xl">Before every meeting,</span>
            <span className="mt-1 block text-4xl md:text-5xl lg:text-6xl">
              your RM knows{" "}
              <AuroraText className="font-bold">
                everything
              </AuroraText>
              .
            </span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-400 md:text-lg">
            SYNC is the voice-AI layer for{" "}
            <TypewriterText
              words={["HubSpot.", "Salesforce.", "Zoho.", "Dynamics.", "Freshworks.", "LeadSquared.", "your CRM."]}
              className="font-semibold text-indigo-300"
            />
            <br />
            Your RM makes a 30-second phone call, walks into the meeting fully prepared.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row md:justify-start">
            <ShimmerButton onClick={onCta} className="px-6 py-3 text-sm font-semibold">
              <Play className="h-4 w-4" />
              Try the live demo
              <ArrowRight className="h-4 w-4" />
            </ShimmerButton>

            <button
              onClick={() => document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })}
              className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-6 py-3 text-sm font-medium text-slate-300 transition-all hover:bg-white/[0.06] hover:text-white"
            >
              How it works
            </button>
          </div>

          {/* Tagline pills */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-2 md:justify-start">
            {[
              { icon: PhoneCall, text: "30-sec phone briefing" },
              { icon: Mic, text: "Voice → CRM actions" },
              { icon: Layers, text: "7 CRM integrations" },
              { icon: Zap, text: "<800ms latency" },
            ].map(({ icon: Icon, text }) => (
              <span key={text} className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1 text-[11px] text-slate-400">
                <Icon className="h-3 w-3 text-indigo-400" />
                {text}
              </span>
            ))}
          </div>
        </div>

        {/* Right: orbital visual */}
        <div className="relative flex items-center justify-center">
          <OrbitalRing />
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── CRM strip ─────────────────────────────── */

function CrmStrip() {
  return (
    <section id="integrations" className="border-y border-white/[0.04] bg-white/[0.01] py-10">
      <div className="mx-auto max-w-7xl px-4 md:px-8">
        <p className="mb-6 text-center text-[10px] font-bold uppercase tracking-widest text-slate-600">
          Plug into the CRM your bank already runs
        </p>
        <Marquee duration={40} className="opacity-90">
          {CRM_LOGOS.concat(CRM_LOGOS).map((crm, i) => (
            <div key={i} className="flex items-center gap-3 px-6">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-sm font-bold"
                style={{ color: crm.color, boxShadow: `0 0 20px ${crm.color}30` }}
              >
                {crm.name[0]}
              </div>
              <span className="text-base font-semibold text-slate-300">{crm.name}</span>
            </div>
          ))}
        </Marquee>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Demo section ─────────────────────────────── */

function DemoSection({ onCta }: { onCta: () => void }) {
  return (
    <section className="relative py-20 md:py-28">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/3 top-1/4 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 md:px-8">
        <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
          {/* Left */}
          <div>
            <Eyebrow color="cyan">Watch a real call</Eyebrow>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
              The RM calls a number.<br />
              SYNC narrates the entire client.
            </h2>
            <p className="mt-5 text-base leading-relaxed text-slate-400">
              No reports. No data dumps. SYNC tells the story of a person —
              their portfolio, their risk signals, the complaint they raised last week,
              the cross-sell tied to their life context.
            </p>

            <ul className="mt-6 space-y-3">
              {[
                "Identity → Portfolio → Risk → Gap → The Play, in 45 seconds",
                "Code-switches to Hinglish where it fits",
                "Handles interruptions naturally (\"What was his EMI again?\")",
                "Auto-logs the touchpoint back to the CRM",
              ].map((line) => (
                <li key={line} className="flex items-start gap-3 text-sm text-slate-300">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>

            <div className="mt-8">
              <ShimmerButton onClick={onCta} className="px-5 py-2.5 text-sm">
                Open live dashboard <ArrowRight className="h-4 w-4" />
              </ShimmerButton>
            </div>
          </div>

          {/* Right: mock call transcript card */}
          <GlowCard glowColor="rgba(6,182,212,0.3)" className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/15 ring-1 ring-emerald-500/30">
                  <PhoneCall className="h-3.5 w-3.5 text-emerald-400" />
                </div>
                <div>
                  <div className="text-sm font-semibold">Live Call</div>
                  <div className="text-[10px] text-slate-500">SYNC → RM Himanshu</div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-bold uppercase text-emerald-400">REC</span>
                <span className="font-mono text-slate-500">00:42</span>
              </div>
            </div>

            {/* Waveform */}
            <div className="mb-4 flex h-12 items-center justify-center gap-0.5 rounded-lg bg-white/[0.02] px-3">
              {Array.from({ length: 60 }).map((_, i) => (
                <div
                  key={i}
                  className="w-0.5 rounded-full bg-indigo-400/60"
                  style={{
                    height: `${20 + Math.abs(Math.sin(i * 0.4)) * 80}%`,
                    animation: `wave-pulse 1.2s ease-in-out ${i * 0.04}s infinite alternate`,
                  }}
                />
              ))}
              <style>{`@keyframes wave-pulse { from { transform: scaleY(0.3); opacity: 0.5; } to { transform: scaleY(1); opacity: 1; } }`}</style>
            </div>

            <div className="space-y-3 text-sm leading-relaxed text-slate-300">
              <TranscriptLine speaker="SYNC">
                "Alright, so <span className="text-white font-semibold">Rahul Mehta</span> — 38, senior manager at Infosys.
                Home loan, 42 lakhs, EMI 34,800, next due in 4 days. <span className="text-emerald-400">Clean record</span> — 14 months, zero misses."
              </TranscriptLine>
              <TranscriptLine speaker="SYNC">
                "One thing though — he raised a <span className="text-amber-400 font-medium">complaint last week</span> about
                branch wait times. Still open. Don't get caught off guard."
              </TranscriptLine>
              <TranscriptLine speaker="SYNC">
                "Now here's the interesting part — eligible for a personal loan top-up,
                5 lakhs. But <span className="text-indigo-300 font-medium">lead with the SIP pitch</span>. Last June he
                mentioned saving for his kid's education, and we never followed up. <em>That's your opening.</em>"
              </TranscriptLine>
              <TranscriptLine speaker="SYNC" muted>
                "Kuch aur chahiye ya ready ho?"
              </TranscriptLine>
            </div>
          </GlowCard>
        </div>
      </div>
    </section>
  );
}

function TranscriptLine({ speaker, children, muted = false }: { speaker: string; children: React.ReactNode; muted?: boolean }) {
  return (
    <div className={`flex gap-3 ${muted ? "opacity-60" : ""}`}>
      <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-indigo-400 mt-1">{speaker}</span>
      <p className="flex-1 italic">{children}</p>
    </div>
  );
}

/* ─────────────────────────────── 3 pillars ─────────────────────────────── */

function PillarsSection() {
  return (
    <section className="relative py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4 md:px-8">
        <div className="mb-12 text-center">
          <Eyebrow color="indigo">Three pillars</Eyebrow>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
            Voice in. CRM out. Repeat.
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {[
            {
              num: "01",
              title: "Pre-meeting Briefing",
              desc: "RM calls a number, says the client's name. 45 seconds later they know everything that matters.",
              color: "indigo",
              tag: "Inbound voice",
            },
            {
              num: "02",
              title: "CRM-Native View",
              desc: "Embedded contact panel sits inside SYNC. See the HubSpot, Salesforce, or LeadSquared record side-by-side with the briefing.",
              color: "violet",
              tag: "Micro-frontend",
            },
            {
              num: "03",
              title: "Voice → CRM Actions",
              desc: "After the meeting, hold the mic. \"Create a follow-up task for Tuesday\" → executed in HubSpot via GPT-4o function calling.",
              color: "cyan",
              tag: "Outbound voice",
            },
          ].map((p) => (
            <GlowCard
              key={p.num}
              glowColor={{ indigo: "rgba(99,102,241,0.3)", violet: "rgba(139,92,246,0.3)", cyan: "rgba(6,182,212,0.3)" }[p.color] ?? ""}
              className="p-6"
            >
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600">{p.tag}</div>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="text-5xl font-black"
                  style={{
                    background: `linear-gradient(180deg, ${{ indigo: "#6366f1", violet: "#8b5cf6", cyan: "#06b6d4" }[p.color]}, transparent 80%)`,
                    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                  }}
                >
                  {p.num}
                </span>
                <h3 className="text-lg font-bold text-white">{p.title}</h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-slate-400">{p.desc}</p>
            </GlowCard>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Features (Bento) ─────────────────────────────── */

function FeaturesSection() {
  return (
    <section id="features" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4 md:px-8">
        <div className="mb-12 text-center">
          <Eyebrow color="indigo">What's inside</Eyebrow>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
            Real OAuth. Real provisioning.<br />Real writeback.
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-base text-slate-400">
            Not a mock CRM with a voice bot bolted on. Plug SYNC into your existing HubSpot, Salesforce, Zoho, Dynamics, Freshworks, or LeadSquared instance — OAuth, custom-field auto-provisioning, and writeback included.
          </p>
        </div>

        <BentoGrid>
          <BentoItem
            title="OAuth 2.0 for every major CRM"
            description="Authlib-backed OAuth dance for HubSpot, Salesforce, Zoho, Dynamics. Tokens encrypted at rest with Fernet."
            glowColor="rgba(99,102,241,0.25)"
            icon={<Shield className="h-5 w-5 text-indigo-400" />}
          />
          <BentoItem
            title="One-click field provisioning"
            description="Click 'Provision 9 missing fields' → SYNC creates them in your HubSpot via the Properties API. Salesforce gets a downloadable package.xml."
            glowColor="rgba(139,92,246,0.25)"
            icon={<Zap className="h-5 w-5 text-violet-400" />}
          />
          <BentoItem
            title="Voice commands → CRM actions"
            description="Hold the mic, speak naturally. GPT-4o resolves intent + anaphora ('mark his complaint as resolved'), confirms, then executes."
            glowColor="rgba(6,182,212,0.25)"
            icon={<Mic className="h-5 w-5 text-cyan-400" />}
          />
          <BentoItem
            title="Embedded CRM contact view"
            description="Open any client and the native HubSpot/Salesforce/LSQ contact panel slides in alongside. No tab switching."
            glowColor="rgba(249,115,22,0.25)"
            icon={<Layers className="h-5 w-5 text-orange-400" />}
          />
          <BentoItem
            title="Hinglish-fluent briefings"
            description="GPT-4o briefings code-switch to Hinglish where it fits. 'EMI time pe aa raha hai' beats 'payment was on schedule' every time."
            glowColor="rgba(16,185,129,0.25)"
            icon={<Sparkles className="h-5 w-5 text-emerald-400" />}
          />
          <BentoItem
            title="Real-time webhook telemetry"
            description="Every Ringg callback shows received → processing → processed live on the dashboard. HMAC-signed for prod."
            glowColor="rgba(244,114,182,0.25)"
            icon={<PhoneCall className="h-5 w-5 text-pink-400" />}
          />
        </BentoGrid>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Stats ─────────────────────────────── */

function StatsSection() {
  return (
    <section id="numbers" className="relative py-20 md:py-28">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 h-96 w-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/8 blur-3xl" />
      </div>
      <div className="relative mx-auto max-w-7xl px-4 md:px-8">
        <div className="mb-12 text-center">
          <Eyebrow color="indigo">Why this matters</Eyebrow>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
            The numbers are stupid.
          </h2>
        </div>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { value: 18, suffix: " min", label: "Prep time saved per meeting", color: "#6366f1" },
            { value: 100, suffix: "%", label: "Open complaints surfaced", color: "#10b981" },
            { value: 3, suffix: "×", label: "Higher cross-sell conversion", color: "#06b6d4" },
            { value: 15, prefix: "₹", suffix: "", label: "Per briefing call", color: "#f97316" },
          ].map((stat) => (
            <GlowCard key={stat.label} className="p-6 text-center" glowColor={`${stat.color}33`}>
              <div className="text-5xl font-bold tracking-tight" style={{ color: stat.color }}>
                <AnimatedCounter target={stat.value} prefix={stat.prefix} suffix={stat.suffix} />
              </div>
              <div className="mt-2 text-[11px] uppercase tracking-widest text-slate-500">{stat.label}</div>
            </GlowCard>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-2xl text-center text-sm text-slate-500">
          50 RMs × 3 meetings/day × 18 min saved = <span className="font-bold text-white">2,700 hours/month reclaimed</span>.
          That's less than one analyst's salary in infrastructure cost.
        </p>
      </div>
    </section>
  );
}

/* ─────────────────────────────── How it works ─────────────────────────────── */

function HowItWorks() {
  return (
    <section id="how" className="relative py-20 md:py-28">
      <div className="mx-auto max-w-5xl px-4 md:px-8">
        <div className="mb-16 text-center">
          <Eyebrow color="violet">3 minutes to a working setup</Eyebrow>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
            From OAuth to first briefing call.
          </h2>
        </div>

        <div className="relative">
          {/* Center timeline */}
          <div className="absolute left-1/2 top-0 hidden h-full w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-white/[0.08] to-transparent md:block" />

          <div className="space-y-12">
            {[
              {
                step: "01",
                title: "Connect your CRM in 30 seconds",
                desc: "Click 'Connect HubSpot'. Real OAuth dance. Tokens encrypted at rest. Done.",
              },
              {
                step: "02",
                title: "Auto-provision the custom fields",
                desc: "SYNC scans your CRM for missing properties. One click creates them via the metadata API.",
              },
              {
                step: "03",
                title: "Make the first call",
                desc: "Trigger 'Sync Now' from the dashboard or dial the Ringg number. 45-second briefing, auto-logged back to the CRM.",
              },
            ].map((s, i) => (
              <div key={s.step} className={`relative flex flex-col items-center gap-6 md:flex-row ${i % 2 === 0 ? "md:flex-row" : "md:flex-row-reverse"}`}>
                <GlowCard className="flex-1 p-6">
                  <div className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">Step {s.step}</div>
                  <h3 className="mt-2 text-xl font-bold text-white">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{s.desc}</p>
                </GlowCard>

                {/* Center node */}
                <div className="relative z-10 hidden md:block">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/[0.1] bg-[#020817] text-sm font-bold text-indigo-300 shadow-[0_0_30px_rgba(99,102,241,0.4)]">
                    {s.step}
                  </div>
                </div>

                <div className="hidden flex-1 md:block" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Final CTA ─────────────────────────────── */

function FinalCta({ onCta }: { onCta: () => void }) {
  return (
    <section className="relative py-20 md:py-28">
      <div className="mx-auto max-w-4xl px-4 md:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-white/[0.08]">
          {/* Background gradient */}
          <div className="absolute inset-0"
            style={{ background: "radial-gradient(ellipse at top, rgba(99,102,241,0.3), transparent 70%), linear-gradient(180deg, #0f172a, #020817)" }}
          />
          {/* Grid overlay */}
          <div className="absolute inset-0 opacity-30">
            <svg width="100%" height="100%">
              <defs>
                <pattern id="cta-grid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <path d="M 30 0 L 0 0 0 30" fill="none" stroke="white" strokeWidth="0.3" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#cta-grid)" />
            </svg>
          </div>

          <div className="relative px-8 py-16 text-center md:px-16 md:py-20">
            <Eyebrow color="indigo">Ship it on stage</Eyebrow>
            <h2 className="mt-4 text-3xl font-bold tracking-tight text-white md:text-5xl">
              Stop reading the CRM.<br />Start <AuroraText>knowing</AuroraText> the client.
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-base text-slate-400">
              The full demo runs offline, ships with 5 richly detailed clients,
              and uses the same code path that talks to a real LeadSquared instance.
            </p>

            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <ShimmerButton onClick={onCta} className="px-6 py-3 text-sm">
                <Play className="h-4 w-4" />
                Launch Dashboard
                <ArrowRight className="h-4 w-4" />
              </ShimmerButton>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.02] px-5 py-3 text-sm font-medium text-slate-300 transition-all hover:bg-white/[0.06] hover:text-white">
                <Github className="h-4 w-4" />View source
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Footer ─────────────────────────────── */

function LandingFooter() {
  return (
    <footer className="border-t border-white/[0.04] py-10">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 text-center md:flex-row md:text-left md:px-8">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-500/20 ring-1 ring-indigo-500/40">
            <span className="text-xs font-bold text-indigo-300">S</span>
          </div>
          <span className="text-sm font-semibold">SYNC</span>
          <span className="text-[11px] text-slate-700">·</span>
          <span className="text-[11px] text-slate-600">GrowthX Voice AI Buildathon</span>
        </div>
        <div className="text-[11px] text-slate-700">
          Built with Ringg AI · OpenAI GPT-4o · FastAPI · React + Aceternity UI
        </div>
      </div>
    </footer>
  );
}

/* ─────────────────────────────── Helpers ─────────────────────────────── */

function Eyebrow({ children, color = "indigo" }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    indigo: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
    violet: "text-violet-400 bg-violet-500/10 border-violet-500/20",
    cyan: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  };
  return (
    <span className={`inline-block rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${colors[color] ?? colors.indigo}`}>
      {children}
    </span>
  );
}
