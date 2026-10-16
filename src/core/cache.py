import json
import os
import time
import threading
import config

# ── Module-level in-memory cache — single source of truth ───────────────────
_memory_cache: dict | None = None
_lock = threading.Lock()

MAX_CACHE_SONGS = 500  # LRU eviction limit


def _load_disk() -> dict:
    """Reads cache from disk. Called once at startup."""
    if not os.path.exists(config.CACHE_FILE):
        return {}
    try:
        with open(config.CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Cache] Failed to load cache file: {e}")
        return {}


def _flush_to_disk(cache: dict):
    """Writes cache to disk atomically (write tmp → rename)."""
    tmp_path = config.CACHE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        # atomic rename — no corruption on crash
        os.replace(tmp_path, config.CACHE_FILE)
    except Exception as e:
        print(f"[Cache] Failed to flush cache: {e}")
        # clean up partial tmp file
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _ensure_loaded():
    """Loads cache from disk into memory if not already loaded."""
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = _load_disk()


def _evict_if_needed(cache: dict):
    """
    True LRU eviction: if cache exceeds MAX_CACHE_SONGS, remove
    entries with the oldest last_played timestamp.
    """
    if len(cache) <= MAX_CACHE_SONGS:
        return
    # remove oldest 20% to avoid constant eviction
    to_remove = max(1, len(cache) // 5)
    # sort by last_played ascending — oldest first
    sorted_keys = sorted(
        cache.keys(),
        key=lambda k: cache[k].get("last_played", 0)
    )
    for key in sorted_keys[:to_remove]:
        del cache[key]
        print(f"[Cache] Evicted old entry: {key}")


# ── Public API ──────────────────────────────────────────────────────────────

def is_cached(shazam_id: str) -> bool:
    """O(1) in-memory check — no disk read."""
    with _lock:
        _ensure_loaded()
        return shazam_id in _memory_cache


def get_cached_song(shazam_id: str) -> dict | None:
    """Looks up a song in the in-memory cache. Updates last_played timestamp."""
    with _lock:
        _ensure_loaded()
        entry = _memory_cache.get(shazam_id, None)
        if entry is not None:
            entry["last_played"] = time.time()
        return entry


def cache_song(shazam_id: str, title: str, artist: str, lyrics: list):
    """
    Saves a song to in-memory cache and flushes to disk.
    Only caches if lyrics are properly synced.
    """
    # check if lyrics are synced
    synced = any(entry["t"] > 0 for entry in lyrics)

    if not synced:
        print(f"[Cache] Skipping unsynced lyrics for: {title}")
        return

    with _lock:
        _ensure_loaded()
        _memory_cache[shazam_id] = {
            "title":  title,
            "artist": artist,
            "lyrics": lyrics,
            "synced": True,
            "last_played": time.time(),
        }
        _evict_if_needed(_memory_cache)
        _flush_to_disk(_memory_cache.copy())

    print(f"[Cache] Saved: {title} by {artist} "
          f"({len(lyrics)} synced lines)")


def flush():
    """Flush in-memory cache to disk. Call on app exit."""
    with _lock:
        if _memory_cache is not None:
            _flush_to_disk(_memory_cache.copy())


def clear_cache():
    """Clears all cached data."""
    with _lock:
        _memory_cache.clear()
        _flush_to_disk(_memory_cache.copy())
        print("[Cache] Cache cleared.")
