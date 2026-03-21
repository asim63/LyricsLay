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

        # toggle lyrics
        self.toggle_action = menu.addAction("Hide lyrics")
        self.toggle_action.triggered.connect(self._toggle_overlay)

        menu.addSeparator()

        # romanization toggle
        self.rom_action = menu.addAction("Romanization: OFF")
        self.rom_action.triggered.connect(self._toggle_romanization)

        menu.addSeparator()

        # settings
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)

        # reset position
        reset_action = menu.addAction("Reset position")
        reset_action.triggered.connect(self._reset_position)

        menu.addSeparator()

        # quit — always last
        quit_action = menu.addAction("Quit LyricsLay")
        quit_action.triggered.connect(self._quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        # sync romanization label on open
        self._update_rom_label()
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
            
    def _reset_position(self):
        """Reset overlay to top center of screen."""
        from src.core import settings
        settings.set("overlay_position", None)
        # reposition immediately
        from PyQt6.QtWidgets import QApplication
        screen   = QApplication.primaryScreen()
        screen_w = screen.geometry().width()
        w        = self.overlay.width()
        self.overlay.move((screen_w - w) // 2, 40)
        self.overlay.grip_handle.reposition()
        self.overlay.resize_handle.reposition()
        print("[Tray] Position reset to top center.")
        
    def _close_overlay(self):
        """Always hides the overlay regardless of current state."""
        if self.overlay.is_visible:
            self.overlay.hide()
            self.overlay.is_visible = False
            self.toggle_action.setText("Show lyrics")

    def _restart(self):
        """Restart the entire application."""
        import sys
        import os
        print("[Tray] Restarting LyricsLay...")
        self.overlay.hide()
        self.hide()
        # restart by re-executing the current process
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _reset_position(self):
        """Reset overlay to top center of screen."""
        from src.core import settings
        from PyQt6.QtWidgets import QApplication
        settings.set("overlay_position", None)
        screen   = QApplication.primaryScreen()
        screen_w = screen.geometry().width()
        w        = self.overlay.width()
        self.overlay.move((screen_w - w) // 2, 40)
        self.overlay.grip_handle.reposition()
        self.overlay.resize_handle.reposition()
        print("[Tray] Position reset.")
        
    def _toggle_romanization(self):
        """Toggle romanization on/off."""
        from src.core import settings
        current = settings.get("romanize_lyrics")
        settings.set("romanize_lyrics", not current)
        self._update_rom_label()
        state = "ON" if not current else "OFF"
        print(f"[Tray] Romanization: {state}")
        self.showMessage(
            "LyricsLay",
            f"Romanization {state} — takes effect on next song",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _update_rom_label(self):
        """Sync romanization menu label."""
        from src.core import settings
        state = settings.get("romanize_lyrics")
        self.rom_action.setText(
            f"Romanization: {'ON ✓' if state else 'OFF'}"
        )
    def _reset_position(self):
        """Reset overlay to top center."""
        from src.core import settings
        from PyQt6.QtWidgets import QApplication
        settings.set("overlay_position", None)
        screen   = QApplication.primaryScreen()
        screen_w = screen.geometry().width()
        w        = self.overlay.width()
        self.overlay.move((screen_w - w) // 2, 40)
        for h in ['close_handle', 'grip_handle', 'resize_handle',
                  'restart_button', 'reidentify_button']:
            if hasattr(self.overlay, h):
                getattr(self.overlay, h).reposition()
        print("[Tray] Position reset.")