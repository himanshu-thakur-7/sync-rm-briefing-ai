/**
 * Editorial voice button — a wax-seal style stamp that pulses amber when held.
 */
import { useEffect } from "react";
import { Mic, MicOff, Loader2, CheckCircle2, XCircle } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useVoiceCommand } from "@/hooks/use-voice-command";
import { useConnection } from "@/lib/connection-context";
import { cn } from "@/lib/utils";

interface Props { clientId?: string; rmName?: string; className?: string; }

export function VoiceCommandBar({ clientId, rmName, className }: Props) {
  const { connectionId } = useConnection();
  const { toast } = useToast();

  const { state, startListening, stopListening, executeCommand, cancelCommand, reset } =
    useVoiceCommand({
      connectionId, clientId, rmName,
      onExecuted: (actionId, tool) => {
        toast({
          title: "✓ Action logged",
          description: `${humanizeTool(tool)}${actionId ? ` · ${actionId.slice(0, 8)}` : ""}`,
        });
      },
    });

  useEffect(() => {
    if (state.status === "done") { const t = setTimeout(reset, 2500); return () => clearTimeout(t); }
    return undefined;
  }, [state.status, reset]);

  useEffect(() => {
    if (state.status === "error" && state.error) {
      toast({ title: "Voice command failed", description: state.error, variant: "destructive" });
      const t = setTimeout(reset, 2000); return () => clearTimeout(t);
    }
    return undefined;
  }, [state.status, state.error, toast, reset]);

  const { status } = state;
  const isHeld = status === "listening";

  return (
    <>
      <div className={cn("flex items-center gap-2", className)}>
        {status === "listening" && state.transcript && (
          <span className="max-w-[180px] truncate font-serif text-[11px] italic text-ink/70">
            "{state.transcript}"
          </span>
        )}
        {status === "parsing" && <span className="font-serif text-[11px] italic text-ink/50">parsing…</span>}
        {status === "executing" && <span className="font-serif text-[11px] italic text-ink/50">filing…</span>}

        <button
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          className={cn(
            "relative flex h-8 w-8 items-center justify-center border transition-all",
            isHeld
              ? "border-amber-700 bg-amber-100 text-amber-900"
              : "border-ink/30 bg-paper text-ink/70 hover:bg-ink hover:text-cream",
            status === "done" && "border-emerald-700 bg-emerald-50 text-emerald-800",
            status === "error" && "border-red-700 bg-red-50 text-red-800",
          )}
          title="Hold to dictate a CRM action"
        >
          {isHeld && <span className="absolute inset-0 animate-ping bg-amber-300/40" />}
          {status === "parsing" || status === "executing"
            ? <Loader2 className="relative h-3.5 w-3.5 animate-spin" />
            : status === "done"
              ? <CheckCircle2 className="relative h-3.5 w-3.5" />
              : status === "error"
                ? <XCircle className="relative h-3.5 w-3.5" />
                : isHeld
                  ? <MicOff className="relative h-3.5 w-3.5" />
                  : <Mic className="relative h-3.5 w-3.5" />
          }
        </button>
      </div>

      <Dialog open={status === "confirming"} onOpenChange={(o) => !o && cancelCommand()}>
        <DialogContent className="rounded-none border-ink bg-paper sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle className="font-edit-mono text-[10px] uppercase tracking-widest text-ink/60">
              § Confirm CRM Action
            </DialogTitle>
            <DialogDescription className="mt-3 border-l-2 border-ink py-1 pl-4 font-serif text-base italic leading-snug text-ink/90">
              {state.parsed?.dry_run_preview ?? ""}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2 border border-ink/15 bg-ink/[0.02] p-3">
            <p className="font-edit-mono text-[9px] uppercase tracking-widest text-ink/50">Transcript</p>
            <p className="mt-1 font-serif text-[12px] italic text-ink/70">"{state.transcript}"</p>
          </div>
          <DialogFooter className="gap-2">
            <button
              onClick={cancelCommand}
              className="border-2 border-ink bg-paper px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-ink hover:bg-ink/[0.05]"
            >
              Cancel
            </button>
            <button
              onClick={() => executeCommand()}
              className="border-2 border-ink bg-ink px-4 py-2 font-edit-mono text-[10px] uppercase tracking-widest text-cream hover:bg-paper hover:text-ink"
            >
              Execute
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function humanizeTool(tool: string) {
  const m: Record<string, string> = {
    create_note: "Note", create_task: "Task", update_contact_field: "Contact update",
    mark_complaint_resolved: "Complaint resolved", mark_complaint_escalated: "Complaint escalated",
    schedule_follow_up: "Follow-up scheduled", log_meeting_outcome: "Meeting outcome",
    flag_for_manager_review: "Manager flag",
  };
  return m[tool] ?? tool;
}
