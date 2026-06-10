/**
 * useVoiceCommand — encapsulates the full voice→command pipeline.
 * Uses relative API paths so Vite proxy handles dev routing, prod works directly.
 */
import { useCallback, useRef, useState } from "react";

export type CommandStatus = "idle" | "listening" | "transcribing" | "parsing" | "confirming" | "executing" | "done" | "error";

export interface ParsedCommand {
  tool: string;
  args: Record<string, unknown>;
  confirmation_required: boolean;
  dry_run_preview: string;
}

export interface VoiceCommandState {
  status: CommandStatus;
  transcript: string;
  parsed: ParsedCommand | null;
  error: string | null;
  actionId: string | null;
}

interface Options {
  connectionId: string;
  clientId?: string;
  rmName?: string;
  onExecuted?: (actionId: string, tool: string) => void;
}

// Set VITE_PREFER_SERVER_STT=1 to force the server path (Ringg Parrot STT)
// instead of the browser's free Web Speech API — useful to showcase Ringg STT
// end-to-end during the demo.
const preferServerSTT = import.meta.env.VITE_PREFER_SERVER_STT === "1";
const hasSpeechAPI = !preferServerSTT && typeof window !== "undefined"
  && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window);

export function useVoiceCommand({ connectionId, clientId, rmName, onExecuted }: Options) {
  const [state, setState] = useState<VoiceCommandState>({
    status: "idle", transcript: "", parsed: null, error: null, actionId: null,
  });

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const reset = useCallback(() => {
    setState({ status: "idle", transcript: "", parsed: null, error: null, actionId: null });
  }, []);

  const stopAndParse = useCallback(async (transcript: string) => {
    setState(s => ({ ...s, status: "parsing" }));
    try {
      const r = await fetch("/api/v1/voice/commands/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript,
          context: { active_connection_id: connectionId, active_client_id: clientId, rm_name: rmName },
        }),
      });
      const parsed: ParsedCommand = await r.json();
      setState(s => ({
        ...s, parsed,
        status: parsed.confirmation_required ? "confirming" : "executing",
      }));
      if (!parsed.confirmation_required) executeCommand(parsed);
    } catch (e: any) {
      setState(s => ({ ...s, status: "error", error: e.message }));
    }
  }, [connectionId, clientId, rmName]);

  const startListening = useCallback(() => {
    setState({ status: "listening", transcript: "", parsed: null, error: null, actionId: null });

    if (hasSpeechAPI) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const rec = new SpeechRecognition();
      rec.continuous = false; rec.interimResults = true; rec.lang = "en-IN";
      recognitionRef.current = rec;
      rec.onresult = (evt: any) => {
        const last = evt.results[evt.results.length - 1];
        const text = last[0].transcript;
        setState(s => ({ ...s, transcript: text }));
        if (last.isFinal) stopAndParse(text);
      };
      rec.onerror = (evt: any) => setState(s => ({ ...s, status: "error", error: evt.error }));
      rec.start();
    } else {
      navigator.mediaDevices?.getUserMedia({ audio: true }).then(stream => {
        const mr = new MediaRecorder(stream);
        mediaRecorderRef.current = mr;
        audioChunksRef.current = [];
        mr.ondataavailable = e => audioChunksRef.current.push(e.data);
        mr.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          setState(s => ({ ...s, status: "transcribing" }));
          try {
            const form = new FormData();
            form.append("audio", new Blob(audioChunksRef.current, { type: "audio/webm" }), "recording.webm");
            const r = await fetch("/api/v1/voice/transcribe", { method: "POST", body: form });
            const { transcript } = await r.json();
            setState(s => ({ ...s, transcript }));
            stopAndParse(transcript);
          } catch { setState(s => ({ ...s, status: "error", error: "Transcription failed" })); }
        };
        mr.start();
      });
    }
  }, [stopAndParse]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    mediaRecorderRef.current?.stop();
  }, []);

  const executeCommand = useCallback(async (cmd?: ParsedCommand) => {
    const target = cmd ?? state.parsed;
    if (!target) return;
    setState(s => ({ ...s, status: "executing" }));
    try {
      const r = await fetch("/api/v1/voice/commands/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool: target.tool,
          args: { ...target.args, connection_id: connectionId },
          confirm: true,
        }),
      });
      const result = await r.json();
      setState(s => ({ ...s, status: "done", actionId: result.action_id ?? null }));
      onExecuted?.(result.action_id, target.tool);
    } catch (e: any) {
      setState(s => ({ ...s, status: "error", error: e.message }));
    }
  }, [state.parsed, connectionId, onExecuted]);

  const cancelCommand = useCallback(() => setState(s => ({ ...s, status: "idle", parsed: null })), []);

  return { state, startListening, stopListening, executeCommand, cancelCommand, reset };
}
