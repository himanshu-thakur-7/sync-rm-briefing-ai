import { useEffect, useRef, useState } from "react";
import { Device, Call } from "@twilio/voice-sdk";
import { PhoneOff, Loader2, VolumeX, Volume2 } from "lucide-react";

interface Props {
  callKey: string;
  clientPhone: string;
  clientName: string;
  onCallEnded?: () => void;
}

type Status = "init" | "connecting" | "ringing" | "connected" | "disconnected" | "error";

export function TwilioCallControls({ callKey, clientPhone, clientName, onCallEnded }: Props) {
  const [status, setStatus] = useState<Status>("init");
  const [errorDetail, setErrorDetail] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [muted, setMuted] = useState(false);
  const deviceRef = useRef<Device | null>(null);
  const callRef = useRef<Call | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    console.log("[TwilioCallControls] mounting", { callKey, clientPhone, clientName });

    async function init() {
      try {
        console.log("[Twilio] Fetching RM voice token…");
        const resp = await fetch("/api/v1/coached-calls/rm-token");
        if (!resp.ok) {
          const body = await resp.text().catch(() => "");
          throw new Error(`Token fetch failed (${resp.status}): ${body}`);
        }
        const { token } = await resp.json();
        console.log("[Twilio] Token received, length:", token?.length);

        if (cancelled) return;

        const device = new Device(token, {
          codecPreferences: [Call.Codec.Opus, Call.Codec.PCMU],
          logLevel: 1,
        });
        deviceRef.current = device;

        device.on("error", (err) => {
          console.error("[Twilio] Device error:", err);
          setErrorDetail(err?.message || String(err));
          setStatus("error");
        });

        await device.register();
        console.log("[Twilio] Device registered, connecting…", { callKey, clientPhone });
        if (cancelled) return;

        setStatus("connecting");
        const call = await device.connect({
          params: {
            call_key: callKey,
            client_phone: clientPhone,
          },
        });
        callRef.current = call;
        console.log("[Twilio] Call initiated, SID:", call.parameters?.CallSid);

        call.on("ringing", () => {
          console.log("[Twilio] Ringing…");
          setStatus("ringing");
        });
        call.on("accept", () => {
          console.log("[Twilio] Call accepted — connected!");
          setStatus("connected");
          timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
        });
        call.on("disconnect", () => {
          console.log("[Twilio] Call disconnected");
          setStatus("disconnected");
          if (timerRef.current) clearInterval(timerRef.current);
          onCallEnded?.();
        });
        call.on("cancel", () => {
          console.log("[Twilio] Call cancelled");
          setStatus("disconnected");
          if (timerRef.current) clearInterval(timerRef.current);
          onCallEnded?.();
        });
        call.on("reject", () => {
          console.log("[Twilio] Call rejected");
          setErrorDetail("Call was rejected");
          setStatus("error");
        });
        call.on("error", (err) => {
          console.error("[Twilio] Call error:", err);
          setErrorDetail(err?.message || String(err));
          setStatus("error");
          if (timerRef.current) clearInterval(timerRef.current);
        });
      } catch (err: any) {
        console.error("[Twilio] Init failed:", err);
        if (!cancelled) {
          setErrorDetail(err?.message || String(err));
          setStatus("error");
        }
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

  const toggleMute = () => {
    const call = callRef.current;
    if (!call) return;
    if (muted) {
      call.mute(false);
      setMuted(false);
    } else {
      call.mute(true);
      setMuted(true);
    }
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
          {status === "init" && "Initializing Twilio…"}
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
        <div className="flex items-center gap-3">
          <button
            onClick={toggleMute}
            className={`inline-flex items-center gap-2 border-2 px-4 py-3 font-edit-mono text-[11px] uppercase tracking-widest transition-colors ${
              muted
                ? "border-amber-700 bg-amber-700 text-paper hover:bg-paper hover:text-amber-700"
                : "border-ink/40 bg-paper text-ink/70 hover:border-ink hover:text-ink"
            }`}
            title={muted ? "Unmute your mic on the call" : "Mute your mic on the call"}
          >
            {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
            {muted ? "Muted" : "Mute"}
          </button>
          <button
            onClick={hangUp}
            className="inline-flex items-center gap-2 border-2 border-red-800 bg-red-800 px-6 py-3 font-edit-mono text-[11px] uppercase tracking-widest text-paper hover:bg-paper hover:text-red-800"
          >
            <PhoneOff className="h-3.5 w-3.5" /> Hang up
          </button>
        </div>
      )}

      {status === "disconnected" && (
        <p className="font-serif text-[12px] italic text-ink/50">
          Whispers and CRM actions are still available in the sidebar.
        </p>
      )}

      {status === "error" && (
        <div className="max-w-md text-center">
          <p className="font-serif text-[12px] italic text-red-800">
            Could not connect the call.
          </p>
          {errorDetail && (
            <p className="mt-1 font-edit-mono text-[10px] text-red-700/70">{errorDetail}</p>
          )}
        </div>
      )}
    </div>
  );
}
