import asyncio
import numpy as np
import wave
import os
import tempfile
import time
from shazamio import Shazam
import config

shazam = Shazam()

def recognise_song(audio: np.ndarray) -> dict | None:
    """
    Takes a numpy audio array, saves it as a WAV file,
    sends it to Shazam, returns song info or None.
    """
    print("[Recogniser] Sending audio to Shazam...")

    # save WAV first
    wav_path = os.path.join(tempfile.gettempdir(), "lyricslay_sample.wav")
    _save_wav(audio, wav_path)

    # measure only the API call time — not WAV saving
    send_time = time.time()
    result    = asyncio.run(_recognise(wav_path))
    shazam_delay_ms = (time.time() - send_time) * 1000

    # clean up temp file
    if os.path.exists(wav_path):
        os.remove(wav_path)

    if not result:
        print("[Recogniser] No match found.")
        return None

    # add delay to result
    result["shazam_delay_ms"] = shazam_delay_ms
    print(f"[Recogniser] Shazam delay: {shazam_delay_ms/1000:.1f}s")
    return result

def _save_wav(audio: np.ndarray, path: str):
    """
    Saves a numpy int16 array as a proper WAV file.
    """
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(config.SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

async def _recognise(wav_path: str) -> dict | None:
    """
    Internal async function — reads WAV and sends to Shazam.
    Returns dict with song info or None.
    """
    try:
        out = await shazam.recognize(wav_path)

        if "track" not in out:
            return None

        track = out["track"]

        # get offset — tells us where in the song we are
        offset_ms = 0
        if "matches" in out and out["matches"]:
            offset_ms = out["matches"][0].get("offset", 0) * 1000

        return {
            "title":     track.get("title",    "Unknown Title"),
            "artist":    track.get("subtitle", "Unknown Artist"),
            "shazam_id": track.get("key",      ""),
            "offset_ms": offset_ms,
            # shazam_delay_ms added by recognise_song() above
        }

    except Exception as e:
        print(f"[Recogniser] Error: {e}")
        return None