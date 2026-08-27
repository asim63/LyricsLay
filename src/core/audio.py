import pyaudiowpatch as pyaudio
import numpy as np
import config


# ── Module-level singleton — created once, reused across all calls ──────────
_pyaudio_instance = None
_device_info = None  # (native_rate, native_channels, device_index, name)


def _get_pyaudio() -> pyaudio.PyAudio:
    """Returns the shared PyAudio instance, creating it only once."""
    global _pyaudio_instance
    if _pyaudio_instance is None:
        _pyaudio_instance = pyaudio.PyAudio()
    return _pyaudio_instance


def _get_cached_device():
    """
    Returns cached device info (rate, channels, index, name) or None.
    Re-enumerates only if cache is empty.
    """
    global _device_info

    if _device_info is not None:
        return _device_info

    p = _get_pyaudio()
    device = _get_loopback_device(p)

    if device is None:
        return None

    _device_info = (
        int(device["defaultSampleRate"]),
        int(device["maxInputChannels"]),
        device["index"],
        device["name"],
    )
    return _device_info


def invalidate_device_cache():
    """Call when audio device changes (e.g. speaker ↔ headphones switch)."""
    global _device_info
    _device_info = None


def record_audio(duration=config.SAMPLE_DURATION) -> np.ndarray:
    """
    Records system audio using WASAPI loopback.
    Reuses the PyAudio instance and caches device info for speed.
    """

    print(f"[Audio] Listening for {duration} seconds...")

    p = _get_pyaudio()

    try:
        dev_info = _get_cached_device()

        if dev_info is None:
            print("[Audio] No loopback device found — falling back to default input")
            return _record_fallback(duration)

        native_rate, native_channels, device_index, device_name = dev_info

        print(
            f"[Audio] Using device: {device_name} "
            f"at {native_rate}Hz, {native_channels}ch"
        )

        stream = p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=native_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024
        )

        frames = []
        total_frames = int(native_rate * duration)
        collected = 0

        try:
            while collected < total_frames:

                try:
                    data = stream.read(
                        1024,
                        exception_on_overflow=False
                    )

                    if not data:
                        print("[Audio] Empty audio buffer.")
                        break

                    frames.append(data)
                    collected += 1024

                except Exception as e:
                    print(f"[Audio] Stream read failed: {e}")
                    # device may have switched — invalidate cache for next call
                    invalidate_device_cache()
                    break

        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

    except Exception as e:
        print(f"[Audio] Recording failed: {e}")
        invalidate_device_cache()
        return np.array([], dtype=np.int16)

    if len(frames) == 0:
        print("[Audio] No audio captured.")
        return np.array([], dtype=np.int16)

    print("[Audio] Done recording.")

    raw = b"".join(frames)

    audio = np.frombuffer(raw, dtype=np.int16)

    # Convert stereo → mono
    if native_channels >= 2:
        try:
            audio = audio.reshape(-1, native_channels)
            audio = audio.mean(axis=1).astype(np.int16)
        except Exception as e:
            print(f"[Audio] Stereo conversion failed: {e}")
            return np.array([], dtype=np.int16)

    # Resample to configured sample rate
    if native_rate != config.SAMPLE_RATE:
        audio = _resample(
            audio,
            native_rate,
            config.SAMPLE_RATE
        )

    return audio


def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """
    Resamples audio from one sample rate to another.
    Example: 48000Hz → 16000Hz
    """

    ratio = to_rate / from_rate
    new_length = int(len(audio) * ratio)

    indices = np.linspace(
        0,
        len(audio) - 1,
        new_length
    )

    return np.interp(
        indices,
        np.arange(len(audio)),
        audio
    ).astype(np.int16)


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

        try:
            info = p.get_device_info_by_index(i)

            if info.get("isLoopbackDevice", False):
                return info

        except Exception:
            continue

    return None


def _record_fallback(duration: int) -> np.ndarray:
    """
    Fallback if no loopback device found.
    """

    try:
        import sounddevice as sd

        recording = sd.rec(
            frames=int(duration * config.SAMPLE_RATE),
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocking=True
        )

        return recording.flatten()

    except Exception as e:
        print(f"[Audio] Fallback recording failed: {e}")
        return np.array([], dtype=np.int16)