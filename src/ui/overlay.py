"""
overlay.py  —  LyricsLay floating lyrics window
================================================

Animation: YouTube Music style — lyrics slide upward continuously.
No fade-to-blank. Text is always visible.

How it works:
  - Three QLabels (past, current, next) sit inside a clipping container
  - On line change, all three labels animate their Y position upward
    by one "slot" height using QPropertyAnimation
  - When animation finishes, labels snap back to original positions
    with new text — seamless, no blank moment
  - Fast lyrics (< 1.5s between lines) skip animation entirely

Buttons:
  - Removed: RestartButton, ReidentifyButton (use hotkeys instead)
  - Kept: CloseButton (×), GripHandle (⠿), ResizeHandle (⌟)
  - Added: SyncButton (⟳) inside the pill, top-left corner
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QFrame, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QSize,
    pyqtSignal, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QRect,
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath
from src.core import settings
import config


# ── animation constants ───────────────────────────────────────────────────────
SLIDE_DURATION_MS = 250   # how long the slide takes
EASING            = QEasingCurve.Type.OutCubic


# ══════════════════════════════════════════════════════════════════════════════
#  Side handle widgets  (close, grip, resize)
#  Identical behaviour to original — just cleaned up styling
# ══════════════════════════════════════════════════════════════════════════════

class _Handle(QWidget):
    """Base for all floating side handles."""
    ICON = ""
    TIP  = ""
    W    = 22
    H    = 22

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self.TIP)

        self._lbl = QLabel(self.ICON, self)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setGeometry(0, 0, self.W, self.H)
        self._lbl.setFont(QFont("Segoe UI", 11))
        self._set_style(False)

    def _set_style(self, hovered: bool):
        if hovered:
            self._lbl.setStyleSheet(
                "color: rgba(255,255,255,230);"
                "background: rgba(255,255,255,20);"
                "border: 1px solid rgba(255,255,255,30);"
                "border-radius: 6px;"
            )
        else:
            self._lbl.setStyleSheet(
                "color: rgba(255,255,255,110);"
                "background: rgba(255,255,255,8);"
                "border: 1px solid rgba(255,255,255,14);"
                "border-radius: 6px;"
            )

    def enterEvent(self, e):   self._set_style(True)
    def leaveEvent(self, e):   self._set_style(False)
    def reposition(self):      pass


class CloseButton(_Handle):
    ICON = "×"
    TIP  = "Hide overlay"

    def reposition(self):
        p = self.overlay.pos()
        self.move(p.x() + self.overlay.width() + 5, p.y())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.overlay.toggle()


class SyncButton(_Handle):
    """
    Floating sync button — separate QWidget window so it receives mouse
    events even though the main overlay is WS_EX_TRANSPARENT click-through.
    Sits at top-left of the pill, just outside it.
    """
    ICON = "⟳"
    TIP  = "Force sync / reidentify (Ctrl+Shift+K)"

    def reposition(self):
        p = self.overlay.pos()
        self.move(p.x() - self.W - 5, p.y())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._set_style(True)
            QTimer.singleShot(200, lambda: self._set_style(False))
            if self.overlay.reidentify_button.on_click:
                self.overlay.reidentify_button.on_click()


class GripHandle(_Handle):
    ICON = "⠿"
    TIP  = "Drag to move · Double-click to hide"
    H    = 60

    def __init__(self, overlay):
        super().__init__(overlay)
        self.dragging      = False
        self.drag_position = QPoint()
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._lbl.setGeometry(0, 0, self.W, self.H)
        self._lbl.setFont(QFont("Segoe UI", 14))

    def reposition(self):
        p = self.overlay.pos()
        self.move(
            p.x() + self.overlay.width() + 5,
            p.y() + (self.overlay.height() - self.H) // 2,
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging      = True
            self.drag_position = (
                e.globalPosition().toPoint() -
                self.overlay.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.overlay.move(e.globalPosition().toPoint() - self.drag_position)
            self.reposition()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            p = self.overlay.pos()
            settings.set("overlay_position", [p.x(), p.y()])

    def mouseDoubleClickEvent(self, e):
        self.overlay.toggle_requested.emit()


class ResizeHandle(_Handle):
    ICON = "⌟"
    TIP  = "Drag to resize"

    def __init__(self, overlay):
        super().__init__(overlay)
        self.resizing          = False
        self.resize_start_pos  = QPoint()
        self.resize_start_size = QSize()
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)

    def reposition(self):
        p = self.overlay.pos()
        self.move(
            p.x() + self.overlay.width() + 5,
            p.y() + self.overlay.height() - self.H,
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.resizing          = True
            self.resize_start_pos  = e.globalPosition().toPoint()
            self.resize_start_size = self.overlay.size()

    def mouseMoveEvent(self, e):
        if self.resizing:
            d     = e.globalPosition().toPoint() - self.resize_start_pos
            new_w = max(300, self.resize_start_size.width()  + d.x())
            new_h = max(90,  self.resize_start_size.height() + d.y())
            self.overlay.resize(new_w, new_h)
            self.overlay.grip_handle.reposition()
            self.reposition()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            settings.set("overlay_width",  self.overlay.width())
            settings.set("overlay_height", self.overlay.height())


# ══════════════════════════════════════════════════════════════════════════════
#  Clipping container — masks the sliding labels
# ══════════════════════════════════════════════════════════════════════════════

class LyricsContainer(QWidget):
    """
    A fixed-height widget that clips its children.
    The three label slots slide up inside this container —
    anything outside its bounds is invisible, creating the
    scroll illusion without any fade-to-blank.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        # enforce clipping via painter path
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        super().paintEvent(event)


# ══════════════════════════════════════════════════════════════════════════════
#  LyricsOverlay
# ══════════════════════════════════════════════════════════════════════════════

class LyricsOverlay(QWidget):
    """
    Floating lyrics overlay.

    Layout inside the pill:
        ┌──────────────────────────────────┐
        │ [⟳]                              │  ← sync button, top-left
        │ ┌────────────────────────────┐   │
        │ │   past line  (dim)         │   │  ← clipped container
        │ │   CURRENT LINE (bright)    │   │
        │ │   next line  (dim)         │   │
        │ └────────────────────────────┘   │
        └──────────────────────────────────┘

    On line change:
      1. All three labels slide up by slot_height px (QPropertyAnimation)
      2. On finish: labels snap back, text updated, no visible jump
      Result: seamless upward scroll, text always visible
    """

    toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.s                       = settings.load_settings()
        self.lyrics                  = []
        self.current_index           = 0
        self.dragging                = False
        self.drag_position           = QPoint()
        self.is_visible              = True
        self._frozen_seconds         = 0.0
        self._unsynced_secs_per_line = 6.0
        self._anim_group             = None
        self._animating              = False

        # reidentify callback — set by main.py after init
        self.reidentify_button = _DummyButton()  # placeholder, main.py sets on_click

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._position_window()

        self.close_handle  = CloseButton(self)
        self.grip_handle   = GripHandle(self)
        self.resize_handle = ResizeHandle(self)
        self.sync_handle   = SyncButton(self)

    # ─── window setup ─────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        w = self.s.get("overlay_width",  700)
        h = self.s.get("overlay_height", 130)
        self.resize(w, h)
        QTimer.singleShot(100, self._apply_clickthrough)

    def _apply_clickthrough(self):
        try:
            import ctypes
            hwnd = int(self.winId())
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
            hwnd = int(self.winId())
            GWL_EXSTYLE       = -20
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
        except Exception:
            pass

    def _disable_drag(self):
        try:
            import ctypes
            hwnd = int(self.winId())
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

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── pill background ───────────────────────────────────────────────────
        self.pill = QFrame()
        self.pill.setObjectName("pill")
        self.pill.setStyleSheet("""
            QFrame#pill {
                background-color: rgba(8, 8, 14, 0.75);
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.07);
            }
        """)

        pill_layout = QVBoxLayout(self.pill)
        pill_layout.setSpacing(0)
        pill_layout.setContentsMargins(20, 10, 20, 14)

        # caption badge
        self.caption_badge = QLabel("")
        self.caption_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.caption_badge.setFont(QFont("Segoe UI", 8))
        self.caption_badge.setStyleSheet(
            "color: rgba(255,255,255,50); background: transparent; border: none;"
        )
        self.caption_badge.hide()
        pill_layout.addWidget(self.caption_badge)

        # ── lyrics clipping container ─────────────────────────────────────────
        # Heights: past=small, current=big, next=small
        # slot_height = total container height / 3 (equal slots)
        # Labels are positioned absolutely inside the container and slide up

        self._container = LyricsContainer(self.pill)
        self._container.setStyleSheet("background: transparent;")

        # We'll use a fixed slot height; labels are placed at y=0, slot, slot*2
        self._slot_h = 36   # px per slot — recalculated on resize

        # three labels — positioned absolutely inside _container
        font_past    = QFont("Segoe UI", config.FONT_SIZE_PAST)
        font_current = QFont("Segoe UI", config.FONT_SIZE_CURRENT)
        font_current.setWeight(QFont.Weight.DemiBold)
        font_next    = QFont("Segoe UI", config.FONT_SIZE_NEXT)

        self.past_label = QLabel("")
        self.past_label.setParent(self._container)
        self.past_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.past_label.setWordWrap(True)
        self.past_label.setFont(font_past)
        self.past_label.setStyleSheet("color: rgba(255,255,255,55); background: transparent;")

        self.current_label = QLabel("")
        self.current_label.setParent(self._container)
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_label.setWordWrap(True)
        self.current_label.setFont(font_current)
        self.current_label.setStyleSheet("color: rgba(255,255,255,255); background: transparent;")

        self.next_label = QLabel("")
        self.next_label.setParent(self._container)
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_label.setWordWrap(True)
        self.next_label.setFont(font_next)
        self.next_label.setStyleSheet("color: rgba(255,255,255,55); background: transparent;")

        pill_layout.addWidget(self._container, stretch=1)

        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wrap_layout = QHBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(self.pill, stretch=1)
        outer.addWidget(wrap)

    def _reflow_labels(self):
        """
        Position the three labels inside _container.
        Called on resize and after every animation reset.
        slot_h = container_height / 3
        past    at y=0
        current at y=slot_h
        next    at y=slot_h*2
        """
        w        = self._container.width()
        h        = self._container.height()
        slot_h   = h // 3
        self._slot_h = max(slot_h, 20)

        self.past_label.setGeometry(0, 0,           w, self._slot_h)
        self.current_label.setGeometry(0, self._slot_h,     w, self._slot_h)
        self.next_label.setGeometry(0, self._slot_h * 2, w, self._slot_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_labels()
        for h in self._handles():
            h.reposition()

    def _handles(self):
        return [getattr(self, h) for h in
                ("close_handle", "grip_handle", "resize_handle", "sync_handle")
                if hasattr(self, h)]

    def _setup_timer(self):
        self.playback_time = 0.0
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)

    def _position_window(self):
        screen   = QApplication.primaryScreen()
        sg       = screen.geometry()
        default_x = (sg.width() - self.width()) // 2
        default_y = 40

        saved = self.s.get("overlay_position", None)
        if saved and isinstance(saved, list) and len(saved) == 2:
            x, y = saved
            if 0 <= x <= sg.width() - 100 and 0 <= y <= sg.height() - 50:
                self.move(x, y)
                return
        self.move(default_x, default_y)


    # ─── show / hide ──────────────────────────────────────────────────────────

    def show(self):
        super().show()
        QTimer.singleShot(0, self._reflow_labels)
        for h in self._handles():
            h.reposition()
            h.show()

    def hide(self):
        super().hide()
        for h in self._handles():
            h.hide()

    def toggle(self):
        if self.is_visible:
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True

    def moveEvent(self, event):
        super().moveEvent(event)
        for h in self._handles():
            h.reposition()

    # ─── lyrics loading ───────────────────────────────────────────────────────

    def load_lyrics(self, lyrics: list,
                    caption_mode: bool = False,
                    start_ms: float = 0.0):

        self.timer.stop()
        self.lyrics        = lyrics
        self.current_index = 0

        if not lyrics:
            self.caption_badge.hide()
            return

        synced = any(e["t"] > 0 for e in lyrics)

        if synced:
            self.playback_time = start_ms / 1000.0
            self.caption_badge.hide()
        else:
            self.playback_time = 0.0
            self.caption_badge.setText("unsynced · timing may be off")
            self.caption_badge.show()
            estimated = max(start_ms / 1000.0 * 2, 210.0)
            self._unsynced_secs_per_line = estimated / max(len(lyrics), 1)

        start_index = 0
        if synced:
            for i, e in enumerate(lyrics):
                if e["t"] <= self.playback_time:
                    start_index = i
            if start_index >= len(lyrics) - 3:
                start_index        = 0
                self.playback_time = 0.0

        self.current_index = start_index
        self._set_display_instant(start_index)
        self.timer.start()
        print(f"[Overlay] Loaded {len(lyrics)} lines "
              f"({'synced' if synced else 'unsynced'}) "
              f"at line {start_index}.")

    def _set_display_instant(self, index: int):
        """Place labels at their resting positions with no animation."""
        if self._anim_group and self._anim_group.state() != QParallelAnimationGroup.State.Stopped:
            self._anim_group.stop()
        self._animating = False

        total = len(self.lyrics)
        if total == 0:
            self.past_label.setText("")
            self.current_label.setText("")
            self.next_label.setText("")
            return

        self.past_label.setText(self.lyrics[index - 1]["line"] if index > 0 else "")
        self.current_label.setText(self.lyrics[index]["line"])
        self.next_label.setText(self.lyrics[index + 1]["line"] if index < total - 1 else "")
        self._reflow_labels()

    # ─── tick ─────────────────────────────────────────────────────────────────

    def _tick(self):
        self.playback_time += 0.1
        if not self.lyrics:
            return

        synced = any(e["t"] > 0 for e in self.lyrics)

        if synced:
            new_index = self.current_index
            for i in range(self.current_index, len(self.lyrics)):
                if self.lyrics[i]["t"] <= self.playback_time:
                    new_index = i
                else:
                    break
        else:
            new_index = min(
                int(self.playback_time / self._unsynced_secs_per_line),
                len(self.lyrics) - 1
            )

        if new_index != self.current_index:
            self.current_index   = new_index
            self._frozen_seconds = 0.0
            self._animate_to(new_index)
        else:
            self._frozen_seconds += 0.1

    # ─── YouTube Music style slide animation ──────────────────────────────────

    def _animate_to(self, index: int):
        """
        Slide all three labels upward by slot_h pixels.
        When done: snap back to resting positions with new text.
        Text is always visible — no blank moment.
        """
        total = len(self.lyrics)
        if total == 0:
            return

        # fast lyrics — skip animation to avoid lag
        if index < total - 1:
            gap = self.lyrics[index + 1]["t"] - self.lyrics[index]["t"]
            if gap < 1.5:
                self._set_display_instant(index)
                return

        # if already animating, just snap and restart — prevents queue buildup
        if self._animating:
            self._set_display_instant(index)
            return

        self._animating = True

        slot_h    = self._slot_h
        w         = self._container.width()

        # new text that will appear after slide
        past_new    = self.lyrics[index - 1]["line"] if index > 0 else ""
        current_new = self.lyrics[index]["line"]
        next_new    = self.lyrics[index + 1]["line"] if index < total - 1 else ""

        # current resting Y positions
        past_y    = 0
        current_y = slot_h
        next_y    = slot_h * 2

        # target Y positions (one slot up)
        past_target    = -slot_h
        current_target = 0
        next_target    = slot_h

        group = QParallelAnimationGroup()

        for label, start_y, end_y in (
            (self.past_label,    past_y,    past_target),
            (self.current_label, current_y, current_target),
            (self.next_label,    next_y,    next_target),
        ):
            anim = QPropertyAnimation(label, b"geometry")
            anim.setDuration(SLIDE_DURATION_MS)
            anim.setStartValue(QRect(0, start_y, w, slot_h))
            anim.setEndValue(QRect(0, end_y,   w, slot_h))
            anim.setEasingCurve(EASING)
            group.addAnimation(anim)

        def _on_done():
            self._animating = False
            # swap text and snap back to resting positions
            self.past_label.setText(past_new)
            self.current_label.setText(current_new)
            self.next_label.setText(next_new)
            self._reflow_labels()

        group.finished.connect(_on_done)
        self._anim_group = group
        group.start()

    # ─── status messages ──────────────────────────────────────────────────────

    def set_loading(self):
        self.timer.stop()
        self.lyrics = []
        self._show_status("", "Identifying song…", "")
        self.caption_badge.hide()

    def set_no_lyrics(self):
        self.timer.stop()
        self.lyrics = []
        self._show_status("", "No lyrics available", "Press Ctrl+Shift+K to retry")
        self.caption_badge.hide()

    def set_paused(self):
        self.timer.stop()
        self._show_status("", "No audio detected", "")
        self.caption_badge.hide()

    def clear(self):
        self.timer.stop()
        self.lyrics = []
        self._show_status("", "", "")
        self.caption_badge.hide()

    def _show_status(self, past: str, current: str, nxt: str):
        if self._anim_group and self._anim_group.state() != QParallelAnimationGroup.State.Stopped:
            self._anim_group.stop()
        self._animating = False
        self.past_label.setText(past)
        self.current_label.setText(current)
        self.next_label.setText(nxt)
        self._reflow_labels()

    def add_caption_line(self, line: str):
        past = self.current_label.text()
        self.past_label.setText(past)
        self.current_label.setText(line)
        self.next_label.setText("")

    # ─── Alt+drag ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton and
                event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.dragging      = True
            self.drag_position = (
                event.globalPosition().toPoint() -
                self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            p = self.pos()
            settings.set("overlay_position", [p.x(), p.y()])
            self._disable_drag()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self._enable_drag()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not self.dragging:
            self._disable_drag()

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)


# ── dummy placeholder so main.py's on_click assignment doesn't crash ──────────

class _DummyButton:
    """
    Placeholder for reidentify_button.
    main.py does:  self.overlay.reidentify_button.on_click = self._on_force_reidentify
    We keep that attribute here so nothing breaks.
    """
    on_click = None