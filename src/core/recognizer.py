import asyncio
import numpy as np
import wave
import os
import tempfile
from shazamio import Shazam
import config

shazam = Shazam()

def recognise_song(audio: np.ndarray) -> dict | None:
    """
    Takes a numpy audio array, saves it as a WAV file,
    sends it to Shazam, returns song info or None.
    """
    print("[Recogniser] Sending audio to Shazam...")

    # save numpy array as a proper WAV file
    wav_path = os.path.join(tempfile.gettempdir(), "lyricslay_sample.wav")
    _save_wav(audio, wav_path)

    # run async recognition
    result = asyncio.run(_recognise(wav_path))

    # clean up temp file
    if os.path.exists(wav_path):
        os.remove(wav_path)

    if not result:
        print("[Recogniser] No match found.")
        return None

    return result

def _save_wav(audio: np.ndarray, path: str):
    """
    Saves a numpy int16 array as a proper WAV file.
    ShazamIO reads WAV files reliably without needing FFmpeg.
    """
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)           # mono
        wf.setsampwidth(2)           # 2 bytes = int16
        wf.setframerate(config.SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

async def _recognise(wav_path: str) -> dict | None:
    """
    Internal async function — reads WAV file and sends to Shazam.
    """
    try:
        out = await shazam.recognize(wav_path)

        if "track" not in out:
            return None

        track = out["track"]
        return {
            "title":    track.get("title",    "Unknown Title"),
            "artist":   track.get("subtitle", "Unknown Artist"),
            "shazam_id": track.get("key",     ""),
        }

    except Exception as e:
        print(f"[Recogniser] Error: {e}")
        return None