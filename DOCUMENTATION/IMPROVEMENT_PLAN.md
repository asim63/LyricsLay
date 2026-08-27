# LyricsLay — Improvement Plan

> Every phase is self-contained. Test after each phase before moving on.

---

## Current Limitations & Bottlenecks

### 🔴 Critical (Directly Impacts Speed / Reliability)

| # | Issue | Where | Impact |
|---|-------|-------|--------|
| 1 | **PyAudio re-created on every `record_audio()` call** | `src/core/audio.py` | Each detection cycle opens+enumerates devices fresh — ~100-300ms wasted per cycle |
| 2 | **Cache reads full JSON from disk on every `is_cached()` + `get_cached_song()`** | `src/core/cache.py` | 2 disk reads per song check; unbounded file size; no eviction |
| 3 | **WAV file written to disk, then Shazam reads it back** | `src/core/recognizer.py` | Unnecessary I/O roundtrip every identification cycle |
| 4 | **`asyncio.run()` called fresh in `fetch_lyrics()`** | `src/lyrics/fetcher.py` | Creates+destroys an event loop per lyrics fetch — ~10-50ms overhead |
| 5 | **No `requests.Session` reuse** | `src/lyrics/fetcher.py` | Each HTTP call creates a new TCP connection — no keep-alive or connection pooling |
| 6 | **Position resync triggers full Shazam call every 4s** | `main.py` `_check_position_jump` | Heavy API call runs constantly even when song hasn't changed |

### 🟡 Moderate (UX / Stability)

| # | Issue | Where | Impact |
|---|-------|-------|--------|
| 7 | **Tray menu looks plain** — no song info, no visual indicator | `src/ui/tray.py` | Poor UX; user can't see what's playing |
| 8 | **No logging framework** — only `print()` statements | All files | Impossible to debug; logs mixed with stdout; no log levels |
| 9 | **`caption.py` is empty** — dead file | `src/ui/caption.py` | Confusion for contributors |
| 10 | **Settings + cache on same disk path, no atomicity** | `src/core/settings.py`, `cache.py` | Crash during write = corrupted JSON |
| 11 | **Thread safety gaps** — `identifying`, `current_song_id` read/written from multiple threads without locks | `main.py` | Potential race conditions |
| 12 | **No retry with backoff** on network calls | `fetcher.py`, `recognizer.py` | Transient failures kill the entire identification |

### 🟢 Minor (Code Quality / Future-Proofing)

| # | Issue | Where | Impact |
|---|-------|-------|--------|
| 13 | **Hardcoded Windows paths** — `APPDATA`, `msvcrt`, `ctypes.windll` | `config.py`, `main.py`, `overlay.py` | Can't port to macOS/Linux |
| 14 | **`_resample` uses linear interpolation** — not a proper resampler | `src/core/audio.py` | Slight audio quality loss at non-native sample rates |
| 15 | **No `requirements.txt` pinned versions** | `requirements.txt` | Builds may break with dependency updates |
| 16 | **`_quick_fingerprint` only 4 features** — ZCR/centroid/rolloff/RMS | `main.py` | False positives on songs with similar spectral profiles |
| 17 | **No error boundary for Shazam library** | `src/core/recognizer.py` | ShazamIO exceptions may propagate unhandled |
| 18 | **Romanizer instantiated fresh per line** | `src/lyrics/romanizer.py` | pykakasi `kakasi()` object created per line instead of once |

---

## Phase 1 — Speed: Reuse PyAudio + Session + Event Loop

> **Goal:** Cut detection cycle overhead by ~300-500ms per cycle

### Changes

1. **`src/core/audio.py`** — Create PyAudio instance once, pass through:
   - Add a module-level `_pyaudio` singleton
   - Reuse the device index across calls instead of re-enumerating
   - Cache the loopback device info

2. **`src/lyrics/fetcher.py`** — Reuse `requests.Session`:
   - Create a module-level `Session` with connection pooling
   - Create a module-level event loop + reuse it (instead of `asyncio.run()` each time)

3. **`src/core/recognizer.py`** — Send audio bytes directly to ShazamIO:
   - Check if `shazamio.Shazam.recognize()` accepts raw bytes/pipe instead of file path
   - If not, at minimum reuse the WAV path and only overwrite the bytes

### Test
- Launch app, play music
- Verify first identification works
- Verify subsequent song changes trigger faster
- Check terminal output — no "PyAudio" device enumeration logs repeating

---

## Phase 2 — Speed: Smart Caching (In-Memory + Disk)

> **Goal:** Eliminate redundant disk reads; cache check becomes instant

### Changes

1. **`src/core/cache.py`** — Add in-memory cache layer:
   - Load full cache dict once into memory at startup
   - `is_cached()` checks the in-memory dict (O(1), no disk read)
   - `cache_song()` writes to memory first, then flushes to disk
   - Add a `flush()` method called on app exit
   - Add basic size limit (e.g. 500 songs max, LRU eviction)

2. **`src/core/cache.py`** — Atomic writes:
   - Write to a `.tmp` file first, then `os.rename()` to prevent corruption

### Test
- Start app → play a song → verify it caches
- Play the same song again → verify instant cache hit (check terminal timestamps)
- Kill app mid-write, relaunch → verify cache file isn't corrupted

---

## Phase 3 — Position Check: Smarter, Not Slower

> **Goal:** Make position checks fast and accurate while keeping them frequent

### Context
The current position check runs a full Shazam API call every cycle (~4 seconds). This is
heavy but keeps lyrics accurately synced. The goal is to make this **smarter** — not to
reduce frequency, but to skip unnecessary Shazam calls when the audio is stable, while
keeping the checks frequent for quick skip detection and accurate sync.

### Changes

1. **Fingerprint-based skip detection** (`main.py`):
   - Compare current fingerprint to the one from the last position check
   - If fingerprint difference < 35% → audio is stable → **skip Shazam** (overlay timer handles scrolling)
   - If fingerprint difference ≥ 35% → likely a skip → call Shazam to get new position
   - This eliminates ~80% of Shazam calls during normal playback

2. **Periodic drift correction** (`main.py`):
   - Every 12 seconds, run Shazam regardless of fingerprint to correct timer drift
   - If drift > 1s: apply 60% gradual correction (gentle, no jarring jump)
   - If drift > 3s + skip detected: snap immediately to new position

3. **Signal-based lyrics refresh** (`overlay.py`):
   - Add `drift_corrected` signal to `LyricsOverlay`
   - After drift correction, emit signal → overlay recalculates lyric index on main thread
   - Prevents frozen lyrics after time correction

### Architecture
```
Every 4s cycle:
  ├── Fingerprint stable (< 35%)? → No Shazam, overlay timer scrolls
  ├── Fingerprint jump (≥ 35%)?   → Shazam → snap if >3s drift
  └── 12s since last drift check? → Shazam → correct drift if >1s
```

### Test
- Play a song — lyrics should scroll normally
- Skip to a different position — lyrics should resync within 4-8 seconds
- Let song play for 2+ minutes — watch for `Drift correction` messages
- Lyrics should stay in sync without freezing after corrections

---


## Phase 4 — Tray UI Redesign

> **Goal:** Make the tray menu look modern and show useful info

### Changes

1. **`src/ui/tray.py`** — Redesigned menu:
   - Show **current song title + artist** at the top of the menu (greyed out, non-clickable)
   - Add a **separator with the song info**
   - Better icon: generate a more distinctive fallback icon (music note + "L" badge)
   - Add "About" section at bottom with version info
   - Add keyboard shortcut hints in menu items (e.g. "Toggle lyrics  Ctrl+Shift+L")

2. **`src/ui/tray.py`** — Dynamic tray tooltip:
   - Update tooltip to show "Now Playing: Title — Artist" when a song is recognized

3. **`src/ui/tray.py`** — Menu polish:
   - Improve spacing and padding
   - Add subtle icon/text hierarchy
   - Consider adding a small "Album art" placeholder area

### Test
- Right-click tray icon → verify new menu layout
- Play a song → verify song title appears in tray tooltip
- Verify all menu actions still work (toggle, romanization, settings, etc.)

---

## Phase 5 — Logging & Error Handling

> **Goal:** Replace all `print()` with structured logging; add retry logic

### Changes

1. **New file: `src/core/logger.py`** — Centralized logger:
   - Use Python `logging` module
   - Console handler with colored output (INFO = green, WARNING = yellow, ERROR = red)
   - File handler writing to `APPDATA/LyricsLay/logs/`
   - Log rotation (max 5MB, keep 3 files)
   - Format: `[HH:MM:SS] [LEVEL] [Module] message`

2. **All files** — Replace `print()` with logger:
   - `logger.info()`, `logger.warning()`, `logger.error()` as appropriate

3. **`src/lyrics/fetcher.py`** — Add retry with exponential backoff:
   - 3 retries with 1s/2s/4s delays for HTTP failures
   - Only retry on 5xx or network errors, not 4xx

4. **`src/core/recognizer.py`** — Add Shazam retry:
   - If Shazam returns no match, retry once after 2s
   - Wrap ShazamIO exceptions properly

### Test
- Trigger an identification → verify clean log output
- Disconnect internet briefly → verify retry messages appear
- Check `APPDATA/LyricsLay/logs/` for log file creation

---

## Phase 6 — Thread Safety & Stability

> **Goal:** Eliminate race conditions; make app crash-proof

### Changes

1. **`main.py`** — Add proper locking:
   - Protect `current_song_id`, `current_fingerprint`, `identifying` with a single `threading.Lock`
   - Use `threading.Event` for the `force_reidentify_flag` instead of a bare boolean

2. **`src/core/cache.py`** — Add file locking:
   - Use `msvcrt.locking()` or a `.lock` file for concurrent access safety

3. **`main.py`** — Add global exception handler:
   - `sys.excepthook` → log + show tray notification instead of silent crash
   - Wrap the detector loop in a top-level try/except that logs + continues

4. **`src/core/recognizer.py`** — Handle ShazamIO edge cases:
   - Catch `asyncio.TimeoutError`
   - Catch `aiohttp.ClientError`
   - Return `None` gracefully instead of crashing

### Test
- Force-identify several songs rapidly (Ctrl+Shift+K spam)
- Switch songs quickly
- Verify no crashes or traceback in terminal

---

## Phase 7 — Code Cleanup & Polish

> **Goal:** Remove dead code, improve maintainability

### Changes

1. **Delete `src/ui/caption.py`** — it's empty
2. **`src/lyrics/romanizer.py`** — Cache romanizer instances:
   - Create `pykakasi.kakasi()` once at module level
   - Create `Transliter` once at module level
   - Reuse for all lines instead of per-line instantiation
3. **`requirements.txt`** — Pin dependency versions:
   - Run `pip freeze` and pin exact versions
4. **Add `pyproject.toml`** — Modern Python project metadata
5. **`main.py`** — Extract `_identify_and_load` into a separate file (e.g. `src/core/identifier.py`) to keep main.py focused on the app lifecycle

### Test
- Full app lifecycle: start → identify → change songs → toggle overlay → settings → quit
- Verify no regressions

---

## Phase 8 (Optional) — Future Enhancements

These are larger scope and can be done later:

| Feature | Description |
|---------|-------------|
| **Live caption fallback** | Use Windows Speech API for unrecognised songs |
| **Lyrics preview in tray** | Show next 1-2 lines in tooltip or a flyout |
| **Keyboard-driven overlay** | Arrow keys to skip forward/back in lyrics |
| **macOS/Linux support** | Replace WASAPI with platform-appropriate audio capture |
| **Auto-updater** | Check GitHub releases for new versions |
| **Theme customization** | User-configurable colors, fonts, overlay opacity |

---

## Testing Checklist (Run After Each Phase)

```
□ App starts without errors
□ Tray icon visible in system tray
□ Play music → identification works
□ Lyrics appear on overlay
□ Lyrics scroll with playback
□ Song change triggers re-identification
□ Ctrl+Shift+L toggles overlay
□ Ctrl+Shift+K force-reidentifies
□ Settings window opens and saves
□ Romanization toggle works
□ No console errors / crashes after 5 minutes of use
```
