import sys
import threading
import time
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
    Bridge between background threads and the Qt main thread.
    Qt UI can only be updated from the main thread —
    we use signals to safely pass data across.
    """
    show_lyrics   = pyqtSignal(list, bool, float)   # lyrics, is_caption_mode
    show_loading  = pyqtSignal()
    show_no_lyrics = pyqtSignal()
    song_changed  = pyqtSignal(str, str)     # title, artist


class LyricsLayApp:
    """
    Main application controller.
    Manages the audio loop, recognition, lyrics fetching,
    hotkey, and connects everything together.
    """

    def __init__(self):
        self.app      = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # keep running in tray

        self.overlay  = LyricsOverlay()
        self.tray     = SystemTray(self.overlay, self.app)
        self.bridge   = SignalBridge()
        self.s        = settings.load_settings()

        self.current_song_id  = None   # shazam_id of currently playing song
        self.running          = True   # controls the audio loop
        self.retries          = 0      # failed recognition attempts

        self._connect_signals()
        self._register_hotkey()

    def _connect_signals(self):
        self.bridge.show_lyrics.connect(self.overlay.load_lyrics)
        self.bridge.show_loading.connect(self.overlay.set_loading)
        self.bridge.show_no_lyrics.connect(self.overlay.set_no_lyrics)
        self.overlay.toggle_requested.connect(self._toggle)
        self.tray.toggle_action.triggered.disconnect()
        self.tray.toggle_action.triggered.connect(self._toggle)
        
    def _toggle(self):
        """Toggle overlay and sync tray menu text."""
        self.overlay.toggle()
        self.tray.update_toggle_text()

    def _register_hotkey(self):
        try:
            from pynput import keyboard

            hotkey_str = self.s.get("hotkey", "<ctrl>+<shift>+l")

            def on_activate():
                print(f"[Hotkey] Triggered!")
                QTimer.singleShot(0, self._toggle)

            # pynput needs the listener kept alive
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
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()

    def re_register_hotkey(self, new_hotkey: str):
        """Called when user changes hotkey in settings."""
        self._unregister_hotkey()
        self.s = settings.load_settings()
        self._register_hotkey()
        print(f"[Hotkey] Re-registered: {new_hotkey}")

    # ─── Audio loop ──────────────────────────────────────────────────

    def _audio_loop(self):
        """
        Runs in a background thread forever.
        Continuously listens, identifies, and loads lyrics.
        """
        print("[Main] Audio loop started.")

        while self.running:
            try:
                # show loading indicator
                self.bridge.show_loading.emit()

                # record audio
                audio = record_audio()

                # identify song
                song = recognise_song(audio)

                if song is None:
                    self.retries += 1
                    print(f"[Main] No match — retry {self.retries}")

                    if self.retries >= 3:
                        # switch to live captions after 3 fails
                        print("[Main] Switching to live captions...")
                        self.retries = 0
                        # for now show no lyrics — caption.py handles this
                        self.bridge.show_no_lyrics.emit()
                        time.sleep(5)
                    continue

                # reset retries on success
                self.retries = 0
                shazam_id    = song["shazam_id"]
                title        = song["title"]
                artist       = song["artist"]

                # skip if same song still playing
                if shazam_id == self.current_song_id:
                    print(f"[Main] Same song — {title}")
                    # re-sync position in case user skipped
                    self._resync_position(shazam_id)
                    time.sleep(8)
                    continue

                # new song detected!
                self.current_song_id = shazam_id
                print(f"[Main] New song: {title} by {artist}")
                self.bridge.song_changed.emit(title, artist)

                # check cache first
                if is_cached(shazam_id):
                    cached = get_cached_song(shazam_id)
                    print(f"[Main] Loaded from cache!")
                    self.bridge.show_lyrics.emit(
                        cached["lyrics"], False,
                        song.get("offset_ms", 0.0)
                    )
                    # wait longer before re-checking
                    time.sleep(30)
                    continue

                # fetch lyrics from APIs
                lyrics = fetch_lyrics(title, artist)

                if lyrics:
                    # save to cache
                    cache_song(shazam_id, title, artist, lyrics)
                    self.bridge.show_lyrics.emit(
                        lyrics, False,
                        song.get("offset_ms", 0.0)
                    )
                    time.sleep(30)
                else:
                    # no lyrics found — show message
                    print("[Main] No lyrics found.")
                    self.bridge.show_no_lyrics.emit()
                    time.sleep(10)

            except Exception as e:
                print(f"[Main] Audio loop error: {e}")
                time.sleep(5)

    def run(self):
        """Start everything and run the app."""
        # show overlay
        self.overlay.show()

        # start audio loop in background thread
        self.audio_thread = threading.Thread(
            target=self._audio_loop,
            daemon=True   # dies when app closes
        )
        self.audio_thread.start()

        print("[Main] LyricsLay started!")
        print("[Main] Press Ctrl+Shift+L to toggle lyrics.")

        # run Qt event loop
        exit_code = self.app.exec()

        # cleanup
        self.running = False
        self._unregister_hotkey()
        sys.exit(exit_code)
    
    def _resync_position(self, shazam_id: str):
        """
        Re-syncs lyrics position after user skips within a song.
        Re-records audio to get current position from Shazam.
        """
        if is_cached(shazam_id):
            cached = get_cached_song(shazam_id)
            lyrics = cached.get("lyrics", [])
            if lyrics:
                print("[Main] Re-syncing position...")
                try:
                    audio  = record_audio()
                    song   = recognise_song(audio)
                    offset = song.get("offset_ms", 0.0) if song else 0.0
                except Exception:
                    offset = 0.0

                self.bridge.show_lyrics.emit(lyrics, False, offset)
                print(f"[Main] Re-synced at offset: {offset}ms")


if __name__ == "__main__":
    lyricslay = LyricsLayApp()
    lyricslay.run()
