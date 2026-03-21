from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QFrame
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QSize,
    pyqtSignal, QEvent
)
from PyQt6.QtGui  import QFont
from src.core     import settings
import config

class RestartButton(QWidget):
    """
    Separate always-interactive window — restart button.
    Sits on the left side of the overlay.
    """
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Restart LyricsLay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("↺")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 13))
        label.setStyleSheet("""
            color: rgba(255,255,255,140);
            background: rgba(0,0,0,0.50);
            border-radius: 8px 8px 0px 0px;
            padding: 2px;
        """)
        layout.addWidget(label)

    def reposition(self):
        pos = self.overlay.pos()
        self.move(
            pos.x() - self.width() - 4,
            pos.y()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            import os, sys
            print("[Overlay] Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)


class ReidentifyButton(QWidget):
    """
    Separate always-interactive window — force reidentify button.
    Sits below restart button on the left side.
    """
    def __init__(self, overlay, on_click):
        super().__init__()
        self.overlay  = overlay
        self.on_click = on_click

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Force reidentify (Ctrl+Shift+K)")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("⟳")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 13))
        label.setStyleSheet("""
            color: rgba(255,255,255,140);
            background: rgba(0,0,0,0.50);
            border-radius: 0px 0px 8px 8px;
            padding: 2px;
        """)
        layout.addWidget(label)

    def reposition(self):
        pos = self.overlay.pos()
        self.move(
            pos.x() - self.width() - 4,
            pos.y() + self.overlay.height() - self.height()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.on_click:
                self.on_click()


class CloseButton(QWidget):
    """
    Separate always-interactive window — close overlay button.
    Sits at the top of the right side.
    """
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Hide overlay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("×")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 14))
        label.setStyleSheet("""
            color: rgba(255,255,255,140);
            background: rgba(0,0,0,0.50);
            border-radius: 8px 8px 0px 0px;
            padding: 2px;
        """)
        layout.addWidget(label)

    def reposition(self):
        pos = self.overlay.pos()
        self.move(
            pos.x() + self.overlay.width() + 4,
            pos.y()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.overlay.toggle()
class GripHandle(QWidget):
    """
    Separate always-interactive window for dragging.
    Sits to the right of the main overlay.
    """

    def __init__(self, overlay):
        super().__init__()
        self.overlay       = overlay
        self.dragging      = False
        self.drag_position = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(24, 75)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Drag to move · Double-click to hide")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("⠿")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 16))
        label.setStyleSheet("""
            color: rgba(255,255,255,160);
            background: rgba(0,0,0,0.50);
            border-radius: 8px 8px 0px 0px;
            padding: 4px;
        """)
        layout.addWidget(label)

    def reposition(self):
        """Sit just to the right of the overlay, top half."""
        pos = self.overlay.pos()
        self.move(
            pos.x() + self.overlay.width() + 4,
            pos.y()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging      = True
            self.drag_position = (
                event.globalPosition().toPoint() -
                self.overlay.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = (
                event.globalPosition().toPoint() - self.drag_position
            )
            self.overlay.move(new_pos)
            self.reposition()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            pos = self.overlay.pos()
            settings.set("overlay_position", [pos.x(), pos.y()])

    def mouseDoubleClickEvent(self, event):
        """Double click to toggle overlay."""
        self.overlay.toggle_requested.emit()


class ResizeHandle(QWidget):
    """
    Separate always-interactive window for resizing.
    Sits just below the grip handle, to the right of the overlay.
    """

    def __init__(self, overlay):
        super().__init__()
        self.overlay            = overlay
        self.resizing           = False
        self.resize_start_pos   = QPoint()
        self.resize_start_size  = QSize()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("Drag to resize")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("⌟")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Arial", 14))
        label.setStyleSheet("""
            color: rgba(255,255,255,140);
            background: rgba(0,0,0,0.50);
            border-radius: 0px 0px 8px 8px;
        """)
        layout.addWidget(label)

    def reposition(self):
        """Sit just below the grip handle."""
        pos = self.overlay.pos()
        self.move(
            pos.x() + self.overlay.width() + 4,
            pos.y() + self.overlay.height() - self.height()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing           = True
            self.resize_start_pos   = event.globalPosition().toPoint()
            self.resize_start_size  = self.overlay.size()

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = (
                event.globalPosition().toPoint() -
                self.resize_start_pos
            )
            new_w = max(300, self.resize_start_size.width()  + delta.x())
            new_h = max(80,  self.resize_start_size.height() + delta.y())
            self.overlay.resize(new_w, new_h)
            self.overlay.grip_handle.reposition()
            self.reposition()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            settings.set("overlay_width",  self.overlay.width())
            settings.set("overlay_height", self.overlay.height())


class LyricsOverlay(QWidget):
    """
    The floating lyrics window.
    Frameless, always-on-top, semi-transparent pill background.
    Shows 3 lines: past (faded), current (bold), next (faded).
    - Drag via GripHandle or Alt+click
    - Resize via ResizeHandle
    - Click-through everywhere on main window
    - Smooth animation on line change
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
        self._frozen_seconds   = 0.0
        self._showing_no_audio = False

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._position_window()

        # right side handles
        self.close_handle  = CloseButton(self)
        self.grip_handle   = GripHandle(self)
        self.resize_handle = ResizeHandle(self)

        # left side buttons — need callbacks from main.py
        self.restart_button    = RestartButton(self)
        self.reidentify_button = ReidentifyButton(self, on_click=None)
        # on_click set by main.py after init
        
        self._anim_timer              = None
        self._anim_targets            = {}
        self._unsynced_secs_per_line  = 6.0  # default fallback

    # ─── Window setup ────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        w = self.s.get("overlay_width",  700)
        h = self.s.get("overlay_height", 120)
        self.resize(w, h)

        QTimer.singleShot(100, self._apply_clickthrough)

    def _apply_clickthrough(self):
        try:
            import ctypes
            hwnd              = int(self.winId())
            GWL_EXSTYLE       = -20
            WS_EX_LAYERED     = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
            print("[Overlay] Click-through enabled.")
        except Exception as e:
            print(f"[Overlay] Click-through failed: {e}")

    def _enable_drag(self):
        try:
            import ctypes
            hwnd              = int(self.winId())
            GWL_EXSTYLE       = -20
            WS_EX_LAYERED     = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style & ~WS_EX_TRANSPARENT
            )
        except Exception:
            pass

    def _disable_drag(self):
        try:
            import ctypes
            hwnd              = int(self.winId())
            GWL_EXSTYLE       = -20
            WS_EX_LAYERED     = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        except Exception:
            pass

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

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

        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self.pill, stretch=1)

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
        screen   = QApplication.primaryScreen()
        screen_w = screen.geometry().width()
        screen_h = screen.geometry().height()
        window_w = self.width()

        default_x = (screen_w - window_w) // 2
        default_y = 40

        saved_pos = self.s.get("overlay_position", None)
        if (saved_pos and
                isinstance(saved_pos, list) and
                len(saved_pos) == 2):
            x, y = saved_pos[0], saved_pos[1]
            if (x < 0 or x > screen_w - 100 or
                    y < 0 or y > screen_h - 50):
                self.move(default_x, default_y)
            else:
                self.move(x, y)
        else:
            self.move(default_x, default_y)

    # ─── Show / Hide ─────────────────────────────────────────────────

    def show(self):
        super().show()
        self.close_handle.reposition()
        self.close_handle.show()
        self.grip_handle.reposition()
        self.grip_handle.show()
        self.resize_handle.reposition()
        self.resize_handle.show()
        self.restart_button.reposition()
        self.restart_button.show()
        self.reidentify_button.reposition()
        self.reidentify_button.show()

    def hide(self):
        super().hide()
        self.close_handle.hide()
        self.grip_handle.hide()
        self.resize_handle.hide()
        self.restart_button.hide()
        self.reidentify_button.hide()

    def toggle(self):
        if self.is_visible:
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True

    def moveEvent(self, event):
        super().moveEvent(event)
        for h in ['close_handle', 'grip_handle', 'resize_handle',
                  'restart_button', 'reidentify_button']:
            if hasattr(self, h):
                getattr(self, h).reposition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for h in ['close_handle', 'grip_handle', 'resize_handle',
                  'restart_button', 'reidentify_button']:
            if hasattr(self, h):
                getattr(self, h).reposition()
    # ─── Lyrics control ──────────────────────────────────────────────

    def load_lyrics(self, lyrics: list,
                    caption_mode: bool = False,
                    start_ms: float = 0.0):

        self.timer.stop()
        self.lyrics          = lyrics
        self.current_index   = 0
        self.is_caption_mode = False  # unused for now

        # no lyrics at all
        if not lyrics:
            self.caption_badge.hide()
            return

        # check if synced
        synced = any(entry["t"] > 0 for entry in lyrics)

        if synced:
            self.playback_time = start_ms / 1000.0
            self.caption_badge.hide()
        else:
            # unsynced — show notice, calculate scroll pace
            self.playback_time = 0.0
            self.caption_badge.setText("lyrics unsynced · timing may be off")
            self.caption_badge.show()

            estimated_duration = max(
                start_ms / 1000.0 * 2,
                210.0
            )
            self._unsynced_secs_per_line = (
                estimated_duration / max(len(lyrics), 1)
            )
            print(f"[Overlay] Unsynced — "
                  f"{self._unsynced_secs_per_line:.1f}s per line")

        # find starting index for synced lyrics
        start_index = 0
        if synced:
            for i, entry in enumerate(lyrics):
                if entry["t"] <= self.playback_time:
                    start_index = i

            # safety reset if too far
            if start_index >= len(lyrics) - 3:
                print("[Overlay] Offset too far — resetting.")
                start_index        = 0
                self.playback_time = 0.0

        self.current_index = start_index
        self._set_display_instant(start_index)
        self.timer.start()
        print(f"[Overlay] Loaded {len(lyrics)} lines "
              f"({'synced' if synced else 'unsynced'}) "
              f"starting at line {start_index}.")
        
    def _set_display_instant(self, index: int):
        """Set labels instantly — no animation, used on first load."""
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

        self._restore_label_style(self.past_label,    90)
        self._restore_label_style(self.current_label, 255)
        self._restore_label_style(self.next_label,    90)

    def _restore_label_style(self, label: QLabel, alpha: int = 255):
        """Restore clean final style for a label."""
        is_current = (label is self.current_label)
        bold = "font-weight: bold;" if is_current else ""
        size = config.FONT_SIZE_CURRENT if is_current else config.FONT_SIZE_PAST
        label.setFont(QFont("Arial", size))
        label.setStyleSheet(
            f"color: rgba(255,255,255,{alpha});"
            f"background: transparent;"
            f"{bold}"
        )

    def _tick(self):
        self.playback_time += 0.1
        if not self.lyrics:
            return

        synced = any(entry["t"] > 0 for entry in self.lyrics)

        if synced:
            # synced mode — find line by timestamp
            new_index = self.current_index
            for i, entry in enumerate(self.lyrics):
                if entry["t"] <= self.playback_time:
                    new_index = i
        else:
            # unsynced — estimate pace from line count
            # assume average song duration of 210 seconds
            secs_per_line = self._unsynced_secs_per_line
            new_index     = min(
                int(self.playback_time / secs_per_line),
                len(self.lyrics) - 1
            )

        if new_index != self.current_index:
            self.current_index = new_index
            self._frozen_seconds = 0 
            self._update_display(new_index)
        else:
            # same line — count frozen time
            self._frozen_seconds = getattr(self, '_frozen_seconds', 0) + 0.1

            # if frozen for more than 15 seconds — show no audio message
            if self._frozen_seconds > 15:
                self.past_label.setText("")
                self.current_label.setText("No audio detected")
                self.next_label.setText("")
                self._showing_no_audio = True
            
        # if was showing no audio but now moving again — restore
        if getattr(self, '_showing_no_audio', False) and \
                new_index != self.current_index:
            self._showing_no_audio = False
            self._frozen_seconds   = 0
            self._update_display(new_index)
            
    def _update_display(self, index: int):
        """Crossfade animation — smooth but never laggy."""
        total = len(self.lyrics)
        if total == 0:
            return

        past_text    = self.lyrics[index - 1]["line"] if index > 0 else ""
        current_text = self.lyrics[index]["line"]
        next_text    = (self.lyrics[index + 1]["line"]
                        if index < total - 1 else "")

        # cancel existing animation
        if hasattr(self, '_anim_timer') and self._anim_timer \
                and self._anim_timer.isActive():
            self._anim_timer.stop()

        STEPS    = 6   # very few steps — snappy not laggy
        INTERVAL = 20  # 20ms each = 120ms total — barely noticeable
        step     = [0]

        # store target texts
        targets = {
            self.past_label:    (past_text,    90),
            self.current_label: (current_text, 255),
            self.next_label:    (next_text,    90),
        }

        def tick():
            step[0] += 1
            t = step[0] / STEPS

            # fade out old, fade in new simultaneously
            for label, (new_text, target_alpha) in targets.items():
                is_current = (label is self.current_label)
                bold       = "font-weight: bold;" if is_current else ""

                if step[0] <= STEPS // 2:
                    # first half — fade out
                    alpha = int(target_alpha * (1 - t * 2))
                    label.setStyleSheet(
                        f"color: rgba(255,255,255,{max(0,alpha)});"
                        f"background: transparent; {bold}"
                    )
                else:
                    # second half — swap text and fade in
                    if step[0] == STEPS // 2 + 1:
                        label.setText(new_text)
                    progress = (t - 0.5) * 2
                    alpha    = int(target_alpha * progress)
                    label.setStyleSheet(
                        f"color: rgba(255,255,255,{min(target_alpha,alpha)});"
                        f"background: transparent; {bold}"
                    )

            if step[0] >= STEPS:
                self._anim_timer.stop()
                # snap to clean final state
                for label, (new_text, alpha) in targets.items():
                    is_curr = (label is self.current_label)
                    bold    = "font-weight: bold;" if is_curr else ""
                    label.setText(new_text)
                    label.setStyleSheet(
                        f"color: rgba(255,255,255,{alpha});"
                        f"background: transparent; {bold}"
                    )

        self._anim_timer = QTimer()
        self._anim_timer.setInterval(INTERVAL)
        self._anim_timer.timeout.connect(tick)
        self._anim_timer.start()

    def set_loading(self):
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("Identifying song...")
        self.next_label.setText("")
        self.lyrics = []

    def set_no_lyrics(self):
        """Show message when no lyrics found for current song."""
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("No lyrics available")
        self.next_label.setText("Press Ctrl+Shift+K to retry")
        self.caption_badge.hide()
        self.lyrics = []
    
    def set_paused(self):
        """Show message when music is paused."""
        self.timer.stop()
        self.past_label.setText("")
        self.current_label.setText("No audio detected")
        self.next_label.setText("")
        self.caption_badge.hide()
        # deliberately NOT clearing self.lyrics
        # so position is remembered when music resumes# don't clear lyrics — resume will reload them
        
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

    # ─── Alt+drag ────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        alt_held = bool(
            event.modifiers() & Qt.KeyboardModifier.AltModifier
        )
        if event.button() == Qt.MouseButton.LeftButton and alt_held:
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
            pos = self.pos()
            settings.set("overlay_position", [pos.x(), pos.y()])
            self._disable_drag()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self._enable_drag()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            if not self.dragging:
                self._disable_drag()

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)