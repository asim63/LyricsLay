import sounddevice as sd
import numpy as np
import config

def record_audio(duration=config.SAMPLE_DURATION):
    """
    Records system audio for a given duration and returns it as a numpy array.
    This captures everything playing on your PC — speakers or headphones.
    """
    print(f"[Audio] Listening for {duration} seconds...")

    recording = sd.rec(
        frames          = int(duration * config.SAMPLE_RATE),
        samplerate      = config.SAMPLE_RATE,
        channels        = 1,       # mono — ShazamIO expects mono audio
        dtype           = "int16", # 16-bit — ShazamIO expects int16
        blocking        = True     # wait until recording is fully done
    )

    print("[Audio] Done recording.")
    return recording

def get_audio_devices():
    """
    Returns a list of all audio devices on the PC.
    Useful for debugging if audio capture isn't working.
    """
    return sd.query_devices()

def get_default_device():
    """
    Returns the default output device — what your PC is currently
    using to play sound (speakers or headphones).
    """
    return sd.query_devices(kind="output")
