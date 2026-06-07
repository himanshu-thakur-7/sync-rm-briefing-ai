/**
 * MorningBrief — § The Daily Standup.
 * Editorial schedule manager + history viewer for SYNC's autonomous
 * morning briefing calls.
 */
import { useEffect, useState, useCallback } from "react";
import { useLocation } from "wouter";
import { ArrowLeft, Plus, Phone, Loader2, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { useConnection } from "@/lib/connection-context";

interface Schedule {
  id: number;
  rm_name: string;
  rm_phone: string;
  connection_id: string;
  hour_local: number;
  minute_local: number;
  weekday_mask: number;
  timezone: string;
  company_name: string;
  language_style: string;
  enabled: boolean;
  last_called_at: string | null;
  next_call_at: string | null;
}

interface CallHistory {
  id: number;
  schedule_id: number;
  call_id: string;
  started_at: string | null;
  ended_at: string | null;
  questions_asked: number;
  actions_executed: number;
  summary: string;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function MorningBrief() {
  const [, navigate] = useLocation();
  const { connectionId } = useConnection();
  const { toast } = useToast();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [history, setHistory] = useState<CallHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [triggering, setTriggering] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const sResp = await fetch("/api/v1/morning-brief/schedules");
      if (!sResp.ok) throw new Error(`schedules: HTTP ${sResp.status}`);
      const s = await sResp.json();
      setSchedules(Array.isArray(s) ? s : []);

      const hResp = await fetch("/api/v1/morning-brief/calls?limit=20");
      if (!hResp.ok) throw new Error(`calls: HTTP ${hResp.status}`);
      const h = await hResp.json();
      setHistory(Array.isArray(h) ? h : []);
    } catch (e: any) {
      // Keep the page usable even if backend is unreachable
      setSchedules([]);
      setHistory([]);
      toast({
        title: "Couldn't reach the backend",
        description: e?.message ?? String(e),
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const handleTrigger = async (id: number) => {
    setTriggering(id);
    try {
      const r = await fetch(`/api/v1/morning-brief/schedules/${id}/trigger`, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
      const d = await r.json();
      toast({
        title: "Standup call placed",
        description: `Call ID ${(d.call_id ?? "").slice(0, 16)}. Watch the live feed for the transcript.`,
      });
      // Re-poll history after a short delay so the simulated convo can finish
      setTimeout(load, 12000);
    } catch (e: any) {
      toast({ title: "Trigger failed", description: e?.message ?? String(e), variant: "destructive" });
    } finally {
      setTriggering(null);
    }
  };

  const handleToggle = async (s: Schedule) => {
    await fetch(`/api/v1/morning-brief/schedules/${s.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !s.enabled }),
    });
    load();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Disable this standup schedule?")) return;
    await fetch(`/api/v1/morning-brief/schedules/${id}`, { method: "DELETE" });
    load();
  };

  return (
    <div className="min-h-screen bg-paper-grain text-ink antialiased">
      {/* Top strip */}
      <div className="border-b border-ink/15 bg-paper">
        <div className="mx-auto flex h-8 max-w-[1100px] items-center justify-between px-4 font-edit-mono text-[10px] uppercase tracking-widest text-ink/60 md:px-6">
          <button onClick={() => navigate("/dashboard")} className="inline-flex items-center gap-1.5 hover:text-ink">
            <ArrowLeft className="h-3 w-3" />
            Back to the Briefing Desk
          </button>
          <span>§ The Daily Standup</span>
        </div>
      </div>

      <main className="mx-auto max-w-[1100px] px-4 py-10 md:px-6 md:py-14">
        {/* Title */}
        <header className="border-b border-ink/15 pb-8">
          <p className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
            § Standing Feature · The Daily Standup
          </p>
          <h1 className="mt-2 font-display text-5xl leading-[0.95] text-ink md:text-6xl">
            Your <em className="italic">morning</em>, on the phone.
          </h1>
          <p className="mt-3 max-w-2xl font-serif text-lg italic leading-snug text-ink/70">
            Each morning at your scheduled time, SYNC dials you, walks today's
            CRM agenda, answers your questions, and creates the follow-ups you
            ask for — mid-conversation, while you're still on the call.
          </p>

          <div className="mt-6">
            <button
              onClick={() => setCreateOpen(true)}
              className="inline-flex items-center gap-2 border-2 border-ink bg-ink px-5 py-2.5 font-edit-mono text-[11px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink"
            >
              <Plus className="h-3.5 w-3.5" />
              Schedule a brief
            </button>
          </div>
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
          </div>
        ) : (
          <>
            {/* Schedules */}
            <section className="mt-10">
              <h2 className="border-t border-ink py-3 font-edit-mono text-[11px] uppercase tracking-widest text-ink/70">
                § A · Active Schedules
              </h2>
              {schedules.length === 0 ? (
                <div className="border-y border-ink/15 px-4 py-12 text-center font-serif italic text-ink/40">
                  No standups scheduled. Click "Schedule a brief" above to set one up.
                </div>
              ) : (
                <div className="border-y border-ink/15 divide-y divide-ink/15">
                  {schedules.map(s => (
                    <ScheduleRow
                      key={s.id} s={s}
                      onTrigger={() => handleTrigger(s.id)}
                      onToggle={() => handleToggle(s)}
                      onDelete={() => handleDelete(s.id)}
                      triggering={triggering === s.id}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* History */}
            <section className="mt-12">
              <h2 className="border-t border-ink py-3 font-edit-mono text-[11px] uppercase tracking-widest text-ink/70">
                § B · Recent Standup Calls
              </h2>
              {history.length === 0 ? (
                <div className="border-y border-ink/15 px-4 py-10 text-center font-serif italic text-ink/40">
                  Standup history will appear here after the first call.
                </div>
              ) : (
                <div className="border-y border-ink/15 divide-y divide-ink/10">
                  {history.map(h => (
                    <div key={h.id} className="grid grid-cols-12 gap-3 px-1 py-3 font-edit-mono text-[11px]">
                      <span className="col-span-3 text-ink/60">
                        {h.started_at ? new Date(h.started_at).toLocaleString("en-IN") : "—"}
                      </span>
                      <span className="col-span-3 truncate text-ink">{h.call_id}</span>
                      <span className="col-span-2 text-ink/80">
                        {h.questions_asked}{" Q · "}{h.actions_executed}{" A"}
                      </span>
                      <span className="col-span-4 truncate font-serif italic text-ink/70">
                        {h.summary || "—"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        <p className="mt-12 border-t border-ink/15 pt-6 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          Mid-call function tools (ask_crm, log_action) wired to /api/v1/morning-brief/&#123;call_id&#125;/&#123;ask|act&#125; ·
          Conversational Ringg agent · Falls back to keyless simulation when no Ringg key
        </p>
      </main>

      <CreateScheduleDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={load}
        defaultConnectionId={connectionId}
      />
    </div>
  );
}

function ScheduleRow({
  s, onTrigger, onToggle, onDelete, triggering,
}: {
  s: Schedule; onTrigger: () => void; onToggle: () => void; onDelete: () => void; triggering: boolean;
}) {
  const time = `${String(s.hour_local).padStart(2, "0")}:${String(s.minute_local).padStart(2, "0")}`;
  const days = WEEKDAYS.map((d, i) => ({ d, on: (s.weekday_mask >> i) & 1 }));
  const nextStr = s.next_call_at ? new Date(s.next_call_at).toLocaleString("en-IN") : "—";
  return (
    <div className="grid grid-cols-12 items-center gap-3 px-1 py-4">
      <div className="col-span-12 md:col-span-4">
        <div className="font-serif text-base text-ink">{s.rm_name}</div>
        <div className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">
          {s.rm_phone} · {s.company_name}
        </div>
      </div>
      <div className="col-span-6 md:col-span-2">
        <div className="font-edit-mono text-xl tabular-nums text-ink">{time}</div>
        <div className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/50">{s.timezone}</div>
      </div>
      <div className="col-span-6 md:col-span-3">
        <div className="flex gap-0.5 font-edit-mono text-[10px] uppercase tracking-widest">
          {days.map(({ d, on }) => (
            <span key={d} className={on ? "text-ink" : "text-ink/20"}>{d.slice(0, 1)}</span>
          ))}
        </div>
        <div className="mt-1 font-edit-mono text-[10px] uppercase tracking-widest text-ink/40">
          {s.enabled ? `Next · ${nextStr}` : "Disabled"}
        </div>
      </div>
      <div className="col-span-12 md:col-span-3 flex justify-end gap-2">
        <button
          onClick={onTrigger}
          disabled={triggering}
          className="inline-flex items-center gap-1 border-2 border-ink bg-ink px-3 py-1.5 font-edit-mono text-[10px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink disabled:opacity-50"
        >
          {triggering ? <Loader2 className="h-3 w-3 animate-spin" /> : <Phone className="h-3 w-3" />}
          Trigger
        </button>
        <button
          onClick={onToggle}
          className="inline-flex items-center justify-center border border-ink/30 px-2 py-1.5 text-ink/60 hover:bg-ink/[0.05]"
          title={s.enabled ? "Disable" : "Enable"}
        >
          {s.enabled ? <ToggleRight className="h-3.5 w-3.5" /> : <ToggleLeft className="h-3.5 w-3.5" />}
        </button>
        <button
          onClick={onDelete}
          className="inline-flex items-center justify-center border border-ink/30 px-2 py-1.5 text-red-700 hover:bg-red-50"
          title="Delete"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function CreateScheduleDialog({
  open, onClose, onCreated, defaultConnectionId,
}: {
  open: boolean; onClose: () => void; onCreated: () => void; defaultConnectionId: string;
}) {
  const { toast } = useToast();
  const [rmName, setRmName] = useState(import.meta.env.VITE_DEMO_RM_NAME ?? "Himanshu");
  const [rmPhone, setRmPhone] = useState(import.meta.env.VITE_DEMO_RM_PHONE ?? "+91 98765 43210");
  const [hour, setHour] = useState(7);
  const [minute, setMinute] = useState(45);
  const [weekdayMask, setWeekdayMask] = useState(31);
  const [tz, setTz] = useState("Asia/Kolkata");
  const [company, setCompany] = useState("Acme");
  const [language, setLanguage] = useState("hinglish");
  const [submitting, setSubmitting] = useState(false);

  const toggleDay = (i: number) => setWeekdayMask(m => m ^ (1 << i));

  const submit = async () => {
    if (!rmName.trim() || !rmPhone.trim() || !defaultConnectionId) {
      toast({
        title: "Missing fields",
        description: "RM name, phone, and an active CRM connection are all required.",
        variant: "destructive",
      });
      return;
    }
    if (weekdayMask === 0) {
      toast({
        title: "Pick at least one day",
        description: "Select the weekdays SYNC should dial you.",
        variant: "destructive",
      });
      return;
    }
    setSubmitting(true);
    try {
      const r = await fetch("/api/v1/morning-brief/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rm_name: rmName, rm_phone: rmPhone, connection_id: defaultConnectionId,
          hour_local: hour, minute_local: minute, weekday_mask: weekdayMask,
          timezone: tz, company_name: company, language_style: language, enabled: true,
        }),
      });
      if (!r.ok) {
        const errText = await r.text();
        throw new Error(`HTTP ${r.status}: ${errText.slice(0, 200)}`);
      }
      const created = await r.json();
      const next = created?.next_call_at
        ? new Date(created.next_call_at).toLocaleString("en-IN")
        : "soon";
      toast({ title: "Standup scheduled", description: `Next call: ${next}` });
      onCreated();
      onClose();
    } catch (e: any) {
      toast({
        title: "Couldn't schedule",
        description: e?.message ?? String(e),
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-none border-ink bg-paper sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
            § Schedule a Brief
          </DialogTitle>
          <DialogDescription className="font-serif text-sm italic text-ink/60">
            SYNC will dial you at this time on the days you pick.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 py-2">
          <div className="space-y-1.5 col-span-2">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">RM Name</Label>
            <Input value={rmName} onChange={e => setRmName(e.target.value)}
              className="rounded-none border-ink/30 bg-paper font-serif shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">RM Phone</Label>
            <Input value={rmPhone} onChange={e => setRmPhone(e.target.value)}
              className="rounded-none border-ink/30 bg-paper font-edit-mono shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Hour (0–23)</Label>
            <Input type="number" min={0} max={23} value={hour} onChange={e => setHour(parseInt(e.target.value || "0"))}
              className="rounded-none border-ink/30 bg-paper font-edit-mono shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Minute</Label>
            <Input type="number" min={0} max={59} value={minute} onChange={e => setMinute(parseInt(e.target.value || "0"))}
              className="rounded-none border-ink/30 bg-paper font-edit-mono shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Weekdays</Label>
            <div className="flex gap-1">
              {WEEKDAYS.map((d, i) => {
                const on = (weekdayMask >> i) & 1;
                return (
                  <button key={d} type="button" onClick={() => toggleDay(i)}
                    className={`flex-1 border px-2 py-1.5 font-edit-mono text-[10px] uppercase tracking-widest ${
                      on ? "border-ink bg-ink text-cream" : "border-ink/30 bg-paper text-ink/50"
                    }`}>
                    {d}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Timezone</Label>
            <Input value={tz} onChange={e => setTz(e.target.value)}
              className="rounded-none border-ink/30 bg-paper font-edit-mono shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Company</Label>
            <Input value={company} onChange={e => setCompany(e.target.value)}
              className="rounded-none border-ink/30 bg-paper font-serif shadow-none focus-visible:border-ink focus-visible:ring-0" />
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Language Style</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="rounded-none border-ink/30 bg-paper font-serif shadow-none focus:border-ink focus:ring-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-none border-ink/30 bg-paper">
                <SelectItem value="hinglish">Hinglish (default)</SelectItem>
                <SelectItem value="english_only">English only</SelectItem>
                <SelectItem value="auto">Auto (match the RM)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter className="gap-2">
          <button onClick={onClose} className="border-2 border-ink bg-paper px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink hover:bg-ink/[0.05]">
            Cancel
          </button>
          <button onClick={submit} disabled={submitting || weekdayMask === 0}
            className="border-2 border-ink bg-ink px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink disabled:opacity-50">
            {submitting ? "Scheduling…" : "Schedule"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
