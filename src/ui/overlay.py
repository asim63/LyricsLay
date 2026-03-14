from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt6.QtCore    import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui     import QFont, QColor, QScreen
from src.core        import settings

class LyricsOverlay(QWidget):
    """
    The floating lyrics window.
    Frameless, always-on-top, draggable, click-through.
    Shows 3 lines: past (faded), current (bold), next (faded).
    """

    # signal emitted when user double-clicks to toggle
    toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.s              = settings.load_settings()
        self.lyrics         = []      # list of {"t": float, "line": str}
        self.current_index  = 0       # which line is currently active
        self.dragging       = False
        self.drag_position  = QPoint()
        self.is_visible     = True
        self.is_caption_mode = False  # live caption mode flag

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._position_window()

    # ─── Window setup ────────────────────────────────────────────────

    def _setup_window(self):
        """Configure the window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint      |  # no title bar
            Qt.WindowType.WindowStaysOnTopHint     |  # always on top
            Qt.WindowType.Tool                        # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self.s.get("overlay_opacity", 0.92))
        self.setFixedWidth(self.s.get("overlay_width", 700))

    def _setup_ui(self):
        """Build the three lyric lines."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 14, 20, 14)

        # past line — small and faded
        self.past_label = QLabel("")
        self.past_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.past_label.setWordWrap(True)
        self._style_label(self.past_label, size=14, opacity=0.35)
        layout.addWidget(self.past_label)

        # current line — bold and bright
        self.current_label = QLabel("")
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_label.setWordWrap(True)
        self._style_label(self.current_label, size=22, opacity=1.0, bold=True)
        layout.addWidget(self.current_label)

        # next line — small and faded
        self.next_label = QLabel("")
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_label.setWordWrap(True)
        self._style_label(self.next_label, size=14, opacity=0.35)
        layout.addWidget(self.next_label)

        # caption badge — shown only in live caption mode
        self.caption_badge = QLabel("live caption · may not be exact")
        self.caption_badge.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.caption_badge.setFont(QFont("Arial", 9))
        self.caption_badge.setStyleSheet("color: rgba(255,255,255,0.35);")
        self.caption_badge.hide()
        layout.addWidget(self.caption_badge)

    def _style_label(self, label: QLabel, size: int,
                     opacity: float, bold: bool = False):
        """Apply consistent styling to a lyric label."""
        font = QFont("Arial", size)
        font.setBold(bold)
        label.setFont(font)
        alpha = int(opacity * 255)
        label.setStyleSheet(
            f"color: rgba(255, 255, 255, {alpha});"
            f"background: transparent;"
        )

    def _setup_timer(self):
        """
        Timer that checks every 100ms whether to advance
        to the next lyric line based on current playback time.
        """
        self.playback_time = 0.0
        self.timer = QTimer()
        self.timer.setInterval(100)   # check every 100ms
        self.timer.timeout.connect(self._tick)

    def _position_window(self):
        """Position the window at top center of the screen."""
        screen: QScreen = QApplication.primaryScreen()
        screen_width    = screen.geometry().width()
        window_width    = self.s.get("overlay_width", 700)
        x = (screen_width - window_width) // 2
        y = 40
        self.move(x, y)

    # ─── Lyrics control ──────────────────────────────────────────────

    def load_lyrics(self, lyrics: list, caption_mode: bool = False):
        """
        Load a new set of lyrics and start displaying them.
        lyrics: [{"t": 14.2, "line": "Good things don't last"}, ...]
        """
        self.lyrics          = lyrics
        self.current_index   = 0
        self.playback_time   = 0.0
        self.is_caption_mode = caption_mode

        # show or hide caption badge
        if caption_mode:
            self.caption_badge.show()
        else:
            self.caption_badge.hide()

        self._update_display(0)
        self.timer.start()
        print(f"[Overlay] Loaded {len(lyrics)} lines.")

    def _tick(self):
        """
        Called every 100ms.
        Advances playback time and updates displayed lines.
        """
        self.playback_time += 0.1

        if not self.lyrics:
            return

        # find which line should be showing right now
        new_index = self.current_index
        for i, entry in enumerate(self.lyrics):
            if entry["t"] <= self.playback_time:
                new_index = i

        # only update display if line changed
        if new_index != self.current_index:
            self.current_index = new_index
            self._update_display(new_index)

    def _update_display(self, index: int):
        """
        Updates the three labels based on current line index.
        """
        total = len(self.lyrics)
        if total == 0:
            return

        # get past, current, next lines safely
        past_text    = self.lyrics[index - 1]["line"] if index > 0 else ""
        current_text = self.lyrics[index]["line"]
        next_text    = self.lyrics[index + 1]["line"] if index < total - 1 else ""

        self.past_label.setText(past_text)
        self.current_label.setText(current_text)
        self.next_label.setText(next_text)

        # auto-detect background brightness and flip text color
        self._update_text_color()

    def set_loading(self):
        """Show a loading message while song is being identified."""
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("Identifying song...")
        self.next_label.setText("")
        self.lyrics = []

    def set_no_lyrics(self):
        """Show a message when no lyrics are found."""
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("No lyrics found")
        self.next_label.setText("")

    def clear(self):
        """Clear all labels and stop the timer."""
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("")
        self.next_label.setText("")
        self.lyrics = []

    # ─── Smart color ─────────────────────────────────────────────────

    def _update_text_color(self):
        """
        Samples the screen pixels behind the overlay
        and switches text to light or dark accordingly.
        """
        try:
            screen = QApplication.primaryScreen()
            # take a screenshot of the area behind the overlay
            geometry   = self.geometry()
            screenshot = screen.grabWindow(
                0,
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height()
            )
            image  = screenshot.toImage()

            # sample a grid of pixels and average their brightness
            total_brightness = 0
            samples = 0
            step = 20  # sample every 20px

            for x in range(0, geometry.width(), step):
                for y in range(0, geometry.height(), step):
                    pixel = image.pixel(x, y)
                    color = QColor(pixel)
                    # perceived brightness formula
                    brightness = (
                        0.299 * color.red() +
                        0.587 * color.green() +
                        0.114 * color.blue()
                    )
                    total_brightness += brightness
                    samples += 1

            avg = total_brightness / samples if samples > 0 else 128

            # light background → dark text, dark background → white text
            if avg > 128:
                self._set_text_dark()
            else:
                self._set_text_light()

        except Exception:
            # if anything fails, default to white text
            self._set_text_light()

    def _set_text_light(self):
        """White text for dark backgrounds."""
        self.current_label.setStyleSheet(
            "color: rgba(255,255,255,255); background: transparent; font-weight: bold;"
        )
        self.past_label.setStyleSheet(
            "color: rgba(255,255,255,90); background: transparent;"
        )
        self.next_label.setStyleSheet(
            "color: rgba(255,255,255,90); background: transparent;"
        )

    def _set_text_dark(self):
        """Dark text for light backgrounds."""
        self.current_label.setStyleSheet(
            "color: rgba(0,0,0,220); background: transparent; font-weight: bold;"
        )
        self.past_label.setStyleSheet(
            "color: rgba(0,0,0,100); background: transparent;"
        )
        self.next_label.setStyleSheet(
            "color: rgba(0,0,0,100); background: transparent;"
        )

    # ─── Dragging ────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """Start dragging on left click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging      = True
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        """Move window while dragging."""
        if self.dragging:
            self.move(
                event.globalPosition().toPoint() - self.drag_position
            )

    def mouseReleaseEvent(self, event):
        """Stop dragging, save new position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            # save position so it's remembered next launch
            pos = self.pos()
            settings.set("overlay_position", [pos.x(), pos.y()])

    def mouseDoubleClickEvent(self, event):
        """Double click toggles the overlay."""
        self.toggle_requested.emit()

    # ─── Show / Hide ─────────────────────────────────────────────────

    def toggle(self):
        """Toggle overlay visibility."""
        if self.is_visible:
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True

    def add_caption_line(self, line: str):
        """
        Used in live caption mode — adds a new transcribed line.
        Scrolls existing lines up.
        """
        past_text = self.current_label.text()
        self.past_label.setText(past_text)
        self.current_label.setText(line)
        self.next_label.setText("")