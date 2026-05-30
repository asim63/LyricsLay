import sys
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import Qt
from src.core import settings


class SystemTray(QSystemTrayIcon):

    def __init__(self, overlay, app, reregister_hotkeys_fn=None):
        super().__init__()
        self.overlay               = overlay
        self.app                   = app
        self.reregister_hotkeys_fn = reregister_hotkeys_fn  # callback to main.py

        self._setup_icon()
        self._setup_menu()

        self.showMessage(
            "LyricsLay",
            "Running in background. Press Ctrl+Shift+L to toggle lyrics.",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

    # ─── icon ─────────────────────────────────────────────────────────────────

    def _setup_icon(self):
        icon_path = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "assets", "icon.ico")
        )
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#89b4fa"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(2, 2, 28, 28)
            painter.end()
            self.setIcon(QIcon(pixmap))

        self.setToolTip("LyricsLay")
        self.setVisible(True)

    # ─── menu ─────────────────────────────────────────────────────────────────

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

        self.toggle_action = menu.addAction("Hide lyrics")
        self.toggle_action.triggered.connect(self._toggle_overlay)

        menu.addSeparator()

        self.rom_action = menu.addAction("Romanization: OFF")
        self.rom_action.triggered.connect(self._toggle_romanization)
        self._update_rom_label()

        menu.addSeparator()

        menu.addAction("Settings").triggered.connect(self._open_settings)
        menu.addAction("Reset position").triggered.connect(self._reset_position)

        menu.addSeparator()
        menu.addAction("Restart LyricsLay").triggered.connect(self._restart)
        menu.addAction("Quit LyricsLay").triggered.connect(self._quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    # ─── actions ──────────────────────────────────────────────────────────────

    def _toggle_overlay(self):
        self.overlay.toggle()
        self.update_toggle_text()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_overlay()

    def update_toggle_text(self):
        self.toggle_action.setText(
            "Hide lyrics" if self.overlay.is_visible else "Show lyrics"
        )

    def _open_settings(self):
        from src.ui.settings_window import SettingsWindow
        self.settings_win = SettingsWindow(
            on_hotkey_changed=self._on_hotkey_changed
        )
        self.settings_win.show()

    def _on_hotkey_changed(self, new_hotkey: str):
        """
        Called when user saves settings.
        Re-registers hotkeys immediately so changes take effect without restart.
        """
        print(f"[Tray] Hotkey changed to: {new_hotkey}")
        # sync romanization label in case it was toggled in settings
        self._update_rom_label()
        # re-register hotkeys in main.py
        if self.reregister_hotkeys_fn:
            self.reregister_hotkeys_fn()
        else:
            print("[Tray] Warning: no reregister_hotkeys_fn set — restart to apply hotkey changes")

    def _toggle_romanization(self):
        current = settings.get("romanize_lyrics")
        settings.set("romanize_lyrics", not current)
        self._update_rom_label()
        state = "ON" if not current else "OFF"
        print(f"[Tray] Romanization: {state}")
        self.showMessage(
            "LyricsLay",
            f"Romanization {state} — reidentify song to update lyrics.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _update_rom_label(self):
        state = settings.get("romanize_lyrics")
        self.rom_action.setText(
            f"Romanization: {'ON ✓' if state else 'OFF'}"
        )

    def _reset_position(self):
        settings.set("overlay_position", None)
        screen   = QApplication.primaryScreen()
        screen_w = screen.geometry().width()
        self.overlay.move((screen_w - self.overlay.width()) // 2, 40)
        for h in ("close_handle", "grip_handle", "resize_handle", "sync_handle"):
            if hasattr(self.overlay, h):
                getattr(self.overlay, h).reposition()
        print("[Tray] Position reset.")
        
    def _restart(self):
        """Restart the entire application."""
        import os
        print("[Tray] Restarting LyricsLay...")
        self.overlay.hide()
        self.hide()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _quit(self):
        self.overlay.hide()
        self.hide()
        self.app.quit()