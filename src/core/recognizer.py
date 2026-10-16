import asyncio
import numpy as np
import wave
import io
import time
import threading
from shazamio import Shazam
import config

shazam = Shazam()

# Persistent event loop for async Shazam calls
_event_loop = None


def _get_event_loop():
    """Returns a persistent event loop, creating one only once."""
    global _event_loop
    if _event_loop is not None and _event_loop.is_running():
        return _event_loop
    _event_loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(
        target=_event_loop.run_forever, daemon=True
    )
    loop_thread.start()
    return _event_loop


def _wav_bytes_from_audio(audio: np.ndarray) -> bytes:
    """
    Converts a numpy int16 array to WAV bytes in memory.
    No disk I/O required.
    """
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(config.SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def recognise_song(audio: np.ndarray) -> dict | None:
    """
    Takes a numpy audio array, converts to WAV bytes in memory,
    sends to Shazam, returns song info or None.
    """
    print("[Recogniser] Sending audio to Shazam...")

    # build WAV bytes in memory — no disk write needed
    wav_data = _wav_bytes_from_audio(audio)

    # measure only the API call time
    send_time = time.time()

    loop = _get_event_loop()
    future = asyncio.run_coroutine_threadsafe(_recognise(wav_data), loop)
    result = future.result(timeout=15)  # 15s timeout for Shazam call

    shazam_delay_ms = (time.time() - send_time) * 1000

    if not result:
        print("[Recogniser] No match found.")
        return None

    # add delay to result
    result["shazam_delay_ms"] = shazam_delay_ms
    print(f"[Recogniser] Shazam delay: {shazam_delay_ms/1000:.1f}s")
    return result


async def _recognise(wav_data: bytes) -> dict | None:
    """
    Internal async function — sends WAV bytes to Shazam.
    Returns dict with song info or None.
    """
    try:
        out = await shazam.recognize(wav_data)

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