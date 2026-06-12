#!/usr/bin/env python3
"""Pre-generate the coached-call theater audio from a RESIDENTIAL IP.

Why this exists: ElevenLabs' free tier rejects API calls originating from
datacenter IPs (Render, AWS, …) with 401 "unusual activity". So the demo
script's audio must be generated from a normal home/office connection and
committed as a disk cache the backend serves directly.

Usage (from repo root, with ELEVENLABS_API_KEY in .env):
    python3 scripts/pregenerate_theater_audio.py

It fetches the canonical script from the deployed backend for each demo
client (so the text + hashing always match prod), generates any missing
lines via ElevenLabs, and writes mp3s to
artifacts/sync-backend/static/theater_tts/{sha1}.mp3. Commit the new files.

KEEP IN SYNC with routers/coached_calls.py: voice IDs, model, voice_settings
and the cache-key formula must match theater_tts() exactly.
"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "artifacts" / "sync-backend" / "static" / "theater_tts"
BACKEND = "https://sync-backend-u9rv.onrender.com"

# ── Must mirror routers/coached_calls.py ──────────────────────────────────
VOICE_RM = "cjVigY5qzO86Huf0OWal"      # Eric
VOICE_CLIENT = "iP95p4xoKVk53GoZ742B"  # Chris (default male client)
VOICE_SYNC = "XrExE9yKIg1WjnnlVkGX"    # Matilda — the SYNC agent voice
CLIENT_VOICE_OVERRIDES = {
    "priya": "EXAVITQu4vr4xnSDxMaL",   # Sarah
    "sneha": "cgSgspJ2msm6clMCkdW9",   # Jessica
}
SCENARIOS = ["coached", "savecall", "standup"]
MODEL = "eleven_multilingual_v2"
VOICE_SETTINGS = {"stability": 0.4, "similarity_boost": 0.8, "style": 0.4, "use_speaker_boost": True}
SETTINGS_TAG = f"s{VOICE_SETTINGS['stability']}-st{VOICE_SETTINGS['style']}"

RM_NAME = "Himanshu"
DEMO_CLIENTS = ["Vikram Desai", "Rahul Mehta", "Priya Sharma", "Amit Patel", "Sneha Reddy"]


def client_voice(client_name: str) -> str:
    return CLIENT_VOICE_OVERRIDES.get(client_name.split(" ")[0].lower(), VOICE_CLIENT)


def read_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("ELEVENLABS_API_KEY not found in .env")


def post_json(url: str, payload: dict, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> None:
    key = read_key()
    OUT.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    generated = skipped = 0

    # standup uses live CRM data + the default RM, so one pass; the other
    # scenarios personalize per client.
    jobs = [(s, c) for s in SCENARIOS for c in
            (DEMO_CLIENTS if s != "standup" else DEMO_CLIENTS[:1])]
    for scenario, client_name in jobs:
        resp = json.loads(post_json(
            f"{BACKEND}/api/v1/coached-calls/simulate/start",
            {"client_name": client_name, "rm_name": RM_NAME, "scenario": scenario},
        ))
        # Close the probe session server-side right away.
        try:
            post_json(f"{BACKEND}/api/v1/coached-calls/simulate/{resp['call_id']}/end", {})
        except Exception:
            pass
        for line in resp["script"]:
            if line["speaker"] == "event":
                continue
            text = line["text"]
            if line["speaker"] == "rm":
                voice = VOICE_RM
            elif line["speaker"] == "sync":
                voice = VOICE_SYNC
            else:
                voice = client_voice(client_name)
            cache_key = hashlib.sha1(f"{voice}|{MODEL}|{SETTINGS_TAG}|{text}".encode()).hexdigest()
            if cache_key in seen:
                continue
            seen.add(cache_key)
            path = OUT / f"{cache_key}.mp3"
            if path.exists():
                skipped += 1
                continue
            audio = post_json(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_64",
                {"text": text, "model_id": MODEL, "voice_settings": VOICE_SETTINGS},
                headers={"xi-api-key": key},
            )
            path.write_bytes(audio)
            generated += 1
            print(f"  ✓ [{line['speaker']:6s}] {text[:60]}…  → {path.name} ({len(audio)//1024} KB)")
            time.sleep(0.4)  # free tier: stay under concurrency/rate caps

    print(f"\nDone — {generated} generated, {skipped} already on disk, "
          f"{len(seen)} unique lines across {len(DEMO_CLIENTS)} clients.")
    print(f"Files in {OUT.relative_to(ROOT)} — commit them.")


if __name__ == "__main__":
    main()
