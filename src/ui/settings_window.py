from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QFont, QKeyEvent
from src.core import settings


# ── single-key-combo capture widget ──────────────────────────────────────────

class HotkeyEdit(QWidget):
    """
    A clean single-combination hotkey capture field.
    Press any key combo — it shows instantly, replaces previous.
    No stacking, no delay.
    """

    def __init__(self, initial: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._value = initial   # stored as Qt string e.g. "Ctrl+Shift+L"
        self._focused = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._label = QLabel(initial or "Click and press a key combo")
        self._label.setFont(QFont("Segoe UI", 12))
        self._label.setStyleSheet("color: #cdd6f4; background: transparent;")
        layout.addWidget(self._label)

        self._update_style(False)

    def value(self) -> str:
        return self._value

    def focusInEvent(self, e):
        self._focused = True
        self._update_style(True)
        self._label.setText("Press a key combo...")
        self._label.setStyleSheet("color: #6c7086; background: transparent;")

    def focusOutEvent(self, e):
        self._focused = False
        self._update_style(False)
        self._label.setText(self._value or "Click and press a key combo")
        self._label.setStyleSheet("color: #cdd6f4; background: transparent;")

    def keyPressEvent(self, e: QKeyEvent):
        # ignore lone modifiers
        if e.key() in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
                       Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        mods = e.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier: parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:   parts.append("Shift")
        if mods & Qt.KeyboardModifier.AltModifier:     parts.append("Alt")
        if mods & Qt.KeyboardModifier.MetaModifier:    parts.append("Meta")

        key_str = QKeySequence(e.key()).toString()
        if key_str:
            parts.append(key_str)

        combo = "+".join(parts)
        if combo:
            self._value = combo
            self._label.setText(combo)
            self._label.setStyleSheet("color: #cdd6f4; background: transparent;")
            self.clearFocus()

    def _update_style(self, focused: bool):
        border = "#7aa2f7" if focused else "#2a2a3a"
        self.setStyleSheet(f"""
            HotkeyEdit {{
                background-color: #111118;
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)


# ── settings window ───────────────────────────────────────────────────────────

class SettingsWindow(QDialog):

    def __init__(self, parent=None, on_hotkey_changed=None):
        super().__init__(parent)
        self.on_hotkey_changed = on_hotkey_changed
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle("LyricsLay — Settings")
        self.setFixedSize(460, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.setStyleSheet("""
            QDialog {
                background-color: #0d0d14;
            }
            QLabel {
                background: transparent;
            }
            QPushButton {
                background-color: #1a1a26;
                color: #cdd6f4;
                border: 1px solid #2a2a3a;
                border-radius: 8px;
                padding: 8px 20px;
                font-family: Segoe UI;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #222232;
                border: 1px solid #3a3a5a;
            }
            QPushButton#save_btn {
                background-color: #3a3a5a;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #5a5a8a;
                font-size: 13px;
            }
            QPushButton#save_btn:hover {
                background-color: #4a4a7a;
                border: 1px solid #7a7aaa;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a26;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        h_layout.addWidget(title)
        layout.addWidget(header)

        # ── content ───────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(18)
        c_layout.setContentsMargins(24, 24, 24, 24)

        # toggle hotkey
        c_layout.addWidget(self._label("Toggle Hotkey"))
        c_layout.addWidget(self._desc("Show / hide the lyrics overlay"))
        current_toggle = self._pynput_to_qt(
            settings.get("hotkey") or "<ctrl>+<shift>+l"
        )
        self.key_edit = HotkeyEdit(current_toggle)
        self.key_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        c_layout.addWidget(self.key_edit)

        c_layout.addWidget(self._divider())

        # reidentify hotkey
        c_layout.addWidget(self._label("Reidentify Hotkey"))
        c_layout.addWidget(self._desc("Force re-detect the current song"))
        current_reid = self._pynput_to_qt(
            settings.get("reidentify_hotkey") or "<ctrl>+<shift>+k"
        )
        self.reid_edit = HotkeyEdit(current_reid)
        self.reid_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        c_layout.addWidget(self.reid_edit)

        c_layout.addWidget(self._divider())

        # romanization row
        rom_row = QHBoxLayout()
        rom_text = QVBoxLayout()
        rom_text.setSpacing(3)
        rom_text.addWidget(self._label("Romanize Lyrics"))
        rom_text.addWidget(self._desc("Convert Japanese / Korean to phonetic Latin"))
        rom_row.addLayout(rom_text)
        rom_row.addStretch()

        self.rom_btn = QPushButton(
            "ON" if settings.get("romanize_lyrics") else "OFF"
        )
        self.rom_btn.setFixedSize(60, 32)
        self.rom_btn.setCheckable(True)
        self.rom_btn.setChecked(bool(settings.get("romanize_lyrics")))
        self._update_rom_style()
        self.rom_btn.clicked.connect(self._on_rom_click)
        rom_row.addWidget(self.rom_btn)
        c_layout.addLayout(rom_row)

        c_layout.addStretch()
        layout.addWidget(content)

        # ── footer ────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background-color: #0d0d14; border-top: 1px solid #1a1a26;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(24, 0, 24, 0)
        f_layout.setSpacing(10)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.setFixedHeight(36)
        reset_btn.clicked.connect(self._reset)
        f_layout.addWidget(reset_btn)

        f_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setObjectName("save_btn")
        save_btn.setFixedSize(100, 36)
        save_btn.clicked.connect(self._save)
        f_layout.addWidget(save_btn)

        layout.addWidget(footer)

    # ── helpers ───────────────────────────────────────────────────────

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        lbl.setStyleSheet("color: #cdd6f4;")
        return lbl

    def _desc(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet("color: #4a4a6a;")
        return lbl

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #1a1a26; border: none;")
        return line

    def _on_rom_click(self):
        self.rom_btn.setText("ON" if self.rom_btn.isChecked() else "OFF")
        self._update_rom_style()

    def _update_rom_style(self):
        if self.rom_btn.isChecked():
            self.rom_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #0d0d14;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
        else:
            self.rom_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a1a26;
                    color: #4a4a6a;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: bold;
                    border: 1px solid #2a2a3a;
                }
                QPushButton:hover { background-color: #222232; }
            """)

    def _save(self):
        toggle_qt = self.key_edit.value()
        reid_qt   = self.reid_edit.value()

        # duplicate hotkey check
        if toggle_qt and reid_qt and toggle_qt == reid_qt:
            msg = QMessageBox(self)
            msg.setWindowTitle("Hotkey Conflict")
            msg.setText(toggle_qt + " is already assigned to another action.\nPlease choose a different combination.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet("background-color: #0d0d14; color: #cdd6f4; font-family: Segoe UI;")
            msg.exec()
            return


        if toggle_qt:
            settings.set("hotkey", self._qt_to_pynput(toggle_qt))
        if reid_qt:
            settings.set("reidentify_hotkey", self._qt_to_pynput(reid_qt))

        settings.set("romanize_lyrics", self.rom_btn.isChecked())

        if self.on_hotkey_changed:
            self.on_hotkey_changed(settings.get("hotkey"))

        self.accept()

    def _reset(self):
        self.key_edit._value = "Ctrl+Shift+L"
        self.key_edit._label.setText("Ctrl+Shift+L")
        self.reid_edit._value = "Ctrl+Shift+K"
        self.reid_edit._label.setText("Ctrl+Shift+K")

    def _pynput_to_qt(self, pynput: str) -> str:
        parts = pynput.split("+")
        result = []
        for p in parts:
            p = p.strip()
            if p == "<ctrl>":    result.append("Ctrl")
            elif p == "<shift>": result.append("Shift")
            elif p == "<alt>":   result.append("Alt")
            elif p == "<cmd>":   result.append("Meta")
            else:                result.append(p.upper())
        return "+".join(result)

    def _qt_to_pynput(self, qt: str) -> str:
        parts = qt.split("+")
        result = []
        for p in parts:
            if p == "Ctrl":    result.append("<ctrl>")
            elif p == "Shift": result.append("<shift>")
            elif p == "Alt":   result.append("<alt>")
            elif p == "Meta":  result.append("<cmd>")
            else:              result.append(p.lower())
        return "+".join(result)