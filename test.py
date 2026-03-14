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




import sys
from PyQt6.QtWidgets import QApplication
from src.ui.settings_window import SettingsWindow
app = QApplication(sys.argv)
win = SettingsWindow()
win.show()
sys.exit(app.exec())
