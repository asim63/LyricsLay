import requests
import asyncio
import config

# ─── Main entry point ─────────────────────────────────────────────────────────

def fetch_lyrics(title: str, artist: str) -> list | None:
    """
    Tries to fetch synced lyrics from three sources in order.
    Returns a list of dicts: [{"t": 14.2, "line": "Good things dont last"}, ...]
    Returns None if all sources fail.
    """
    print(f"[Fetcher] Looking for lyrics: {title} — {artist}")

    # try all three sources in parallel
    result = asyncio.run(_fetch_all(title, artist))
    return result

async def _fetch_all(title: str, artist: str) -> list | None:
    """
    Fires all three APIs at the same time.
    Returns the best result — synced lyrics preferred over plain.
    """
    import asyncio

    # run all three simultaneously
    results = await asyncio.gather(
        _fetch_lrclib(title, artist),
        _fetch_lyricsovh(title, artist),
        _fetch_genius(title, artist),
        return_exceptions=True
    )

    lrclib_result, ovh_result, genius_result = results

    # priority: synced (lrclib) > plain (ovh) > plain (genius)
    if isinstance(lrclib_result, list) and lrclib_result:
        print("[Fetcher] Found synced lyrics from LRCLIB ✅")
        return _apply_romanization(lrclib_result)

    if isinstance(ovh_result, list) and ovh_result:
        print("[Fetcher] Found plain lyrics from Lyrics.ovh ✅")
        return _apply_romanization(ovh_result)

    if isinstance(genius_result, list) and genius_result:
        print("[Fetcher] Found plain lyrics from Genius ✅")
        return _apply_romanization(genius_result)

    print("[Fetcher] No lyrics found in any source.")
    return None

# ─── Source 1: LRCLIB (synced lyrics) ─────────────────────────────────────────

async def _fetch_lrclib(title: str, artist: str) -> list | None:
    """
    Fetches synced .lrc lyrics from LRCLIB.
    Returns timestamped lines or None.
    """
    try:
        url = "https://lrclib.net/api/get"
        params = {
            "track_name":  title,
            "artist_name": artist,
        }

        # run blocking request in a thread so it doesn't block async loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, params=params, timeout=5)
        )

        if response.status_code != 200:
            return None

        data = response.json()

        # prefer synced lyrics, fall back to plain if needed
        if data.get("syncedLyrics"):
            from src.lyrics.parser import parse_lrc
            return parse_lrc(data["syncedLyrics"])

        if data.get("plainLyrics"):
            return _plain_to_timed(data["plainLyrics"])

        return None

    except Exception as e:
        print(f"[Fetcher] LRCLIB error: {e}")
        return None

# ─── Source 2: Lyrics.ovh (plain lyrics) ──────────────────────────────────────

async def _fetch_lyricsovh(title: str, artist: str) -> list | None:
    """
    Fetches plain lyrics from Lyrics.ovh API.
    """
    try:
        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, timeout=5)
        )

        if response.status_code != 200:
            return None

        data = response.json()
        lyrics_text = data.get("lyrics", "")

        if not lyrics_text:
            return None

        return _plain_to_timed(lyrics_text)

    except Exception as e:
        print(f"[Fetcher] Lyrics.ovh error: {e}")
        return None

# ─── Source 3: Genius (scraper) ───────────────────────────────────────────────

async def _fetch_genius(title: str, artist: str) -> list | None:
    """
    Scrapes lyrics from Genius as a last resort.
    Searches for the song page then extracts the lyrics.
    """
    try:
        # step 1 — search for the song on Genius
        search_url = "https://genius.com/api/search/multi"
        params = {"q": f"{title} {artist}"}
        headers = {"User-Agent": "Mozilla/5.0"}

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(search_url, params=params,
                                 headers=headers, timeout=5)
        )

        if response.status_code != 200:
            return None

        data = response.json()

        # find the song URL from search results
        song_url = _extract_genius_url(data)
        if not song_url:
            return None

        # step 2 — scrape the actual lyrics page
        page = await loop.run_in_executor(
            None,
            lambda: requests.get(song_url, headers=headers, timeout=5)
        )

        if page.status_code != 200:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page.text, "html.parser")

        # Genius wraps lyrics in data-lyrics-container divs
        containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
        if not containers:
            return None

        lines = []
        for container in containers:
            for br in container.find_all("br"):
                br.replace_with("\n")
            lines += container.get_text().split("\n")

        # clean up empty lines
        lines = [l.strip() for l in lines if l.strip()]
        return _plain_to_timed("\n".join(lines))

    except Exception as e:
        print(f"[Fetcher] Genius error: {e}")
        return None

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_genius_url(data: dict) -> str | None:
    """
    Digs through Genius search results to find the song page URL.
    """
    try:
        sections = data["response"]["sections"]
        for section in sections:
            for hit in section.get("hits", []):
                if hit["type"] == "song":
                    return hit["result"]["url"]
    except Exception:
        pass
    return None

def _plain_to_timed(text: str) -> list:
    """
    Converts plain lyrics text into our timed format.
    Since we have no timestamps, we space lines evenly.
    The overlay will auto-scroll them.
    t=0 means no timestamp — overlay handles it differently.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return [{"t": 0.0, "line": line} for line in lines]

def _apply_romanization(lyrics: list) -> list:
    """Apply romanization to lyrics if enabled in settings."""
    from src.core.settings import get as get_setting
    if not get_setting("romanize_lyrics"):
        return lyrics

    from src.lyrics.romanizer import romanize
    print("[Fetcher] Applying romanization...")
    return [
        {"t": entry["t"], "line": romanize(entry["line"])}
        for entry in lyrics
    ]