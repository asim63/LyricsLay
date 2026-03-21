from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QKeySequenceEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QFont
from src.core import settings

class SettingsWindow(QDialog):
    """
    Small popup window where the user can customise their hotkey.
    Opens from the system tray menu.
    """

    def __init__(self, parent=None, on_hotkey_changed=None):
        super().__init__(parent)
        self.on_hotkey_changed = on_hotkey_changed
        self.current_settings  = settings.load_settings()

        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        """Configure the window itself."""
        self.setWindowTitle("LyricsLay — Settings")
        self.setFixedSize(420, 300)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        # clean stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-family: Arial;
            }
            QPushButton {
                background-color: #45475a;
                color: #ffffff;
                border: 1px solid #585b70;
                border-radius: 6px;
                padding: 8px 20px;
                font-family: Arial;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QPushButton#save_btn {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                border: none;
            }
            QPushButton#save_btn:hover {
                background-color: #74c7ec;
            }
            QKeySequenceEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px;
                font-family: Arial;
                font-size: 13px;
            }
            QFrame#divider {
                color: #45475a;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #45475a;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # ── toggle hotkey ─────────────────────────────────────────────
        toggle_label = QLabel("Toggle hotkey")
        toggle_label.setFont(QFont("Arial", 12))
        toggle_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(toggle_label)

        toggle_desc = QLabel("Show / hide the lyrics overlay")
        toggle_desc.setFont(QFont("Arial", 10))
        toggle_desc.setStyleSheet("color: #6c7086;")
        layout.addWidget(toggle_desc)

        self.key_edit = QKeySequenceEdit()
        current_hotkey = self.current_settings.get(
            "hotkey", "<ctrl>+<shift>+l"
        )
        self.key_edit.setKeySequence(
            QKeySequence(self._pynput_to_qt(current_hotkey))
        )
        layout.addWidget(self.key_edit)

        # ── reidentify hotkey ─────────────────────────────────────────
        reid_label = QLabel("Reidentify hotkey")
        reid_label.setFont(QFont("Arial", 12))
        reid_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(reid_label)

        reid_desc = QLabel("Force re-detect current song")
        reid_desc.setFont(QFont("Arial", 10))
        reid_desc.setStyleSheet("color: #6c7086;")
        layout.addWidget(reid_desc)

        self.reid_edit = QKeySequenceEdit()
        current_reid = self.current_settings.get(
            "reidentify_hotkey", "<ctrl>+<shift>+k"
        )
        self.reid_edit.setKeySequence(
            QKeySequence(self._pynput_to_qt(current_reid))
        )
        layout.addWidget(self.reid_edit)

        layout.addStretch()

        # buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        reset_btn = QPushButton("Reset to default")
        reset_btn.setMinimumHeight(36)
        reset_btn.setMinimumWidth(130)
        reset_btn.clicked.connect(self._reset_hotkeys)
        btn_row.addWidget(reset_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("save_btn")
        save_btn.setMinimumHeight(36)
        save_btn.setMinimumWidth(100)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _save(self):
        """Save both hotkeys."""
        qt_toggle = self.key_edit.keySequence().toString()
        qt_reid   = self.reid_edit.keySequence().toString()

        if qt_toggle:
            pynput_toggle = self._qt_to_pynput(qt_toggle)
            settings.set("hotkey", pynput_toggle)

        if qt_reid:
            pynput_reid = self._qt_to_pynput(qt_reid)
            settings.set("reidentify_hotkey", pynput_reid)

        if self.on_hotkey_changed:
            self.on_hotkey_changed(
                settings.get("hotkey"),
                settings.get("reidentify_hotkey")
            )
        self.accept()

    def _reset_hotkeys(self):
        """Reset both hotkeys to defaults."""
        self.key_edit.setKeySequence(QKeySequence("Ctrl+Shift+L"))
        self.reid_edit.setKeySequence(QKeySequence("Ctrl+Shift+K"))

    def _save(self):
        """Save the new hotkey and notify the app."""
        qt_sequence = self.key_edit.keySequence().toString()
        if not qt_sequence:
            return

        # convert Qt format back to pynput format
        pynput_hotkey = self._qt_to_pynput(qt_sequence)
        settings.set("hotkey", pynput_hotkey)

        # notify the app to re-register the hotkey
        if self.on_hotkey_changed:
            self.on_hotkey_changed(pynput_hotkey)

        self.accept()

    def _reset_hotkey(self):
        """Reset hotkey to default Ctrl+Shift+L."""
        self.key_edit.setKeySequence(QKeySequence("Ctrl+Shift+L"))

    def _pynput_to_qt(self, pynput: str) -> str:
        """
        Converts pynput format to Qt format for display.
        e.g. "<ctrl>+<shift>+l" → "Ctrl+Shift+L"
        """
        return (pynput
            .replace("<ctrl>",  "Ctrl")
            .replace("<shift>", "Shift")
            .replace("<alt>",   "Alt")
            .replace("<cmd>",   "Meta")
            .upper()
            .replace("CTRL",  "Ctrl")
            .replace("SHIFT", "Shift")
            .replace("ALT",   "Alt")
            .replace("META",  "Meta")
        )

    def _qt_to_pynput(self, qt: str) -> str:
        """
        Converts Qt format back to pynput format for saving.
        e.g. "Ctrl+Shift+L" → "<ctrl>+<shift>+l"
        """
        result = qt
        result = result.replace("Ctrl",  "<ctrl>")
        result = result.replace("Shift", "<shift>")
        result = result.replace("Alt",   "<alt>")
        result = result.replace("Meta",  "<cmd>")
        # lowercase the actual key letter
        parts = result.split("+")
        parts[-1] = parts[-1].lower()
        return "+".join(parts)
