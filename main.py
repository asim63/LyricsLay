import os

from src.core import audio
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

import sys
import threading
import time
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import pyqtSignal, QObject
from src.core        import settings
from src.core.audio      import record_audio
from src.core.recognizer import recognise_song
from src.core.cache      import is_cached, get_cached_song, cache_song, flush as flush_cache
from src.lyrics.fetcher  import fetch_lyrics
from src.ui.overlay      import LyricsOverlay
from src.ui.tray         import SystemTray
import config

# ── Single instance lock ──────────────────────────────────────────────────────
import tempfile
_lock_file_path = os.path.join(tempfile.gettempdir(), "lyricslay.lock")
try:
    _lock_file = open(_lock_file_path, 'w')
    import msvcrt
    msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except (IOError, OSError):
    sys.exit(0)
class SignalBridge(QObject):
    """
    Bridge between background threads and Qt main thread.
    Qt UI can only be updated from the main thread.
    """
    show_lyrics      = pyqtSignal(list, bool, float)
    show_loading     = pyqtSignal()
    show_no_lyrics   = pyqtSignal()
    song_changed     = pyqtSignal(str, str)
    toggle_overlay   = pyqtSignal()
    force_reidentify = pyqtSignal()


class LyricsLayApp:
    """
    Main application controller.

    Two-thread architecture:
    - Fast detector : checks every 4s if audio changed
    - Identifier    : full Shazam call when change detected

    Hotkeys:
    - Ctrl+Shift+L : toggle overlay
    - Ctrl+Shift+K : force reidentify current song
    """

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.overlay = LyricsOverlay()
        self.tray = SystemTray(self.overlay, self.app, reregister_hotkeys_fn=self.re_register_hotkey)
        self.bridge  = SignalBridge()
        self.s       = settings.load_settings()

        self.current_song_id       = None
        self.current_fingerprint   = None
        self.last_offset_ms        = 0.0
        self.running               = True
        self.identifying           = False
        self.force_reidentify_flag = False
        self.current_song_synced   = True
        self._shazam_lock          = threading.Lock()
        self._last_position_fp     = None   # fingerprint at last position check
        self._last_shazam_time     = 0.0    # timestamp of last Shazam position call

        self._connect_signals()
        self._register_hotkeys()
        # wire reidentify button on overlay
        self.overlay.reidentify_button.on_click = self._on_force_reidentify

    # ─── Signals ─────────────────────────────────────────────────────

    def _connect_signals(self):
        self.bridge.show_lyrics.connect(self.overlay.load_lyrics)
        self.bridge.show_loading.connect(self.overlay.set_loading)
        self.bridge.show_no_lyrics.connect(self.overlay.set_no_lyrics)
        self.bridge.toggle_overlay.connect(self._toggle)
        self.bridge.force_reidentify.connect(self._on_force_reidentify)

        self.overlay.toggle_requested.connect(self._toggle)
        self.tray.toggle_action.triggered.disconnect()
        self.tray.toggle_action.triggered.connect(self._toggle)

    def _toggle(self):
        """Toggle overlay and sync tray menu text."""
        self.overlay.toggle()
        self.tray.update_toggle_text()

    def _on_force_reidentify(self):
        """Called when user presses Ctrl+Shift+K."""
        print("[Hotkey] Force reidentify requested!")
        self.force_reidentify_flag = True
        self.current_song_id       = None
        self.current_fingerprint   = None

    # ─── Hotkeys ─────────────────────────────────────────────────────

    def _register_hotkeys(self):
        """Register all global hotkeys."""
        try:
            from pynput import keyboard

            toggle_key     = self.s.get("hotkey", config.DEFAULT_TOGGLE_HOTKEY)
            reidentify_key = self.s.get("reidentify_hotkey", config.DEFAULT_REIDENTIFY_HOTKEY)
            def on_toggle():
                print("[Hotkey] Toggle!")
                self.bridge.toggle_overlay.emit()

            def on_reidentify():
                print("[Hotkey] Force reidentify!")
                self.bridge.force_reidentify.emit()

            self.hotkey = keyboard.GlobalHotKeys({
                toggle_key:     on_toggle,
                reidentify_key: on_reidentify,
            })
            self.hotkey.daemon = True
            self.hotkey.start()
            print(f"[Hotkey] Toggle:     {toggle_key}")
            print(f"[Hotkey] Reidentify: {reidentify_key}")

        except Exception as e:
            print(f"[Hotkey] Failed: {e}")

    def _unregister_hotkeys(self):
        """Stop all hotkey listeners."""
        if hasattr(self, 'hotkey'):
            self.hotkey.stop()

    def re_register_hotkey(self, new_hotkey: str = None):
        """Called when user changes hotkey in settings."""
        self._unregister_hotkeys()
        self.s = settings.load_settings()
        self._register_hotkeys()

    # ─── Fast change detector ─────────────────────────────────────────

    def _change_detector_loop(self):
        """
        Runs continuously every 4 seconds.
        Records audio, checks fingerprint for song changes.
        Also checks position every cycle using same audio.
        """
        print("[Detector] Started.")
        time.sleep(8)

        fp_history = []

        while self.running:
            try:
                # force reidentify requested via hotkey
                if self.force_reidentify_flag:
                    self.force_reidentify_flag = False
                    fp_history                 = []
                    print("[Detector] Force reidentifying...")
                    audio = record_audio(duration=5)
                    self._trigger_identification(audio, force=True)
                    time.sleep(3)
                    continue

                if self.identifying:
                    time.sleep(1)
                    continue

                audio       = record_audio(duration=4)
                fingerprint = self._quick_fingerprint(audio)

                fp_history.append(fingerprint)
                if len(fp_history) > 4:
                    fp_history.pop(0)

                avg_fp = np.mean(fp_history, axis=0)

                if self.current_fingerprint is None:
                    self.current_fingerprint = avg_fp
                    self._trigger_identification(audio)
                    time.sleep(4)
                    continue

                # ── check for song change ─────────────────────────────
                if self._audio_changed(avg_fp, self.current_fingerprint):
                    print("[Detector] Possible change — confirming...")

                    time.sleep(3)
                    audio2 = record_audio(duration=4)
                    fp2    = self._quick_fingerprint(audio2)

                    if self._audio_changed(fp2, self.current_fingerprint):
                        print("[Detector] Change confirmed!")
                        self.current_fingerprint = avg_fp
                        self.current_song_id     = None
                        fp_history               = []
                        self._trigger_identification(audio2)
                    else:
                        print("[Detector] False positive — ignoring.")

                else:
                    # same song — smart position check (every cycle)
                    if (self.current_song_id and not self.identifying
                            and self.current_song_synced):
                        self._smart_position_check(audio, fingerprint)

                time.sleep(4)

            except Exception as e:
                print(f"[Detector] Error: {e}")
                time.sleep(3)

    def _smart_position_check(self, audio: np.ndarray, fingerprint: np.ndarray):
        """
        Smart position check — runs every cycle.
        Calls Shazam when: fingerprint jumps OR 15s since last call.
        """
        now = time.time()

        # first check — always do Shazam to establish baseline
        if self._last_position_fp is None:
            self._last_position_fp = fingerprint
            self._last_shazam_time = now
            threading.Thread(
                target=self._check_position_jump,
                args=(audio,),
                daemon=True
            ).start()
            return

        # ── Trigger 1: fingerprint jump = skip detected ──────────────
        diff = self._fingerprint_diff(fingerprint, self._last_position_fp)
        if diff >= 0.35:
            print(f"[Detector] Fingerprint jump: {diff:.2%} — checking position")
            self._last_position_fp = fingerprint
            self._last_shazam_time = now
            threading.Thread(
                target=self._check_position_jump,
                args=(audio,),
                daemon=True
            ).start()
            return

        # ── Trigger 2: periodic safety net (every 15s) ──────────────
        if now - self._last_shazam_time >= 15.0:
            self._last_position_fp = fingerprint
            self._last_shazam_time = now
            threading.Thread(
                target=self._check_position_jump,
                args=(audio,),
                daemon=True
            ).start()
            return

        # audio is stable — wall-clock timer keeps scrolling accurately

    def _fingerprint_diff(self, fp1: np.ndarray, fp2: np.ndarray) -> float:
        """Compare two fingerprints. Returns 0.0 = identical, 1.0 = very different."""
        if fp2[3] < 10 and fp1[3] < 10:
            return 0.0
        if fp2[3] < 10 or fp1[3] < 10:
            return 1.0
        diffs = []
        for i in range(3):
            if fp2[i] == 0:
                continue
            diffs.append(abs(fp1[i] - fp2[i]) / (abs(fp2[i]) + 1e-8))
        if not diffs:
            return 0.0
        return float(np.mean(diffs))

    def _check_position_jump(self, audio: np.ndarray):
        """
        Full Shazam position check — called when fingerprint shows a skip.
        Uses resync_to() for zero-drift timer update.
        """
        if not self.current_song_id or self.identifying:
            return

        if not self._shazam_lock.acquire(blocking=False):
            return

        try:
            song = recognise_song(audio)
            if not song:
                return

            if not self.current_song_id:
                return

            if song["shazam_id"] != self.current_song_id:
                print("[Detector] Different song in position check!")
                self.current_song_id     = None
                self.current_fingerprint = None
                self._trigger_identification(audio)
                return

            if not getattr(self.overlay, "_is_synced", True):
                return

            # raw position — wall-clock timer handles the rest
            # raw position + recording duration
            new_pos_ms = song.get("offset_ms", 0.0) + (config.SAMPLE_DURATION * 1000)
            expected_ms = self.overlay.playback_time * 1000
            diff_ms = abs(new_pos_ms - expected_ms)

            print(f"[Detector] Position — "
                  f"expected: {expected_ms/1000:.1f}s  "
                  f"actual: {new_pos_ms/1000:.1f}s  "
                  f"diff: {diff_ms/1000:.1f}s")

            # any significant difference → resync (wall-clock handles drift)
            if diff_ms > 3000:
                print("[Detector] Skip detected! Resyncing...")
                # resync via Qt signal — thread-safe, runs on main thread
                self.overlay.resync_signal.emit(new_pos_ms / 1000.0)

        except Exception as e:
            print(f"[Detector] Position check error: {e}")
        finally:
            self._shazam_lock.release()

    def _quick_fingerprint(self, audio: np.ndarray) -> np.ndarray:
        """
        Stable spectral fingerprint.
        Uses ZCR, spectral centroid, rolloff and RMS.
        Consistent within same song even across quiet/loud sections.
        """
        if len(audio) == 0:
            return np.zeros(4)

        audio_f = audio.astype(float)

        signs = np.sign(audio_f)
        zcr   = float(np.mean(np.abs(np.diff(signs))) / 2)

        fft   = np.abs(np.fft.rfft(audio_f))
        freqs = np.fft.rfftfreq(len(audio_f))
        centroid = float(
            np.sum(freqs * fft) / np.sum(fft)
        ) if np.sum(fft) > 0 else 0.0

        cumsum    = np.cumsum(fft)
        threshold = 0.85 * cumsum[-1]
        rolloff   = float(freqs[np.searchsorted(cumsum, threshold)])

        rms = float(np.sqrt(np.mean(audio_f ** 2)))

        return np.array([zcr, centroid, rolloff, rms])

    def _audio_changed(self,
                       new_fp: np.ndarray,
                       old_fp: np.ndarray) -> bool:
        """
        Returns True if audio changed significantly.
        Compares spectral features — volume independent.
        """
        if old_fp[3] < 10 and new_fp[3] < 10:
            return False
        if old_fp[3] < 10 or new_fp[3] < 10:
            return True

        diffs = []
        for i in range(3):
            if old_fp[i] == 0:
                continue
            diff = abs(new_fp[i] - old_fp[i]) / (abs(old_fp[i]) + 1e-8)
            diffs.append(diff)

        if not diffs:
            return False

        avg_diff = float(np.mean(diffs))
        changed  = avg_diff > 0.40

        if changed:
            print(f"[Detector] Spectral diff: {avg_diff:.2%}")
        return changed

    def _trigger_identification(self, audio: np.ndarray,
                                 force: bool = False):
        """Start full identification in background thread."""
        if self.identifying and not force:
            return

        threading.Thread(
            target=self._identify_and_load,
            args=(audio,),
            daemon=True
        ).start()

    # ─── Full identifier ──────────────────────────────────────────────

    def _identify_and_load(self, audio: np.ndarray):
        """
        Full pipeline: Audio → Shazam → Lyrics → Overlay.
        Compensates for recording + API delay in sync offset.
        """

        self.identifying = True

        try:
            print("[Identifier] Identifying...")

            # Empty audio protection
            if audio.size == 0:
                print("[Identifier] Empty audio buffer — retrying...")
                self.bridge.show_no_lyrics.emit()
                return

            # Retry short recordings
            if len(audio) < 16000 * 4:
                print("[Identifier] Audio too short — retrying capture...")
                audio = record_audio(duration=5)

                if audio.size == 0:
                    print("[Identifier] Retry capture failed.")
                    self.bridge.show_no_lyrics.emit()
                    return

            with self._shazam_lock:
                song = recognise_song(audio)

            if song is None:
                print("[Identifier] No match.")
                self.bridge.show_no_lyrics.emit()
                self.current_song_id = None
                self.current_fingerprint = None
                return

            shazam_id = song["shazam_id"]
            title = song["title"]
            artist = song["artist"]
            offset_ms = song.get("offset_ms", 0.0)
            shazam_delay = song.get("shazam_delay_ms", 0.0)

            print(
                f"[Identifier] {title} by {artist} "
                f"(raw offset: {offset_ms:.0f}ms)"
            )

            # raw position + recording duration compensation
            # offset_ms is where song was during recording, add recording time
            current_pos_ms = offset_ms + (config.SAMPLE_DURATION * 1000)

            # determine cache key based on romanization setting
            from src.core.settings import get as get_setting
            cache_key = (
                f"{shazam_id}_rom"
                if get_setting("romanize_lyrics")
                else shazam_id
            )

            # SAME SONG HANDLING
            if shazam_id == self.current_song_id:

                # synced lyrics → allow proper resync
                if getattr(self, "current_song_synced", False):

                    print("[Identifier] Same song — resyncing.")

                    self._resync_position(
                        shazam_id,
                        current_pos_ms
                    )

                else:
                    # unsynced lyrics should NOT resync
                    print(
                        "[Identifier] Same unsynced song — "
                        "keeping auto-scroll."
                    )
                    
                return

            # NEW SONG
            self.bridge.show_loading.emit()
            self.current_song_id = shazam_id
            self.last_offset_ms = current_pos_ms

            self.bridge.song_changed.emit(title, artist)

            # load from cache
            if is_cached(cache_key):

                cached = get_cached_song(cache_key)

                print(
                    f"[Identifier] From cache! ✅ "
                    f"Position: {current_pos_ms/1000:.1f}s"
                )

                # determine if cached lyrics are synced
                synced = cached["lyrics"] and any(
                    entry["t"] > 0
                    for entry in cached["lyrics"]
                )

                self.current_song_synced = synced

                self.bridge.show_lyrics.emit(
                    cached["lyrics"],
                    False,
                    current_pos_ms
                )

                return

            # fetch lyrics
            lyrics = fetch_lyrics(title, artist)
            synced = lyrics and any(
                entry["t"] > 0
                for entry in lyrics
            )
            # IMPORTANT
            self.current_song_synced = synced

            # SYNCED LYRICS
            if lyrics and synced:

                cache_song(
                    cache_key,
                    title,
                    artist,
                    lyrics
                )

                self.bridge.show_lyrics.emit(
                    lyrics,
                    False,
                    current_pos_ms
                )

                print(
                    f"[Identifier] Done. "
                    f"Position: {current_pos_ms/1000:.1f}s"
                )
            # UNSYNCED LYRICS
            elif lyrics and not synced:
                print(
                    "[Identifier] Unsynced lyrics — "
                    "auto-scroll mode."
                )
                self.bridge.show_lyrics.emit(
                    lyrics,
                    False,
                    current_pos_ms
                )
            # NO LYRICS
            else:
                cache_song(
                    cache_key,
                    title,
                    artist,
                    []
                )
                self.current_song_synced = False
                print("[Identifier] No lyrics found.")
                self.bridge.show_no_lyrics.emit()

        except Exception as e:
            print(f"[Identifier] Error: {e}")
            self.current_song_synced = False
            self.bridge.show_no_lyrics.emit()
        finally:
            self.identifying = False

    def _resync_position(self, shazam_id: str, offset_ms: float):
        """Resyncs lyrics to correct position after skip."""
        # never resync unsynced lyrics — they have no timestamps
        if not getattr(self.overlay, "_is_synced", True):
            return
    
        from src.core.settings import get as get_setting
        cache_key = (
            f"{shazam_id}_rom"
            if get_setting("romanize_lyrics")
            else shazam_id
        )

        if is_cached(cache_key):
            cached = get_cached_song(cache_key)
            lyrics = cached.get("lyrics", [])
            if lyrics:
                print(f"[Identifier] Resyncing at "
                      f"{offset_ms/1000:.1f}s")
                self.bridge.show_lyrics.emit(lyrics, False, offset_ms)
    # ─── Run ─────────────────────────────────────────────────────────

    def run(self):
        """Start everything and enter Qt event loop."""
        self.overlay.show()

        threading.Thread(
            target=self._change_detector_loop,
            daemon=True
        ).start()

        threading.Thread(
            target=self._initial_identify,
            daemon=True
        ).start()

        print("[Main] LyricsLay started!")
        print("[Main] Ctrl+Shift+L → toggle overlay")
        print("[Main] Ctrl+Shift+K → force reidentify")

        exit_code = self.app.exec()
        self.running = False
        self._unregister_hotkeys()
        flush_cache()
        sys.exit(exit_code)

    def _initial_identify(self):
        """
        Identify on startup in case music is already playing.
        Runs immediately without waiting for detector.
        """
        try:
            time.sleep(1)
            audio = record_audio(duration=5)
            self._identify_and_load(audio)
        except Exception as e:
            print(f"[Main] Initial identify error: {e}")


if __name__ == "__main__":
    lyricslay = LyricsLayApp()
    lyricslay.run()