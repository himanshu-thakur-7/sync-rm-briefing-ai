import { useEffect } from "react";
import { Mic, MicOff, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
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
          title: "✓ CRM action executed",
          description: `${humanizeTool(tool)} logged${actionId ? ` (${actionId.slice(0, 8)})` : ""}.`,
        });
      },
    });

  useEffect(() => {
    if (state.status === "done") {
      const t = setTimeout(reset, 2500);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [state.status, reset]);

  useEffect(() => {
    if (state.status === "error" && state.error) {
      toast({ title: "Voice command failed", description: state.error, variant: "destructive" });
      const t = setTimeout(reset, 2000);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [state.status, state.error, toast, reset]);

  const { status } = state;
  const isHeld = status === "listening";

  return (
    <>
      <div className={cn("flex items-center gap-2", className)}>
        {status === "listening" && state.transcript && (
          <span className="max-w-[180px] truncate text-[11px] italic text-slate-400">
            "{state.transcript}"
          </span>
        )}
        {status === "parsing" && <span className="text-[11px] text-slate-500 animate-pulse">Parsing…</span>}
        {status === "executing" && <span className="text-[11px] text-slate-500 animate-pulse">Executing…</span>}

        <button
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          className={cn(
            "relative flex h-8 w-8 items-center justify-center rounded-lg border transition-all",
            isHeld
              ? "border-indigo-500/50 bg-indigo-500/20 ring-2 ring-indigo-500/40"
              : "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]",
            status === "done" && "border-emerald-500/40 bg-emerald-500/15",
            status === "error" && "border-red-500/40 bg-red-500/15",
          )}
          title="Hold to speak a CRM command"
        >
          {isHeld && (
            <span className="absolute inset-0 rounded-lg animate-ping bg-indigo-500/30" />
          )}
          {status === "parsing" || status === "executing"
            ? <Loader2 className="relative h-3.5 w-3.5 animate-spin text-slate-300" />
            : status === "done"
              ? <CheckCircle2 className="relative h-3.5 w-3.5 text-emerald-400" />
              : status === "error"
                ? <XCircle className="relative h-3.5 w-3.5 text-red-400" />
                : isHeld
                  ? <MicOff className="relative h-3.5 w-3.5 text-indigo-300" />
                  : <Mic className="relative h-3.5 w-3.5 text-slate-400" />
          }
        </button>
      </div>

      <Dialog open={status === "confirming"} onOpenChange={(o) => !o && cancelCommand()}>
        <DialogContent className="border-white/[0.08] bg-[#0d1117] sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle className="text-xs font-semibold uppercase tracking-widest text-indigo-400">
              Confirm CRM Action
            </DialogTitle>
            <DialogDescription className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
              {state.parsed?.dry_run_preview ?? ""}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-[11px]">
            <span className="font-semibold text-slate-500">Transcript:</span>{" "}
            <span className="text-slate-300">"{state.transcript}"</span>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" className="border-white/[0.08] bg-white/[0.02] text-slate-300 hover:bg-white/[0.06]" onClick={cancelCommand}>
              Cancel
            </Button>
            <Button className="bg-indigo-600 hover:bg-indigo-500" onClick={() => executeCommand()}>
              Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function humanizeTool(tool: string) {
  const m: Record<string, string> = {
    create_note: "Note",
    create_task: "Task",
    update_contact_field: "Contact update",
    mark_complaint_resolved: "Complaint resolved",
    mark_complaint_escalated: "Complaint escalated",
    schedule_follow_up: "Follow-up scheduled",
    log_meeting_outcome: "Meeting outcome",
    flag_for_manager_review: "Manager flag",
  };
  return m[tool] ?? tool;
}
