import { useEffect, useRef, useState } from "react";
import { Device, Call } from "@twilio/voice-sdk";
import { Phone, PhoneOff, Loader2 } from "lucide-react";

interface Props {
  callKey: string;
  clientPhone: string;
  clientName: string;
  onCallEnded?: () => void;
}

type Status = "init" | "connecting" | "ringing" | "connected" | "disconnected" | "error";

export function TwilioCallControls({ callKey, clientPhone, clientName, onCallEnded }: Props) {
  const [status, setStatus] = useState<Status>("init");
  const [elapsed, setElapsed] = useState(0);
  const deviceRef = useRef<Device | null>(null);
  const callRef = useRef<Call | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const resp = await fetch("/api/v1/coached-calls/rm-token");
        if (!resp.ok) throw new Error(`Token fetch failed: ${resp.status}`);
        const { token } = await resp.json();

        if (cancelled) return;

        const device = new Device(token, {
          codecPreferences: [Call.Codec.Opus, Call.Codec.PCMU],
          logLevel: 1,
        });
        deviceRef.current = device;

        device.on("error", (err) => {
          console.error("Twilio Device error:", err);
          setStatus("error");
        });

        await device.register();
        if (cancelled) return;

        setStatus("connecting");
        const call = await device.connect({
          params: {
            call_key: callKey,
            client_phone: clientPhone,
          },
        });
        callRef.current = call;

        call.on("ringing", () => setStatus("ringing"));
        call.on("accept", () => {
          setStatus("connected");
          timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
        });
        call.on("disconnect", () => {
          setStatus("disconnected");
          if (timerRef.current) clearInterval(timerRef.current);
          onCallEnded?.();
        });
        call.on("error", (err) => {
          console.error("Twilio Call error:", err);
          setStatus("error");
          if (timerRef.current) clearInterval(timerRef.current);
        });
      } catch (err) {
        console.error("Twilio init failed:", err);
        if (!cancelled) setStatus("error");
      }
    }

    init();

    return () => {
      cancelled = true;
      if (timerRef.current) clearInterval(timerRef.current);
      try { callRef.current?.disconnect(); } catch {}
      try { deviceRef.current?.destroy(); } catch {}
    };
  }, [callKey, clientPhone]);

  const hangUp = () => {
    try { callRef.current?.disconnect(); } catch {}
    setStatus("disconnected");
    if (timerRef.current) clearInterval(timerRef.current);
    onCallEnded?.();
  };

  const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
  const firstName = clientName.split(" ")[0];

  return (
    <div className="mt-4 flex flex-col items-center gap-3 border-t border-ink/15 pt-4">
      <div className="flex items-center gap-3">
        {status === "connected" && (
          <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-500" />
        )}
        <span className="font-edit-mono text-[11px] uppercase tracking-widest text-ink/70">
          {status === "init" && "Initializing…"}
          {status === "connecting" && `Connecting to ${firstName}…`}
          {status === "ringing" && `Ringing ${firstName}…`}
          {status === "connected" && `On call with ${firstName} — ${fmt(elapsed)}`}
          {status === "disconnected" && "Call ended"}
          {status === "error" && "Connection failed"}
        </span>
      </div>

      {(status === "connecting" || status === "ringing") && (
        <Loader2 className="h-5 w-5 animate-spin text-ink/40" />
      )}

      {(status === "connected" || status === "connecting" || status === "ringing") && (
        <button
          onClick={hangUp}
          className="inline-flex items-center gap-2 border-2 border-red-800 bg-red-800 px-6 py-3 font-edit-mono text-[11px] uppercase tracking-widest text-paper hover:bg-paper hover:text-red-800"
        >
          <PhoneOff className="h-3.5 w-3.5" /> Hang up
        </button>
      )}

      {status === "disconnected" && (
        <p className="font-serif text-[12px] italic text-ink/50">
          Whispers and CRM actions are still available in the sidebar.
        </p>
      )}

      {status === "error" && (
        <p className="max-w-sm text-center font-serif text-[12px] italic text-red-800">
          Could not connect the call. Check that Twilio credentials are configured and the client number is verified.
        </p>
      )}
    </div>
  );
}
