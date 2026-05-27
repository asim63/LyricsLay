import pyaudiowpatch as pyaudio
import numpy as np
import config


def record_audio(duration=config.SAMPLE_DURATION) -> np.ndarray:
    """
    Records system audio using WASAPI loopback.
    Automatically recovers from device switches
    (speaker ↔ headphones).
    """

    print(f"[Audio] Listening for {duration} seconds...")

    p = pyaudio.PyAudio()

    try:
        device = _get_loopback_device(p)

        if device is None:
            print("[Audio] No loopback device found — falling back to default input")
            p.terminate()
            return _record_fallback(duration)

        native_rate = int(device["defaultSampleRate"])
        native_channels = int(device["maxInputChannels"])

        print(
            f"[Audio] Using device: {device['name']} "
            f"at {native_rate}Hz, {native_channels}ch"
        )

        stream = p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=native_rate,
            input=True,
            input_device_index=device["index"],
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
                    break

        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

    except Exception as e:
        print(f"[Audio] Recording failed: {e}")
        p.terminate()
        return np.array([], dtype=np.int16)

    p.terminate()

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