import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from src.ui.overlay import LyricsOverlay

app = QApplication(sys.argv)
overlay = LyricsOverlay()
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
def debug_color():
    screen = QApplication.primaryScreen()
    dpr    = screen.devicePixelRatio()
    geo    = overlay.geometry()

    print(f"\n--- debug ---")
    print(f"DPR: {dpr}")
    print(f"Overlay pos: {geo.x()}, {geo.y()}, {geo.width()}x{geo.height()}")

    pixmap = screen.grabWindow(
        0, geo.x(), geo.y(), geo.width(), geo.height() + 80
    )
    print(f"Pixmap null: {pixmap.isNull()}")
    print(f"Pixmap size: {pixmap.width()}x{pixmap.height()}")

    image = pixmap.toImage()

    cx = image.width() // 2
    cy = image.height() // 2
    pixel = image.pixel(cx, cy)
    color = QColor(pixel)
    brightness = 0.299*color.red() + 0.587*color.green() + 0.114*color.blue()
    print(f"Center pixel RGB: {color.red()},{color.green()},{color.blue()}")
    print(f"Center brightness: {brightness:.1f}")
    print(f"Decision: {'DARK text' if brightness > 135 else 'WHITE text'}")
    
# run debug every 2 seconds
timer = QTimer()
timer.setInterval(2000)
timer.timeout.connect(debug_color)
timer.start()

sys.exit(app.exec())