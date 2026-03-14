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
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # title
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        # divider
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #45475a;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # hotkey section
        hotkey_label = QLabel("Toggle hotkey")
        hotkey_label.setFont(QFont("Arial", 12))
        hotkey_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(hotkey_label)

        hotkey_desc = QLabel("Press any key combination below to set your hotkey")
        hotkey_desc.setFont(QFont("Arial", 10))
        hotkey_desc.setStyleSheet("color: #6c7086;")
        layout.addWidget(hotkey_desc)

        # key sequence editor — user presses keys and it records them
        self.key_edit = QKeySequenceEdit()
        current_hotkey = self.current_settings.get("hotkey", "<ctrl>+<shift>+l")
        # convert pynput format to Qt format for display
        qt_hotkey = self._pynput_to_qt(current_hotkey)
        self.key_edit.setKeySequence(QKeySequence(qt_hotkey))
        layout.addWidget(self.key_edit)

        # hint
        hint = QLabel("Example: Ctrl+Shift+L  or  Ctrl+Alt+Space")
        hint.setFont(QFont("Arial", 10))
        hint.setStyleSheet("color: #6c7086;")
        layout.addWidget(hint)

        layout.addStretch()

       # buttons row
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
        reset_btn.clicked.connect(self._reset_hotkey)
        btn_row.addWidget(reset_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("save_btn")
        save_btn.setMinimumHeight(36)
        save_btn.setMinimumWidth(100)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

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
