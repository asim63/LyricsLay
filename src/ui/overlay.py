from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QFrame, QSizeGrip
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize, pyqtSignal, QEvent
from PyQt6.QtGui  import QFont, QCursor
from src.core     import settings
import config

class LyricsOverlay(QWidget):
    """
    The floating lyrics window.
    Frameless, always-on-top, semi-transparent pill background.
    Shows 3 lines: past (faded), current (bold), next (faded).
    - Drag via grip handle or Alt+click anywhere
    - Resize by dragging bottom-right corner
    - Click-through everywhere except grip
    """

    toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.s               = settings.load_settings()
        self.lyrics          = []
        self.current_index   = 0
        self.dragging        = False
        self.drag_position   = QPoint()
        self.is_visible      = True
        self.is_caption_mode = False

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._position_window()

    # ─── Window setup ────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # start as click-through
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.setMouseTracking(True)
        # set initial size from settings
        w = self.s.get("overlay_width", 700)
        self.resize(w, 120)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── container row: pill + grip ────────────────────────────────
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        # ── pill ──────────────────────────────────────────────────────
        self.pill = QFrame()
        self.pill.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.55);
                border-radius: 16px;
            }
        """)

        pill_layout = QVBoxLayout(self.pill)
        pill_layout.setSpacing(8)
        pill_layout.setContentsMargins(24, 14, 24, 14)

        # past line
        self.past_label = QLabel("")
        self.past_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.past_label.setWordWrap(True)
        self.past_label.setFont(QFont("Arial", config.FONT_SIZE_PAST))
        self.past_label.setStyleSheet(
            "color: rgba(255,255,255,90); background: transparent;"
        )
        pill_layout.addWidget(self.past_label)

        # current line
        self.current_label = QLabel("")
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_label.setWordWrap(True)
        self.current_label.setFont(
            QFont("Arial", config.FONT_SIZE_CURRENT))
        self.current_label.setStyleSheet(
            "color: rgba(255,255,255,255);"
            "background: transparent;"
            "font-weight: bold;"
        )
        pill_layout.addWidget(self.current_label)

        # next line
        self.next_label = QLabel("")
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_label.setWordWrap(True)
        self.next_label.setFont(QFont("Arial", config.FONT_SIZE_NEXT))
        self.next_label.setStyleSheet(
            "color: rgba(255,255,255,90); background: transparent;"
        )
        pill_layout.addWidget(self.next_label)

        # caption badge
        self.caption_badge = QLabel("live caption · may not be exact")
        self.caption_badge.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.caption_badge.setFont(QFont("Arial", 9))
        self.caption_badge.setStyleSheet(
            "color: rgba(255,255,255,80); background: transparent;"
        )
        self.caption_badge.hide()
        pill_layout.addWidget(self.caption_badge)

        container_layout.addWidget(self.pill, stretch=1)

        # ── right column: grip + size grip ───────────────────────────
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(4)

        # drag grip handle
        self.grip = QLabel("⠿")
        self.grip.setFixedWidth(20)
        self.grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grip.setFont(QFont("Arial", 16))
        self.grip.setStyleSheet("""
            color: rgba(255,255,255,140);
            background: rgba(0,0,0,0.45);
            border-radius: 8px;
            padding: 8px 0px;
        """)
        self.grip.setCursor(Qt.CursorShape.SizeAllCursor)
        self.grip.installEventFilter(self)
        right_col.addWidget(self.grip, stretch=1)

        # resize grip — bottom right corner
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        self.size_grip.setStyleSheet(
            "background: rgba(255,255,255,60); border-radius: 4px;"
        )
        self.size_grip.installEventFilter(self)
        right_col.addWidget(
            self.size_grip, 0, Qt.AlignmentFlag.AlignRight
        )

        container_layout.addLayout(right_col)

        container_widget = QWidget()
        container_widget.setStyleSheet("background: transparent;")
        container_widget.setLayout(container_layout)
        outer.addWidget(container_widget)

    def _setup_timer(self):
        self.playback_time = 0.0
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)

    def _position_window(self):
        """
        Default: top center.
        If user has moved it before, restore that position.
        """
        screen       = QApplication.primaryScreen()
        screen_w     = screen.geometry().width()
        window_w     = self.width()

        # default = top center
        default_x = (screen_w - window_w) // 2
        default_y = 40

        saved_pos = self.s.get("overlay_position", None)
        if (saved_pos and isinstance(saved_pos, list)
                and len(saved_pos) == 2):
            # restore saved position
            self.move(saved_pos[0], saved_pos[1])
        else:
            # first launch — top center
            self.move(default_x, default_y)

    # ─── Lyrics control ──────────────────────────────────────────────

    def load_lyrics(self, lyrics: list, caption_mode: bool = False):
        self.lyrics          = lyrics
        self.current_index   = 0
        self.playback_time   = 0.0
        self.is_caption_mode = caption_mode

        if caption_mode:
            self.caption_badge.show()
        else:
            self.caption_badge.hide()

        self._update_display(0)
        self.timer.start()
        print(f"[Overlay] Loaded {len(lyrics)} lines.")

    def _tick(self):
        self.playback_time += 0.1
        if not self.lyrics:
            return

        new_index = self.current_index
        for i, entry in enumerate(self.lyrics):
            if entry["t"] <= self.playback_time:
                new_index = i

        if new_index != self.current_index:
            self.current_index = new_index
            self._update_display(new_index)

    def _update_display(self, index: int):
        total = len(self.lyrics)
        if total == 0:
            return

        past_text    = self.lyrics[index - 1]["line"] if index > 0 else ""
        current_text = self.lyrics[index]["line"]
        next_text    = (self.lyrics[index + 1]["line"]
                        if index < total - 1 else "")

        self.past_label.setText(past_text)
        self.current_label.setText(current_text)
        self.next_label.setText(next_text)

    def set_loading(self):
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("Identifying song...")
        self.next_label.setText("")
        self.lyrics = []

    def set_no_lyrics(self):
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("No lyrics found")
        self.next_label.setText("")

    def clear(self):
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("")
        self.next_label.setText("")
        self.lyrics = []

    def add_caption_line(self, line: str):
        past_text = self.current_label.text()
        self.past_label.setText(past_text)
        self.current_label.setText(line)
        self.next_label.setText("")

    # ─── Show / Hide ─────────────────────────────────────────────────

    def toggle(self):
        if self.is_visible:
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True

    # ─── Drag & Resize ───────────────────────────────────────────────

    def _enable_drag(self):
        """Disable click-through so mouse events reach window."""
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
        )

    def _disable_drag(self):
        """Re-enable click-through."""
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

    def eventFilter(self, obj, event):
        """
        Grip/size_grip hover → enable mouse events.
        Leave → re-enable click-through.
        """
        if obj in (self.grip, self.size_grip):
            if event.type() == QEvent.Type.Enter:
                self._enable_drag()
            elif event.type() == QEvent.Type.Leave:
                if not self.dragging:
                    self._disable_drag()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Drag if clicking grip or holding Alt."""
        alt_held = bool(
            event.modifiers() & Qt.KeyboardModifier.AltModifier
        )
        on_grip = self.grip.geometry().contains(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if alt_held or on_grip:
                self.dragging      = True
                self.drag_position = (
                    event.globalPosition().toPoint() -
                    self.frameGeometry().topLeft()
                )

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(
                event.globalPosition().toPoint() - self.drag_position
            )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            # save position AND size
            pos = self.pos()
            settings.set("overlay_position", [pos.x(), pos.y()])
            settings.set("overlay_width", self.width())
            self._disable_drag()

    def resizeEvent(self, event):
        """Save size when user resizes via size grip."""
        super().resizeEvent(event)
        settings.set("overlay_width", self.width())

    def mouseDoubleClickEvent(self, event):
        on_grip = self.grip.geometry().contains(event.pos())
        if on_grip:
            self.toggle_requested.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self._enable_drag()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            if not self.dragging:
                self._disable_drag()