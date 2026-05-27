import os
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

import sys
import tempfile

# ── Single instance lock ──────────────────────────────────────────────────────
_lock_file_path = os.path.join(tempfile.gettempdir(), "lyricslay.lock")
try:
    _lock_file = open(_lock_file_path, 'w')
    import msvcrt
    msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except (IOError, OSError):
    sys.exit(0)

import threading
import time
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import QTimer, pyqtSignal, QObject
from src.core        import settings
from src.core.settings   import get as get_setting
from src.core.audio      import record_audio
from src.core.recognizer import recognise_song
from src.core.cache      import is_cached, get_cached_song, cache_song
from src.lyrics.fetcher  import fetch_lyrics
from src.ui.overlay      import LyricsOverlay
from src.ui.tray         import SystemTray
import config


class SignalBridge(QObject):
    show_lyrics      = pyqtSignal(list, bool, float)
    show_loading     = pyqtSignal()
    show_no_lyrics   = pyqtSignal()
    song_changed     = pyqtSignal(str, str)
    toggle_overlay   = pyqtSignal()
    force_reidentify = pyqtSignal()


class LyricsLayApp:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.overlay = LyricsOverlay()
        self.tray    = SystemTray(self.overlay, self.app,
                                  reregister_hotkeys_fn=self.re_register_hotkey)
        self.bridge  = SignalBridge()
        self.s       = settings.load_settings()

        self.current_song_id       = None
        self.current_fingerprint   = None
        self.last_offset_ms        = 0.0
        self.running               = True
        self.identifying           = False
        self.force_reidentify_flag = False
        self._shazam_lock          = threading.Lock()

        self._connect_signals()
        self._register_hotkeys()
        self.overlay.reidentify_button.on_click = self._on_force_reidentify

    # ─── signals ──────────────────────────────────────────────────────────────

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
        self.overlay.toggle()
        self.tray.update_toggle_text()

    def _on_force_reidentify(self):
        print("[Hotkey] Force reidentify requested!")
        self.force_reidentify_flag = True
        self.current_song_id       = None
        self.current_fingerprint   = None

    # ─── hotkeys ──────────────────────────────────────────────────────────────

    def _register_hotkeys(self):
        try:
            from pynput import keyboard
            toggle_key     = self.s.get("hotkey",            config.DEFAULT_TOGGLE_HOTKEY)
            reidentify_key = self.s.get("reidentify_hotkey", config.DEFAULT_REIDENTIFY_HOTKEY)

            self.hotkey = keyboard.GlobalHotKeys({
                toggle_key:     lambda: self.bridge.toggle_overlay.emit(),
                reidentify_key: lambda: self.bridge.force_reidentify.emit(),
            })
            self.hotkey.daemon = True
            self.hotkey.start()
            print(f"[Hotkey] Toggle:     {toggle_key}")
            print(f"[Hotkey] Reidentify: {reidentify_key}")
        except Exception as e:
            print(f"[Hotkey] Failed: {e}")

    def _unregister_hotkeys(self):
        if hasattr(self, "hotkey"):
            self.hotkey.stop()

    def re_register_hotkey(self, new_hotkey: str = None):
        self._unregister_hotkeys()
        self.s = settings.load_settings()
        self._register_hotkeys()

    # ─── change detector ──────────────────────────────────────────────────────

    def _change_detector_loop(self):
        print("[Detector] Started.")
        time.sleep(8)
        fp_history = []

        while self.running:
            try:
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
                    if self.current_song_id and not self.identifying:
                        threading.Thread(
                            target=self._check_position_jump,
                            args=(audio,),
                            daemon=True
                        ).start()

                time.sleep(4)

            except Exception as e:
                print(f"[Detector] Error: {e}")
                time.sleep(3)

    def _check_position_jump(self, audio: np.ndarray):
        if not self.current_song_id or self.identifying:
            return
        if not self._shazam_lock.acquire(blocking=False):
            return
        try:
            song = recognise_song(audio)
            if not song or song["shazam_id"] != self.current_song_id:
                return

            current_pos_ms = (
                song.get("offset_ms", 0.0) +
                config.SAMPLE_DURATION * 1000 +
                song.get("shazam_delay_ms", 0.0)
            )
            expected_ms = self.overlay.playback_time * 1000
            diff_ms     = abs(current_pos_ms - expected_ms)

            print(f"[Detector] Position — "
                  f"expected: {expected_ms/1000:.1f}s  "
                  f"actual: {current_pos_ms/1000:.1f}s  "
                  f"diff: {diff_ms/1000:.1f}s")

            if diff_ms > 5000:
                print("[Detector] Jump detected! Resyncing...")
                self._resync_position(self.current_song_id, current_pos_ms)
        except Exception as e:
            print(f"[Detector] Position check error: {e}")
        finally:
            self._shazam_lock.release()

    def _quick_fingerprint(self, audio: np.ndarray) -> np.ndarray:
        if len(audio) == 0:
            return np.zeros(4)
        audio_f  = audio.astype(float)
        signs    = np.sign(audio_f)
        zcr      = float(np.mean(np.abs(np.diff(signs))) / 2)
        fft      = np.abs(np.fft.rfft(audio_f))
        freqs    = np.fft.rfftfreq(len(audio_f))
        fft_sum  = np.sum(fft)
        centroid = float(np.sum(freqs * fft) / fft_sum) if fft_sum > 0 else 0.0
        cumsum   = np.cumsum(fft)
        rolloff  = float(freqs[np.searchsorted(cumsum, 0.85 * cumsum[-1])])
        rms      = float(np.sqrt(np.mean(audio_f ** 2)))
        return np.array([zcr, centroid, rolloff, rms])

    def _audio_changed(self, new_fp: np.ndarray, old_fp: np.ndarray) -> bool:
        if old_fp[3] < 10 and new_fp[3] < 10:
            return False
        if old_fp[3] < 10 or new_fp[3] < 10:
            return True
        diffs = []
        for i in range(3):
            if old_fp[i] == 0:
                continue
            diffs.append(abs(new_fp[i] - old_fp[i]) / (abs(old_fp[i]) + 1e-8))
        if not diffs:
            return False
        avg_diff = float(np.mean(diffs))
        if avg_diff > 0.40:
            print(f"[Detector] Spectral diff: {avg_diff:.2%}")
            return True
        return False

    def _trigger_identification(self, audio: np.ndarray, force: bool = False):
        if self.identifying and not force:
            return
        threading.Thread(
            target=self._identify_and_load,
            args=(audio,),
            daemon=True
        ).start()

    # ─── identification pipeline ──────────────────────────────────────────────

    def _identify_and_load(self, audio: np.ndarray):
        self.identifying = True
        self.bridge.show_loading.emit()

        try:
            print("[Identifier] Identifying...")

            if len(audio) < 16000 * 4:
                audio = record_audio(duration=5)

            with self._shazam_lock:
                song = recognise_song(audio)

            if song is None:
                print("[Identifier] No match.")
                self.bridge.show_no_lyrics.emit()
                self.current_song_id     = None
                self.current_fingerprint = None
                return

            shazam_id    = song["shazam_id"]
            title        = song["title"]
            artist       = song["artist"]
            offset_ms    = song.get("offset_ms", 0.0)
            shazam_delay = song.get("shazam_delay_ms", 0.0)

            print(f"[Identifier] {title} by {artist} (raw offset: {offset_ms:.0f}ms)")

            SAMPLE_MS = config.SAMPLE_DURATION * 1000
            LYRICS_MS = 500

            adjusted_offset = offset_ms + SAMPLE_MS + shazam_delay + LYRICS_MS
            cache_offset    = offset_ms + SAMPLE_MS + shazam_delay
            romanize        = get_setting("romanize_lyrics")
            base_key        = shazam_id
            rom_key         = f"{shazam_id}_rom"

            # same song — just resync
            if shazam_id == self.current_song_id:
                print("[Identifier] Same song — resyncing.")
                self._resync_position(shazam_id, adjusted_offset)
                return

            self.current_song_id = shazam_id
            self.last_offset_ms  = adjusted_offset
            self.bridge.song_changed.emit(title, artist)

            # ── cache lookup ──────────────────────────────────────────
            if romanize:
                if is_cached(rom_key):
                    cached = get_cached_song(rom_key)
                    print(f"[Identifier] From cache (romanized) ✅  Offset: {cache_offset:.0f}ms")
                    self.bridge.show_lyrics.emit(cached["lyrics"], False, cache_offset)
                    return
                if is_cached(base_key):
                    cached = get_cached_song(base_key)
                    print("[Identifier] Plain cache found — romanizing on the fly...")
                    from src.lyrics.fetcher import _apply_romanization
                    rom_lyrics = _apply_romanization(cached["lyrics"])
                    cache_song(rom_key, title, artist, rom_lyrics)
                    self.bridge.show_lyrics.emit(rom_lyrics, False, cache_offset)
                    return
            else:
                if is_cached(base_key):
                    cached = get_cached_song(base_key)
                    print(f"[Identifier] From cache ✅  Offset: {cache_offset:.0f}ms")
                    self.bridge.show_lyrics.emit(cached["lyrics"], False, cache_offset)
                    return
                if is_cached(rom_key):
                    cached = get_cached_song(rom_key)
                    print(f"[Identifier] From cache (romanized fallback) ✅  Offset: {cache_offset:.0f}ms")
                    self.bridge.show_lyrics.emit(cached["lyrics"], False, cache_offset)
                    return

            # ── fetch from APIs ───────────────────────────────────────
            lyrics_start = time.time()
            lyrics       = fetch_lyrics(title, artist)

            actual_lyrics_ms = (time.time() - lyrics_start) * 1000
            final_offset     = max(0, adjusted_offset + actual_lyrics_ms - LYRICS_MS)
            synced           = lyrics and any(e["t"] > 0 for e in lyrics)

            if lyrics and synced:
                cache_song(base_key, title, artist, lyrics)
                if romanize:
                    from src.lyrics.fetcher import _apply_romanization
                    rom_lyrics = _apply_romanization(lyrics)
                    cache_song(rom_key, title, artist, rom_lyrics)
                    self.bridge.show_lyrics.emit(rom_lyrics, False, final_offset)
                else:
                    self.bridge.show_lyrics.emit(lyrics, False, final_offset)
                print(f"[Identifier] Done. Offset: {final_offset:.0f}ms")

            elif lyrics and not synced:
                print("[Identifier] Unsynced lyrics — auto-scroll mode.")
                self.bridge.show_lyrics.emit(lyrics, False, final_offset)

            else:
                cache_song(base_key, title, artist, [])
                print("[Identifier] No lyrics found.")
                self.bridge.show_no_lyrics.emit()

        except Exception as e:
            print(f"[Identifier] Error: {e}")
            self.bridge.show_no_lyrics.emit()
        finally:
            self.identifying = False

    def _resync_position(self, shazam_id: str, offset_ms: float):
        cache_key = f"{shazam_id}_rom" if get_setting("romanize_lyrics") else shazam_id
        if is_cached(cache_key):
            cached = get_cached_song(cache_key)
            lyrics = cached.get("lyrics", [])
            if lyrics:
                print(f"[Identifier] Resyncing at {offset_ms/1000:.1f}s")
                self.bridge.show_lyrics.emit(lyrics, False, offset_ms)

    # ─── run ──────────────────────────────────────────────────────────────────

    def run(self):
        self.overlay.show()
        threading.Thread(target=self._change_detector_loop, daemon=True).start()
        threading.Thread(target=self._initial_identify,     daemon=True).start()
        print("[Main] LyricsLay started!")
        print("[Main] Ctrl+Shift+L → toggle overlay")
        print("[Main] Ctrl+Shift+K → force reidentify")
        exit_code = self.app.exec()
        self.running = False
        self._unregister_hotkeys()
        sys.exit(exit_code)

    def _initial_identify(self):
        try:
            time.sleep(1)
            audio = record_audio(duration=5)
            self._identify_and_load(audio)
        except Exception as e:
            print(f"[Main] Initial identify error: {e}")


if __name__ == "__main__":
    lyricslay = LyricsLayApp()
    lyricslay.run()