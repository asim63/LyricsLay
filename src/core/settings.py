import json
import os
import config

# default settings — used on first launch
DEFAULTS = {
    "hotkey":           "<ctrl>+<shift>+l",
    "overlay_position": list(config.OVERLAY_POSITION),
    "overlay_width":    config.OVERLAY_WIDTH,
    "overlay_opacity":  config.OVERLAY_OPACITY,
    "font_size":        config.FONT_SIZE_CURRENT,
    "show_on_startup":  True,
}

SETTINGS_FILE = os.path.join(config.CACHE_DIR, "settings.json")

def load_settings() -> dict:
    """
    Loads user settings from disk.
    Falls back to defaults for any missing keys.
    """
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULTS)
        return DEFAULTS.copy()

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)

    # merge with defaults so new settings added in updates
    # don't crash on older settings files
    merged = DEFAULTS.copy()
    merged.update(saved)
    return merged

def save_settings(settings: dict):
    """
    Saves user settings to disk.
    """
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    print(f"[Settings] Saved.")

def get(key: str):
    """
    Quick helper — get one setting by key.
    e.g. settings.get("hotkey")
    """
    return load_settings().get(key, DEFAULTS.get(key))

def set(key: str, value):
    """
    Quick helper — update one setting and save.
    e.g. settings.set("hotkey", "<ctrl>+<shift>+m")
    """
    current = load_settings()
    current[key] = value
    save_settings(current)
    print(f"[Settings] {key} → {value}")