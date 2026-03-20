import sys
import threading
import time
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import QTimer, pyqtSignal, QObject
from src.core        import settings
from src.core.audio      import record_audio
from src.core.recognizer import recognise_song
from src.core.cache      import is_cached, get_cached_song, cache_song
from src.lyrics.fetcher  import fetch_lyrics
from src.ui.overlay      import LyricsOverlay
from src.ui.tray         import SystemTray


class SignalBridge(QObject):
    """
    Bridge between background threads and Qt main thread.
    Qt UI can only be updated from the main thread.
    """
    show_lyrics    = pyqtSignal(list, bool, float)
    show_loading   = pyqtSignal()
    show_no_lyrics = pyqtSignal()
    song_changed   = pyqtSignal(str, str)
    toggle_overlay = pyqtSignal()


class LyricsLayApp:
    """
    Main application controller.
    Two-thread architecture:
    - Fast detector: checks every 2s if audio changed
    - Identifier: full Shazam call when change detected
    """

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.overlay = LyricsOverlay()
        self.tray    = SystemTray(self.overlay, self.app)
        self.bridge  = SignalBridge()
        self.s       = settings.load_settings()

        self.current_song_id     = None
        self.current_fingerprint = None
        self.running             = True
        self.identifying         = False

        self._connect_signals()
        self._register_hotkey()

    # ─── Signals ─────────────────────────────────────────────────────

    def _connect_signals(self):
        """Connect bridge signals to overlay and tray."""
        self.bridge.show_lyrics.connect(self.overlay.load_lyrics)
        self.bridge.show_loading.connect(self.overlay.set_loading)
        self.bridge.show_no_lyrics.connect(self.overlay.set_no_lyrics)
        self.bridge.toggle_overlay.connect(self._toggle)

        self.overlay.toggle_requested.connect(self._toggle)
        self.tray.toggle_action.triggered.disconnect()
        self.tray.toggle_action.triggered.connect(self._toggle)

    def _toggle(self):
        """Toggle overlay and sync tray menu text."""
        self.overlay.toggle()
        self.tray.update_toggle_text()

    # ─── Hotkey ──────────────────────────────────────────────────────

    def _register_hotkey(self):
        """Register global hotkey in background thread."""
        try:
            from pynput import keyboard

            hotkey_str = self.s.get("hotkey", "<ctrl>+<shift>+l")

            def on_activate():
                print(f"[Hotkey] Triggered!")
                # emit signal — safely crosses thread boundary
                self.bridge.toggle_overlay.emit()

            self.hotkey = keyboard.GlobalHotKeys({
                hotkey_str: on_activate
            })
            self.hotkey.daemon = True
            self.hotkey.start()
            print(f"[Hotkey] Registered: {hotkey_str}")

        except Exception as e:
            print(f"[Hotkey] Failed: {e}")

    def _unregister_hotkey(self):
        """Stop the hotkey listener."""
        if hasattr(self, 'hotkey'):
            self.hotkey.stop()

    def re_register_hotkey(self, new_hotkey: str):
        """Called when user changes hotkey in settings."""
        self._unregister_hotkey()
        self.s = settings.load_settings()
        self._register_hotkey()

    # ─── Fast change detector ─────────────────────────────────────────

    def _change_detector_loop(self):
        """
        Runs every 2 seconds.
        Records a short 2s clip and checks if audio
        changed significantly from the current song.
        If changed — triggers full identification.
        """
        print("[Detector] Started.")

        # wait for first identification to complete
        time.sleep(8)

        while self.running:
            try:
                if self.identifying:
                    time.sleep(1)
                    continue

                # short 2s sample — just enough to detect change
                audio       = record_audio(duration=2)
                fingerprint = self._quick_fingerprint(audio)

                if self.current_fingerprint is None:
                    # first run — trigger identification
                    self.current_fingerprint = fingerprint
                    self._trigger_identification(audio)

                elif self._audio_changed(fingerprint,
                                         self.current_fingerprint):
                    print("[Detector] Audio change detected!")
                    self.current_fingerprint = fingerprint
                    self.current_song_id     = None
                    self._trigger_identification(audio)

                # check every 2 seconds
                time.sleep(2)

            except Exception as e:
                print(f"[Detector] Error: {e}")
                time.sleep(3)

    def _quick_fingerprint(self, audio: np.ndarray) -> np.ndarray:
        """
        Creates a stable spectral fingerprint.
        Returns energy per frequency band — more unique
        and stable than simple RMS energy.
        """
        if len(audio) == 0:
            return np.zeros(8)

        # split into 8 frequency-like bands using chunking
        # more stable than raw energy sum
        chunk_size = max(1, len(audio) // 8)
        bands      = []

        for i in range(8):
            start  = i * chunk_size
            end    = start + chunk_size
            chunk  = audio[start:end].astype(float)
            if len(chunk) > 0:
                # use median instead of mean — resistant to spikes
                energy = float(np.sqrt(np.median(chunk ** 2)))
            else:
                energy = 0.0
            bands.append(energy)

        return np.array(bands)

    def _audio_changed(self,
                       new_fp: np.ndarray,
                       old_fp: np.ndarray) -> bool:
        """
        Compares two fingerprints.
        Only returns True if audio changed significantly.
        Uses cosine distance — stable against volume changes.
        """
        # handle silence → music transition
        old_energy = float(np.sum(old_fp))
        new_energy = float(np.sum(new_fp))

        # if both are silence — no change
        if old_energy < 50 and new_energy < 50:
            return False

        # if one is silence and other isn't — definite change
        if old_energy < 50 or new_energy < 50:
            return True

        # cosine similarity — volume independent
        dot      = float(np.dot(new_fp, old_fp))
        norm     = float(np.linalg.norm(new_fp) *
                         np.linalg.norm(old_fp))
        if norm == 0:
            return False

        similarity = dot / norm
        changed    = similarity < 0.85  # 85% similarity threshold

        if changed:
            print(f"[Detector] Similarity: {similarity:.2%} → change!")
        return changed

    def _trigger_identification(self, audio: np.ndarray):
        """
        Starts full identification in a separate thread.
        Passes already-recorded audio to avoid re-recording.
        """
        if self.identifying:
            return

        thread = threading.Thread(
            target=self._identify_and_load,
            args=(audio,),
            daemon=True
        )
        thread.start()

    # ─── Full identifier ──────────────────────────────────────────────

    def _identify_and_load(self, audio: np.ndarray):
        """
        Full identification pipeline:
        Audio → Shazam → Lyrics → Overlay
        Compensates for recording + API delay in offset.
        """
        self.identifying = True
        self.bridge.show_loading.emit()

        try:
            print("[Identifier] Identifying song...")

            # record start time to measure total pipeline delay
            pipeline_start = time.time()

            # if audio is only 2s, record a full 5s for Shazam accuracy
            if len(audio) < 16000 * 4:
                audio = record_audio(duration=5)

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

            print(f"[Identifier] {title} by {artist} "
                  f"(raw offset: {offset_ms:.0f}ms)")

            # ── compensate for pipeline delay ─────────────────────────
            # offset_ms = where in song Shazam heard us
            # We add:
            #   + sample duration (audio we recorded)
            #   + shazam API delay
            #   + estimated lyrics fetch time
            SAMPLE_MS    = config.SAMPLE_DURATION * 1000
            LYRICS_MS    = 1500   # avg lyrics fetch time
            pipeline_ms  = (time.time() - pipeline_start) * 1000

            adjusted_offset = (
                offset_ms    +
                SAMPLE_MS    +
                shazam_delay +
                LYRICS_MS
            )

            print(f"[Identifier] Adjusted offset: "
                  f"{adjusted_offset:.0f}ms "
                  f"(pipeline: {pipeline_ms:.0f}ms)")

            # same song — just resync position
            if shazam_id == self.current_song_id:
                print("[Identifier] Same song — resyncing.")
                self._resync_position(shazam_id, adjusted_offset)
                return

            # new song!
            self.current_song_id = shazam_id
            self.bridge.song_changed.emit(title, artist)

            # ── fetch lyrics ──────────────────────────────────────────
            lyrics_start = time.time()

            if is_cached(shazam_id):
                cached = get_cached_song(shazam_id)
                print("[Identifier] Loaded from cache!")
                # cache is instant so no extra delay needed
                self.bridge.show_lyrics.emit(
                    cached["lyrics"], False, adjusted_offset
                )
                return

            lyrics = fetch_lyrics(title, artist)

            # measure actual lyrics fetch time and add it
            actual_lyrics_ms = (time.time() - lyrics_start) * 1000
            final_offset     = adjusted_offset + actual_lyrics_ms - LYRICS_MS
            final_offset     = max(0, final_offset)

            if lyrics:
                cache_song(shazam_id, title, artist, lyrics)
                self.bridge.show_lyrics.emit(lyrics, False, final_offset)
                print(f"[Identifier] Final offset: {final_offset:.0f}ms")
            else:
                print("[Identifier] No lyrics found.")
                self.bridge.show_no_lyrics.emit()

        except Exception as e:
            print(f"[Identifier] Error: {e}")
            self.bridge.show_no_lyrics.emit()

        finally:
            self.identifying = False

    def _resync_position(self, shazam_id: str, offset_ms: float):
        """Resync lyrics to current position after skip."""
        if is_cached(shazam_id):
            cached = get_cached_song(shazam_id)
            lyrics = cached.get("lyrics", [])
            if lyrics:
                print(f"[Identifier] Resyncing at {offset_ms:.0f}ms")
                self.bridge.show_lyrics.emit(lyrics, False, offset_ms)

    # ─── Run ─────────────────────────────────────────────────────────

    def run(self):
        """Start everything and run the app."""
        self.overlay.show()

        # start change detector in background thread
        detector_thread = threading.Thread(
            target=self._change_detector_loop,
            daemon=True
        )
        detector_thread.start()

        # also start initial identification immediately
        init_thread = threading.Thread(
            target=self._initial_identify,
            daemon=True
        )
        init_thread.start()

        print("[Main] LyricsLay started!")
        print("[Main] Toggle: Ctrl+Shift+L")

        exit_code = self.app.exec()

        self.running = False
        self._unregister_hotkey()
        sys.exit(exit_code)

    def _initial_identify(self):
        """
        Run identification immediately on startup
        in case music is already playing.
        """
        try:
            time.sleep(1)  # let UI settle first
            audio = record_audio(duration=5)
            self._identify_and_load(audio)
        except Exception as e:
            print(f"[Main] Initial identify error: {e}")


if __name__ == "__main__":
    import config
    lyricslay = LyricsLayApp()
    lyricslay.run()