import pyaudiowpatch as pyaudio
import numpy as np
import config

def record_audio(duration=config.SAMPLE_DURATION) -> np.ndarray:
    """
    Records system audio using WASAPI loopback.
    Captures whatever is playing through speakers or headphones.
    """
    print(f"[Audio] Listening for {duration} seconds...")

    p = pyaudio.PyAudio()

    device = _get_loopback_device(p)
    if device is None:
        print("[Audio] No loopback device found — falling back to default input")
        p.terminate()
        return _record_fallback(duration)

    native_rate     = int(device["defaultSampleRate"])
    native_channels = int(device["maxInputChannels"])
    print(f"[Audio] Using device: {device['name']} at {native_rate}Hz, {native_channels}ch")

    stream = p.open(
        format             = pyaudio.paInt16,
        channels           = native_channels,  # use device's native channels
        rate               = native_rate,
        input              = True,
        input_device_index = device["index"],
        frames_per_buffer  = 1024
    )

    frames = []
    total_frames = int(native_rate * duration)
    collected = 0

    while collected < total_frames:
        data = stream.read(1024, exception_on_overflow=False)
        frames.append(data)
        collected += 1024

    stream.stop_stream()
    stream.close()
    p.terminate()

    print("[Audio] Done recording.")

    raw = b"".join(frames)
    audio = np.frombuffer(raw, dtype=np.int16)

    # if stereo, convert to mono by averaging both channels
    if native_channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1).astype(np.int16)

    # resample to 16000Hz if needed
    if native_rate != config.SAMPLE_RATE:
        audio = _resample(audio, native_rate, config.SAMPLE_RATE)

    return audio

def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """
    Resamples audio from one sample rate to another.
    e.g. 48000Hz → 16000Hz
    """
    ratio = to_rate / from_rate
    new_length = int(len(audio) * ratio)
    indices = np.linspace(0, len(audio) - 1, new_length)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.int16)

def _get_loopback_device(p: pyaudio.PyAudio) -> dict | None:
    """
    Finds the active WASAPI loopback device.
    """
    try:
        default_output = p.get_default_wasapi_loopback()
        if default_output:
            return default_output
    except Exception:
        pass

    # fallback — scan all devices for any loopback
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info.get("isLoopbackDevice", False):
            return info

    return None

def _record_fallback(duration: int) -> np.ndarray:
    """
    Fallback if no loopback device found.
    """
    import sounddevice as sd
    recording = sd.rec(
        frames     = int(duration * config.SAMPLE_RATE),
        samplerate = config.SAMPLE_RATE,
        channels   = 1,
        dtype      = "int16",
        blocking   = True
    )
    return recording
