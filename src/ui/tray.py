import sys
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtGui  import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt
from src.core     import settings


class SystemTray(QSystemTrayIcon):
    """
    System tray icon — lives in the bottom-right taskbar.
    Right-click shows the menu.
    """

    def __init__(self, overlay, app):
        super().__init__()
        self.overlay = overlay
        self.app     = app

        self._setup_icon()
        self._setup_menu()

        # show notification on first launch
        self.showMessage(
            "LyricsLay",
            "Running in background. Press Ctrl+Shift+L to toggle lyrics.",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

    # ─── Icon ────────────────────────────────────────────────────────

    def _setup_icon(self):
        """
        Creates a simple coloured circle as the tray icon.
        We'll replace this with a real icon file later.
        """
        pixmap  = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#89b4fa"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)

        # draw a small music note shape
        painter.setBrush(QColor("#1e1e2e"))
        painter.drawEllipse(6, 18, 8, 8)   # note head
        painter.drawEllipse(18, 14, 8, 8)  # note head 2
        painter.setPen(QColor("#1e1e2e"))
        from PyQt6.QtGui import QPen
        pen = QPen(QColor("#1e1e2e"), 2)
        painter.setPen(pen)
        painter.drawLine(14, 22, 14, 8)    # stem 1
        painter.drawLine(26, 18, 26, 4)    # stem 2
        painter.drawLine(14, 8, 26, 4)     # beam
        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setToolTip("LyricsLay")
        self.setVisible(True)

    # ─── Menu ────────────────────────────────────────────────────────

    def _setup_menu(self):
        """Build the right-click menu."""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 4px;
                font-family: Arial;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #313244;
            }
            QMenu::separator {
                height: 1px;
                background: #45475a;
                margin: 4px 8px;
            }
        """)

        # ── toggle lyrics ─────────────────────────────────────────────
        self.toggle_action = menu.addAction("Hide lyrics")
        self.toggle_action.triggered.connect(self._toggle_overlay)

        menu.addSeparator()

        # ── settings ──────────────────────────────────────────────────
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)

        menu.addSeparator()

        # ── quit ──────────────────────────────────────────────────────
        quit_action = menu.addAction("Quit LyricsLay")
        quit_action.triggered.connect(self._quit)

        self.setContextMenu(menu)

        # single click also toggles
        self.activated.connect(self._on_activated)

    # ─── Actions ─────────────────────────────────────────────────────

    def _toggle_overlay(self):
        """Show or hide the overlay."""
        self.overlay.toggle()
        # update menu text to reflect current state
        if self.overlay.is_visible:
            self.toggle_action.setText("Hide lyrics")
        else:
            self.toggle_action.setText("Show lyrics")

    def _on_activated(self, reason):
        """Single click on tray icon — toggle overlay."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_overlay()

    def _open_settings(self):
        """Open the settings window."""
        from src.ui.settings_window import SettingsWindow
        self.settings_win = SettingsWindow(
            on_hotkey_changed=self._on_hotkey_changed
        )
        self.settings_win.show()

    def _on_hotkey_changed(self, new_hotkey: str):
        """Called when user saves a new hotkey in settings."""
        print(f"[Tray] Hotkey changed to: {new_hotkey}")
        # main.py will handle re-registering the hotkey
        # via the overlay's toggle_requested signal

    def _quit(self):
        """Quit the app cleanly."""
        self.overlay.hide()
        self.hide()
        self.app.quit()

    def update_toggle_text(self):
        """Sync menu text with current overlay visibility."""
        if self.overlay.is_visible:
            self.toggle_action.setText("Hide lyrics")
        else:
            self.toggle_action.setText("Show lyrics")