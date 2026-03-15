# update test.py
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.overlay import LyricsOverlay
from src.ui.tray    import SystemTray

app     = QApplication(sys.argv)
overlay = LyricsOverlay()
tray    = SystemTray(overlay, app)
overlay.show()

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