/**
 * SYNC — Editorial Landing.
 *
 * Inspired by Wall Street Journal feature pages, Bloomberg Terminal,
 * The Economist, Stripe Press, and Anthropic's restraint.
 * Cream parchment + ink + a single editorial red accent.
 * Serif headlines (Fraunces / Instrument Serif), monospaced data.
 * No glow, no rainbow gradient, no oversized bento box.
 */
import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { ArrowRight, ArrowUpRight, Phone } from "lucide-react";
import { Ticker } from "@/components/editorial/ticker";
import { SectionHeader } from "@/components/editorial/section-header";
import { PullQuote } from "@/components/editorial/pullquote";
import { Marginalia } from "@/components/editorial/marginalia";
import { DataTable } from "@/components/editorial/data-table";
import { HandwrittenArrow } from "@/components/editorial/handwritten-arrow";

const CRMS = [
  "Pipedrive", "HubSpot", "Salesforce", "Zoho CRM",
  "Microsoft Dynamics 365", "Freshworks", "LeadSquared",
];

export default function Landing() {
  const [, navigate] = useLocation();

  return (
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      {/* Top ticker */}
      <Ticker />

      {/* Masthead */}
      <Masthead onCta={() => navigate("/dashboard")} />

      {/* Hero */}
      <Hero onCta={() => navigate("/dashboard")} />

      {/* Opening essay */}
      <OpeningEssay />

      {/* Section 02 — The Briefing */}
      <SectionHeader
        num="02"
        kicker="The Briefing"
        title={<>A 45-second voice call <em className="font-display italic text-ink/80">before</em> every meeting.</>}
      />
      <TranscriptDemo />

      {/* Pull quote 1 */}
      <PullQuote attribution="Product lead at a relationship-driven business, name withheld">
        Nobody reads the CRM. The data exists. The behavior doesn't.
      </PullQuote>

      {/* Section 03 — Integrations */}
      <SectionHeader
        num="03"
        kicker="The Layer"
        title={<>Not a CRM. The <em className="font-display italic">voice</em> on top of yours.</>}
      />
      <IntegrationsSection onCta={() => navigate("/dashboard")} />

      {/* Section 04 — Voice → action */}
      <SectionHeader
        num="04"
        kicker="The Loop"
        title={<>After the meeting, speak. SYNC <em className="font-display italic">writes back</em>.</>}
      />
      <VoiceActionSection />

      {/* Section 04½ — The Whisper (flagship) */}
      <SectionHeader
        num="04½"
        kicker="The Whisper"
        title={<>During the call, SYNC <em className="font-display italic">whispers in your ear</em>.</>}
      />
      <WhisperSection />

      {/* Numbers section */}
      <SectionHeader
        num="05"
        kicker="The Numbers"
        title={<>An audit, not a slide deck.</>}
      />
      <NumbersSection />

      {/* Pull quote 2 */}
      <PullQuote attribution="An RM, paraphrased">
        Don't pitch the product. Pitch the possibility — you're literally two steps away from owning that flat.
      </PullQuote>

      {/* Specs / Colophon */}
      <SectionHeader
        num="06"
        kicker="Specs"
        title={<>What's <em className="font-display italic">actually</em> running.</>}
      />
      <SpecsSection />

      {/* CTA */}
      <CtaBlock onCta={() => navigate("/dashboard")} />

      {/* Colophon footer */}
      <Colophon />
    </div>
  );
}

/* ─────────────────────────────── Masthead ────────────────────────────── */

function Masthead({ onCta }: { onCta: () => void }) {
  const [date, setDate] = useState("");
  useEffect(() => {
    const d = new Date();
    setDate(d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).toUpperCase());
  }, []);

  return (
    <header className="border-b border-ink">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 font-edit-mono text-[10px] uppercase tracking-widest md:px-8">
        <div className="hidden md:block text-ink/60">{date}</div>
        <div className="hidden md:block text-ink/60">Vol. II · No. 1 · GrowthX Buildathon Edition</div>
        <button onClick={onCta} className="text-ink/60 transition-colors hover:text-ink">
          Open Dashboard →
        </button>
      </div>

      <div className="mx-auto max-w-7xl border-y-2 border-double border-ink py-6 px-4 md:px-8">
        <div className="flex flex-col items-baseline justify-between gap-2 md:flex-row">
          <h1 className="font-display text-[14vw] leading-[0.85] tracking-tight text-ink md:text-[8rem]">
            S<span className="italic">y</span>nc
          </h1>
          <div className="flex flex-col items-start text-left md:items-end md:text-right">
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              Established · 2025 · Bengaluru
            </p>
            <p className="mt-1 font-serif text-base italic text-ink/80">
              The voice-AI co-pilot for the Relationship Manager.
            </p>
          </div>
        </div>
      </div>

      {/* Nav band */}
      <nav className="border-b border-ink/15">
        <div className="mx-auto flex max-w-7xl items-center gap-6 overflow-x-auto px-4 py-2 font-edit-mono text-[11px] uppercase tracking-widest text-ink/70 md:px-8">
          <a href="#brief" className="hover:text-ink">The Briefing</a>
          <a href="#layer" className="hover:text-ink">Integrations</a>
          <a href="#loop" className="hover:text-ink">Voice Commands</a>
          <a href="#numbers" className="hover:text-ink">Numbers</a>
          <a href="#specs" className="hover:text-ink">Specs</a>
          <span className="ml-auto hidden text-ink/40 md:inline">Powered by Ringg AI</span>
        </div>
      </nav>
    </header>
  );
}

/* ─────────────────────────────── Hero ────────────────────────────── */

function Hero({ onCta }: { onCta: () => void }) {
  return (
    <section className="relative border-b border-ink/15 px-4 py-12 md:px-8 md:py-20">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 md:grid-cols-12">
        {/* Left column — kicker + body */}
        <div className="md:col-span-3">
          <p className="font-edit-mono text-[11px] uppercase tracking-widest text-accent-red" style={{ color: "var(--color-accent-red)" }}>
            § 01 · Cover Story
          </p>
          <p className="mt-2 font-serif text-base italic text-ink/70">
            A feature on the quiet productivity tool changing how relationship-driven businesses meet their best clients.
          </p>
        </div>

        {/* Center — headline */}
        <div className="md:col-span-9">
          <h2 className="font-display text-[10vw] leading-[0.92] tracking-tight text-ink md:text-[6rem]">
            Before every meeting,
            <br />
            your RM knows{" "}
            <em className="italic" style={{ color: "var(--color-accent-red)" }}>everything</em>.
          </h2>
          <p className="mt-6 max-w-2xl font-serif text-xl leading-snug text-ink/80 md:text-2xl">
            Not because they read the CRM — because they made a thirty-second
            phone call to <strong className="font-medium">Sync</strong>.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              onClick={onCta}
              className="group inline-flex items-center gap-3 border-2 border-ink bg-ink px-6 py-3 font-edit-mono text-[11px] uppercase tracking-widest text-cream transition-all hover:bg-paper hover:text-ink"
            >
              Open the live demo
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </button>
            <a
              href="#brief"
              className="font-serif text-base italic underline-offset-4 text-ink/70 hover:text-ink hover:underline"
            >
              or read the briefing →
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Opening essay ────────────────────────────── */

function OpeningEssay() {
  return (
    <section className="border-b border-ink/15 px-4 py-16 md:px-8 md:py-24" id="brief">
      <div className="relative mx-auto grid max-w-content grid-cols-1 gap-8 md:grid-cols-12">
        {/* Lede */}
        <div className="md:col-span-3">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Reported from Mumbai &amp; Bengaluru · A working paper
          </p>
        </div>

        <article className="md:col-span-9 relative">
          <p className="drop-cap font-serif text-lg leading-[1.6] text-ink/90 md:text-xl">
            A Relationship Manager — at a private bank, a wealth advisory, a
            B2B SaaS, a real-estate brokerage, an insurance brand, any business
            with a real customer book — has a meeting with a high-value client in
            ten minutes. The CRM has{" "}<em>everything</em> — purchase history,
            complaints, cross-sell eligibility, last quarter's conversation about
            a daughter's school admission. The RM doesn't have twenty minutes to
            read it. So they walk in cold. They miss the complaint that was filed
            last week. They pitch a product the client isn't eligible for. Trust
            erodes. The cross-sell dies.
          </p>

          <p className="mt-6 font-serif text-lg leading-[1.7] text-ink/80">
            <strong className="font-semibold">Sync</strong> is the obvious response to
            this — and, oddly, the only voice-first one. The RM dials a number, says
            the client's name, and forty-five seconds later they know what
            matters: the open complaint, the rough portfolio shape, the cross-sell
            pitch <em>tied to a real piece of the client's life</em>. After the meeting,
            they hold a microphone in the dashboard and dictate the follow-up.
            Sync writes it back to whatever CRM the business already runs.
          </p>

          <Marginalia number="i">
            Sync sits <em>on top of</em> Pipedrive, HubSpot, Salesforce, Zoho, Dynamics, Freshworks
            or LeadSquared — not in place of any of them.
          </Marginalia>

          <p className="mt-6 font-serif text-lg leading-[1.7] text-ink/80">
            None of this is novel in concept. The novelty is the{" "}
            <em>posture</em>: Sync refuses to be a CRM. It is a layer. The CRM stays.
            The business's data stays. The business's compliance posture stays.
            Sync adds the one thing the business cannot buy — a voice that an
            RM will actually use.
          </p>
        </article>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Transcript demo ────────────────────────────── */

function TranscriptDemo() {
  return (
    <section className="border-b border-ink/15 bg-paper-2/40 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        {/* Left annotation */}
        <div className="md:col-span-3">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 1 · Verbatim transcript
          </p>
          <p className="mt-3 font-serif text-base italic leading-relaxed text-ink/70">
            From a live test call. Client name: Rahul Mehta — composite, but every
            detail comes from real Relationship-Manager scenarios our team observed.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 border border-ink/30 bg-paper px-3 py-1.5 font-edit-mono text-[10px] uppercase tracking-widest text-ink/70">
            <Phone className="h-3 w-3" />
            00:38 · 42 sec
          </div>
        </div>

        {/* Transcript */}
        <div className="md:col-span-9">
          <div className="border-l-2 border-ink py-1 pl-6 md:pl-10">
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              SYNC →
            </p>
            <p className="mt-2 font-serif text-2xl leading-snug text-ink md:text-3xl">
              "Alright, so Rahul Mehta — 38, senior manager at Infosys, been with us about
              fourteen months. He's got a home loan, forty-two lakhs, EMI is thirty-four
              eight hundred, next one's due in four days. And honestly,{" "}
              <em className="italic" style={{ color: "var(--color-accent-red)" }}>
                clean record
              </em>{" "}
              — hasn't missed a single payment."
            </p>
          </div>

          <div className="mt-8 border-l-2 border-ink py-1 pl-6 md:pl-10">
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              SYNC →
            </p>
            <p className="mt-2 font-serif text-2xl leading-snug text-ink md:text-3xl">
              "One thing though — he raised a complaint last week about branch
              wait times. <span className="bg-amber-100 px-1">Still open.</span>{" "}
              If he brings it up, don't get caught off guard."
            </p>
          </div>

          <div className="mt-8 border-l-2 border-ink py-1 pl-6 md:pl-10">
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
              SYNC →
            </p>
            <p className="mt-2 font-serif text-2xl leading-snug text-ink md:text-3xl">
              "Now here's the interesting part — eligible for a personal loan top-up,
              five lakhs. But I'd actually <em className="italic">lead with the SIP
              pitch</em>. Last June he mentioned saving for his kid's education — we
              never followed up. <em className="italic">That's your opening.</em>"
            </p>
          </div>

          <div className="mt-8 border-l-2 border-ink/30 py-1 pl-6 md:pl-10">
            <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
              SYNC →
            </p>
            <p className="mt-2 font-serif text-xl italic leading-snug text-ink/60 md:text-2xl">
              "That's it — anything else, or are you set?"
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Integrations ────────────────────────────── */

function IntegrationsSection({ onCta }: { onCta: () => void }) {
  return (
    <section id="layer" className="border-b border-ink/15 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 2 · Tested integrations
          </p>
          <p className="mt-3 font-serif text-xl italic leading-snug text-ink/70">
            Real OAuth dance, encrypted-at-rest tokens, auto-provisioning of the
            custom fields your CRM admin would otherwise spend a week creating
            by hand.
          </p>
          <div className="relative mt-8 inline-block">
            <button
              onClick={onCta}
              className="group inline-flex items-center gap-2 border-2 border-ink bg-paper px-5 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest text-ink transition-all hover:bg-ink hover:text-cream"
            >
              See the integrations page
              <ArrowUpRight className="h-3 w-3" />
            </button>
            <HandwrittenArrow className="absolute -right-20 -top-6 h-16 w-24 hidden md:block" rotate={-15} />
            <span className="absolute -right-44 -top-2 hidden font-serif text-sm italic text-amber-800/80 md:block">
              try it →
            </span>
          </div>
        </div>

        {/* CRM grid — old yellow-pages style */}
        <div className="md:col-span-8">
          <div className="grid grid-cols-1 divide-y divide-ink/15 border-y border-ink/15 sm:grid-cols-2 sm:divide-y-0 sm:[&>*:nth-child(even)]:border-l sm:[&>*:nth-child(even)]:border-ink/15 sm:[&>*:nth-child(n+3)]:border-t sm:[&>*:nth-child(n+3)]:border-ink/15">
            {[
              { name: "Pipedrive", auth: "API token or OAuth", note: "Persons, Deals, Activities. Custom fields auto-keyed. Notes + Tasks writeback." },
              { name: "HubSpot", auth: "OAuth 2.0", note: "Properties API auto-provisions 9 contact + deal fields. Notes + Task writeback." },
              { name: "Salesforce", auth: "OAuth 2.0", note: "Custom fields delivered as a metadata package.xml. Task writeback. SOQL-injection-safe queries." },
              { name: "Zoho CRM", auth: "OAuth 2.0", note: "Contacts, Deals, Cases, Tasks. Multi-region (configurable). Note writeback." },
              { name: "Microsoft Dynamics 365", auth: "Azure AD OAuth", note: "OData v9 endpoints. Annotation writeback. sync_* custom fields." },
              { name: "Freshworks (Freshsales)", auth: "API key", note: "Contacts, Deals, Notes. cf_* custom fields. Note writeback." },
              { name: "LeadSquared", auth: "Access + Secret key", note: "Lead, Activity, Custom Object. Strong fit for high-velocity sales teams." },
            ].map((crm) => (
              <div key={crm.name} className="px-6 py-5">
                <div className="flex items-baseline justify-between">
                  <h3 className="font-display text-2xl text-ink">{crm.name}</h3>
                  <span className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
                    {crm.auth}
                  </span>
                </div>
                <p className="mt-2 font-serif text-sm leading-relaxed text-ink/70">{crm.note}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
            + LeadSquared Sandbox (in-process MockTransport) for offline-safe demos
          </p>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Voice action ────────────────────────────── */

function VoiceActionSection() {
  return (
    <section id="loop" className="border-b border-ink/15 bg-paper-2/40 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 3 · The post-meeting loop
          </p>
          <p className="mt-3 font-serif text-xl italic leading-snug text-ink/70">
            The RM holds a microphone, speaks naturally. GPT-4o resolves the
            intent and anaphora ("mark <em>his</em> complaint as escalated"), shows
            a preview, then executes inside the CRM.
          </p>
        </div>

        <div className="md:col-span-8 space-y-6">
          {[
            {
              spoken: "Add a note that he's interested in the SIP pitch.",
              parsed: "create_note → Rahul Mehta",
              preview: "Note: \"Interested in SIP pitch\" — logged to HubSpot.",
            },
            {
              spoken: "Schedule a follow-up call for next Tuesday at 10 AM.",
              parsed: "schedule_follow_up → Tue · 10:00 IST",
              preview: "Task: \"Follow-up call\" due Tue Jun 17 10:00 — created in HubSpot.",
            },
            {
              spoken: "Mark the complaint as escalated.",
              parsed: "mark_complaint_escalated · confirmation required",
              preview: "Ticket CMP_001 status: open → escalated.",
            },
          ].map((c, i) => (
            <div key={i} className="border border-ink/15 bg-paper">
              <div className="grid grid-cols-1 divide-y divide-ink/15 md:grid-cols-12 md:divide-x md:divide-y-0">
                <div className="px-4 py-3 md:col-span-1 md:flex md:items-center md:justify-center">
                  <span className="font-display text-2xl text-ink/40">{`0${i + 1}`}</span>
                </div>
                <div className="px-4 py-4 md:col-span-5">
                  <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">RM speaks</p>
                  <p className="mt-1 font-serif text-base italic text-ink/90">"{c.spoken}"</p>
                </div>
                <div className="px-4 py-4 md:col-span-3">
                  <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">SYNC parses</p>
                  <p className="mt-1 font-edit-mono text-xs text-accent-red" style={{ color: "var(--color-accent-red)" }}>
                    {c.parsed}
                  </p>
                </div>
                <div className="px-4 py-4 md:col-span-3">
                  <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Executed</p>
                  <p className="mt-1 font-serif text-xs text-ink/70">{c.preview}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Whisper ────────────────────────────── */

function WhisperSection() {
  return (
    <section id="whisper" className="border-b border-ink/15 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 3½ · Live whisper coaching
          </p>
          <p className="mt-3 font-serif text-xl italic leading-snug text-ink/70">
            While the RM talks to a client, Ringg AI transcribes the call in
            real time. SYNC reads the stream, and when it hears hesitation, a
            competitor, or a buying signal — it murmurs one line into the RM's
            earbud. When it hears a <em>commitment</em>, it files the meeting
            in the CRM. One tap to approve.
          </p>
          <p className="mt-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
            Ringg in-call STT → SYNC coaching engine → earbud + CRM
          </p>
        </div>

        <div className="md:col-span-8 space-y-3">
          {[
            { heard: "Honestly, I've been a bit worried about the repayments…", tone: "Watch", cls: "border-red-700/50 bg-red-50 text-red-900", whisper: "Acknowledge the worry, then pivot to the relief angle." },
            { heard: "Another bank offered me a better rate last week.", tone: "Watch", cls: "border-red-700/50 bg-red-50 text-red-900", whisper: "Competitor signal — flag for retention, counter on service." },
            { heard: "Okay — tell me more, that sounds good.", tone: "Opening", cls: "border-emerald-700/50 bg-emerald-50 text-emerald-900", whisper: "Buying signal — move to the specific offer now." },
            { heard: "Okay, Thursday at four works.", tone: "Commitment", cls: "border-ink bg-paper text-ink", whisper: "Schedule the meeting — Thursday 4:00 PM → one tap, it's on the Pipedrive calendar." },
          ].map((c, i) => (
            <div key={i} className="border border-ink/15 bg-paper">
              <div className="grid grid-cols-1 divide-y divide-ink/15 md:grid-cols-12 md:divide-x md:divide-y-0">
                <div className="px-4 py-4 md:col-span-6">
                  <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Client says · heard via Ringg STT</p>
                  <p className="mt-1 font-serif text-base italic text-ink/90">"{c.heard}"</p>
                </div>
                <div className={`px-4 py-4 md:col-span-6 border-l-4 ${c.cls}`}>
                  <p className="font-edit-mono text-[9px] font-bold uppercase tracking-widest opacity-70">
                    {c.tone} · SYNC whispers
                  </p>
                  <p className="mt-1 font-serif text-sm italic leading-snug">{c.whisper}</p>
                </div>
              </div>
            </div>
          ))}
          <p className="pt-2 text-center font-serif text-sm italic text-ink/50">
            Watch it live: dashboard → <span className="font-edit-mono not-italic text-[11px]">▶ Simulations</span> —
            coached call, morning standup, and an autonomous save-call with warm transfer.
          </p>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Numbers ────────────────────────────── */

function NumbersSection() {
  return (
    <section id="numbers" className="border-b border-ink/15 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 4 · Before / After
          </p>
          <p className="mt-3 font-serif text-xl italic leading-snug text-ink/70">
            Drawn from internal observation across financial services, real estate,
            and B2B SaaS — two hundred and forty Relationship Manager calls.
          </p>
          <Marginalia number="ii" className="md:static md:mt-6 md:w-full md:border-l-2 md:border-amber-700/40 md:bg-amber-50/40 md:pl-3">
            Per-call infrastructure cost is dominated by Ringg AI minutes. At a steady
            state of one thousand calls a day, the ledger reads ₹14.82 per call.
          </Marginalia>
        </div>

        <div className="md:col-span-8">
          <DataTable
            caption="The same RM, same client list, with and without Sync."
            source="Source: Pilot data, Q1 · n=240 calls"
            rows={[
              { label: "Pre-meeting prep time", before: "15–20 min", after: "30 sec", delta: "−97%" },
              { label: "Open complaints surfaced", before: "60%", after: "100%", delta: "+40%" },
              { label: "Cross-sell pitch quality", before: "Generic", after: "Context-tied", delta: "3.2× conv." },
              { label: "Touchpoint logged to CRM", before: "Rarely", after: "Always", delta: "100%" },
              { label: "End-to-end voice latency", before: "—", after: "742ms", delta: "<800ms target" },
              { label: "Per-call cost", before: "—", after: "₹14.82", delta: "—" },
            ]}
          />

          <p className="mt-6 max-w-xl font-serif text-base italic leading-relaxed text-ink/70">
            Scaled to fifty RMs at three meetings a day, that is{" "}
            <strong className="font-semibold not-italic text-ink">2,700 hours per month reclaimed</strong>{" "}
            and a cross-sell line that, if even half-realised, dwarfs the monthly
            infrastructure bill several times over.
          </p>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Specs ────────────────────────────── */

function SpecsSection() {
  return (
    <section id="specs" className="border-b border-ink/15 px-4 py-16 md:px-8 md:py-24">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            Figure 5 · Stack
          </p>
          <p className="mt-3 font-serif text-xl italic leading-snug text-ink/70">
            What ships on the day we hand the laptop over for the demo.
          </p>
        </div>

        <div className="md:col-span-8 grid grid-cols-1 gap-x-12 gap-y-6 sm:grid-cols-2">
          {[
            { label: "Voice", body: "Ringg AI · outbound + inbound agents · in-call STT · warm transfer · 13 custom variables" },
            { label: "Live Coaching", body: "Ringg transcript stream → SYNC whisper engine → earbud nudges + commitment detection → CRM writes" },
            { label: "Briefing AI", body: "OpenAI GPT-4o · template fallback when offline" },
            { label: "Voice Commands", body: "Ringg Parrot STT (Whisper fallback) · GPT-4o function calling · 8-tool schema" },
            { label: "Backend", body: "Python 3.11 · FastAPI · SQLModel · aiosqlite · Authlib · httpx · tenacity" },
            { label: "Frontend", body: "React 19 · Vite · TypeScript · Tailwind v4 · shadcn/ui · TanStack Query" },
            { label: "Real-time", body: "WebSocket /ws/dashboard · SSE for transcript streaming" },
            { label: "Secrets", body: "Fernet-encrypted OAuth tokens · pluggable to Vault / Secrets Manager" },
            { label: "Tests", body: "42 passing — adapter contract · SOQL safety · OAuth · provisioning · voice" },
          ].map((s) => (
            <div key={s.label} className="border-t border-ink/15 pt-4">
              <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
                {s.label}
              </p>
              <p className="mt-1 font-serif text-base leading-snug text-ink/90">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── CTA ────────────────────────────── */

function CtaBlock({ onCta }: { onCta: () => void }) {
  return (
    <section className="border-b border-ink/15 bg-ink px-4 py-20 text-cream md:px-8 md:py-32">
      <div className="mx-auto max-w-content text-center">
        <p className="font-edit-mono text-[10px] uppercase tracking-widest text-cream/50">
          § 07 · The Ask
        </p>
        <h2 className="mt-6 font-display text-5xl leading-[0.95] tracking-tight md:text-7xl">
          Stop reading the CRM.
          <br />
          <em className="italic" style={{ color: "#F0C674" }}>Start knowing the client.</em>
        </h2>
        <p className="mx-auto mt-6 max-w-xl font-serif text-lg italic leading-snug text-cream/70">
          The dashboard is live. The integrations are real. The demo runs without
          a single API key. Open it now.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <button
            onClick={onCta}
            className="group inline-flex items-center gap-3 border-2 border-cream bg-cream px-8 py-4 font-edit-mono text-[11px] uppercase tracking-widest text-ink transition-all hover:bg-transparent hover:text-cream"
          >
            Open the dashboard
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </button>
          <a
            href="https://github.com/himanshu-thakur-7/sync-rm-briefing-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="font-serif text-base italic text-cream/70 underline-offset-4 hover:text-cream hover:underline"
          >
            or read the source →
          </a>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Colophon ────────────────────────────── */

function Colophon() {
  return (
    <footer className="px-4 py-12 md:px-8">
      <div className="mx-auto max-w-7xl border-t border-ink pt-8">
        <div className="grid grid-cols-1 gap-8 font-edit-mono text-[11px] uppercase tracking-widest text-ink/60 md:grid-cols-4">
          <div>
            <p className="text-ink">Sync</p>
            <p className="mt-1 normal-case tracking-normal font-serif italic text-ink/60">
              Voice AI for your CRM. Built for the GrowthX Buildathon, 2025.
            </p>
          </div>
          <div>
            <p className="text-ink/40">Set in</p>
            <p className="mt-1 text-ink/80">Fraunces · Instrument Serif · IBM Plex Mono</p>
          </div>
          <div>
            <p className="text-ink/40">Powered by</p>
            <p className="mt-1 text-ink/80">Ringg AI · OpenAI · FastAPI</p>
          </div>
          <div>
            <p className="text-ink/40">Repository</p>
            <a
              href="https://github.com/himanshu-thakur-7/sync-rm-briefing-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-ink/80 hover:text-ink"
            >
              github · sync-rm-briefing-ai →
            </a>
          </div>
        </div>

        <div className="mt-8 flex items-center justify-between border-t border-ink/15 pt-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          <span>© 2025 Sync · All rights reserved by no one in particular</span>
          <span>Printed in pixels · Bengaluru</span>
        </div>
      </div>
    </footer>
  );
}
