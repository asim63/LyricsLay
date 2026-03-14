# from src.core.audio import record_audio
# from src.core.recognizer import recognise_song
# from src.lyrics.fetcher import fetch_lyrics
# from src.core.cache import cache_song, is_cached

# print("Starting full pipeline test...")
# print("Play some music!")

# audio = record_audio(5)
# song = recognise_song(audio)

# if song:
#     print(f"Song: {song['title']} by {song['artist']}")

#     if is_cached(song['shazam_id']):
#         print("Already cached — would load instantly!")
#     else:
#         lyrics = fetch_lyrics(song['title'], song['artist'])
#         if lyrics:
#             cache_song(song['shazam_id'], song['title'], song['artist'], lyrics)
#             print(f"Lyrics fetched and cached — {len(lyrics)} lines")
#             print("First 3 lines:")
#             for line in lyrics[:3]:
#                 print(f"  {line}")
#         else:
#             print("No lyrics found")
# else:
#     print("Could not identify song")




# import sys
# from PyQt6.QtWidgets import QApplication
# from src.ui.settings_window import SettingsWindow
# app = QApplication(sys.argv)
# win = SettingsWindow()
# win.show()
# sys.exit(app.exec())

# add this to test.py temporarily and run it
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.ui.overlay import LyricsOverlay

app = QApplication(sys.argv)
overlay = LyricsOverlay()
overlay.show()

# load fake lyrics to see the scrolling
fake_lyrics = [
    {"t": 0.0,  "line": ""},
    {"t": 1.0,  "line": "A long long time ago"},
    {"t": 4.0,  "line": "I can still remember"},
    {"t": 7.0,  "line": "How that music used to make me smile"},
    {"t": 11.0, "line": "And I knew if I had my chance"},
    {"t": 14.0, "line": "That I could make those people dance"},
    {"t": 17.0, "line": "And maybe they'd be happy for a while"},
    {"t": 21.0, "line": "But February made me shiver"},
    {"t": 24.0, "line": "With every paper I'd deliver"},
    {"t": 27.0, "line": "Bad news on the doorstep"},
]

overlay.load_lyrics(fake_lyrics)
sys.exit(app.exec())
