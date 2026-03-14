import json
import os
import config

def load_cache() -> dict:
    """
    Loads the cache file from disk.
    Returns an empty dict if the file doesn't exist yet.
    """
    if not os.path.exists(config.CACHE_FILE):
        return {}

    with open(config.CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache: dict):
    """
    Saves the full cache dict back to disk.
    """
    with open(config.CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_cached_song(shazam_id: str) -> dict | None:
    """
    Looks up a song in the cache by its Shazam ID.
    Returns the song data or None if not found.
    """
    cache = load_cache()
    return cache.get(shazam_id, None)

def cache_song(shazam_id: str, title: str, artist: str, lyrics: list):
    """
    Saves a song and its lyrics to the cache.
    lyrics is a list of dicts: [{"t": 14.2, "line": "Good things dont last"}, ...]
    """
    cache = load_cache()

    cache[shazam_id] = {
        "title":  title,
        "artist": artist,
        "lyrics": lyrics,
    }

    save_cache(cache)
    print(f"[Cache] Saved: {title} by {artist}")

def is_cached(shazam_id: str) -> bool:
    """
    Quick check — is this song already in the cache?
    """
    cache = load_cache()
    return shazam_id in cache
