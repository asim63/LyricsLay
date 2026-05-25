
import json
import os
import config

DEFAULTS = {
    "hotkey":            config.DEFAULT_TOGGLE_HOTKEY,
    "reidentify_hotkey": config.DEFAULT_REIDENTIFY_HOTKEY,
    "overlay_position":  None,
    "overlay_width":     config.OVERLAY_WIDTH,
    "overlay_height":    120,
    "overlay_opacity":   config.OVERLAY_OPACITY,
    "font_size":         config.FONT_SIZE_CURRENT,
    "show_on_startup":   True,
    "romanize_lyrics":   False,
}

SETTINGS_FILE = os.path.join(config.CACHE_DIR, "settings.json")

# module-level in-process cache — avoids redundant disk reads
_cache: dict | None = None


def load_settings() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULTS)
        _cache = DEFAULTS.copy()
        return _cache

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)

    merged = DEFAULTS.copy()
    merged.update(saved)
    _cache = merged
    return _cache


def save_settings(data: dict):
    global _cache
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _cache = data.copy()
    print("[Settings] Saved.")


def get(key: str):
    return load_settings().get(key, DEFAULTS.get(key))


def set(key: str, value):
    current = load_settings()
    current[key] = value
    save_settings(current)
    print(f"[Settings] {key} → {value}")