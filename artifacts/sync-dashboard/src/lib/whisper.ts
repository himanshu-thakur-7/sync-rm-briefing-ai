/**
 * Whisper Mode — speak coaching nudges into the RM's ear.
 *
 * The RM keeps the dashboard open with one earbud in while they're on a phone
 * call with a client. When a coaching_nudge arrives, we play a soft chime and
 * speak the nudge via the browser's SpeechSynthesis — the client on the phone
 * hears nothing; the RM hears SYNC murmur in their ear.
 *
 * State persists in localStorage so the toggle survives reloads.
 */

const KEY = "sync-whisper-mode";

export function isWhisperOn(): boolean {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}

export function setWhisperOn(on: boolean): void {
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* ignore */ }
}

export function whisperSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// ─── Soft chime (WebAudio) ─────────────────────────────────────────────────
// A gentle two-note "attention" tone before the spoken nudge, so the RM's ear
// registers something is coming. Warn nudges get a slightly lower, flatter tone.

let audioCtx: AudioContext | null = null;

function chime(tone: string): Promise<void> {
  return new Promise(resolve => {
    try {
      audioCtx = audioCtx ?? new AudioContext();
      const ctx = audioCtx;
      const notes = tone === "warn" ? [440, 392] : [587, 784]; // warn: A4→G4; else D5→G5
      notes.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.12);
        gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + i * 0.12 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.12 + 0.11);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + i * 0.12);
        osc.stop(ctx.currentTime + i * 0.12 + 0.12);
      });
      setTimeout(resolve, 280);
    } catch {
      resolve(); // no chime is fine — speech still goes out
    }
  });
}

// ─── Speech ────────────────────────────────────────────────────────────────

function pickVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find(v => /en[-_]IN/i.test(v.lang)) ??
    voices.find(v => /en[-_]GB/i.test(v.lang)) ??
    voices.find(v => v.lang?.toLowerCase().startsWith("en")) ??
    voices[0]
  );
}

/** Exported chime for the theater — draws the ear to a whisper card without
 *  reading it aloud. */
export function playChime(tone: string): Promise<void> {
  return chime(tone);
}

// While the Coached Call theater is open it owns ALL audio sequencing —
// dialogue voices and whispers interleave on its clock. Suppress the global
// speakNudge path so a nudge never cancels a dialogue line mid-sentence.
let theaterActive = false;
export function setTheaterActive(on: boolean): void { theaterActive = on; }

/** Speak a nudge if Whisper Mode is on. Cancels any still-playing nudge first —
 *  a stale tip is worse than a missed one mid-conversation. */
export async function speakNudge(text: string, tone: string): Promise<void> {
  if (theaterActive) return;
  if (!isWhisperOn() || !whisperSupported() || !text.trim()) return;

  window.speechSynthesis.cancel();
  await chime(tone);

  const u = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) u.voice = voice;
  u.rate = 1.06;   // slightly brisk — it's a whisper between sentences, not a speech
  u.pitch = 1.0;
  u.volume = 1.0;
  window.speechSynthesis.speak(u);
}

/** Theater-mode whisper: chime + speak regardless of the 🎧 toggle, resolving
 *  when speech finishes so the caller can sequence dialogue around it. */
export async function speakWhisperLine(text: string, tone: string): Promise<void> {
  if (!whisperSupported() || !text.trim()) return;
  await chime(tone);
  await new Promise<void>(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) u.voice = voice;
    u.rate = 1.1;
    u.pitch = 1.0;
    u.volume = 0.95;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    // Safety: some engines drop onend — resolve after an estimated duration.
    setTimeout(resolve, 1200 + text.split(/\s+/).length * 380);
    window.speechSynthesis.speak(u);
  });
}

/** Speak one dialogue line with a per-speaker voice profile. Resolves on end. */
export function speakDialogue(text: string, opts: { pitch: number; rate: number }): Promise<void> {
  if (!whisperSupported() || !text.trim()) return Promise.resolve();
  return new Promise<void>(resolve => {
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) u.voice = voice;
    u.pitch = opts.pitch;
    u.rate = opts.rate;
    u.volume = 1.0;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    setTimeout(resolve, 1500 + text.split(/\s+/).length * 420);
    window.speechSynthesis.speak(u);
  });
}

/** Speak a short confirmation when the toggle is flipped on — doubles as the
 *  user-gesture "priming" some browsers require before later TTS. */
export function speakArmed(): void {
  if (!whisperSupported()) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance("Whisper mode on. I'll murmur tips here during live calls.");
  const voice = pickVoice();
  if (voice) u.voice = voice;
  u.rate = 1.06;
  window.speechSynthesis.speak(u);
}
