import os

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(os.path.expanduser("~"), ".lyricslay")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")

os.makedirs(CACHE_DIR, exist_ok=True)

# ─── Audio ────────────────────────────────────────────────────────────────────
SAMPLE_RATE     = 16000   # Hz — what ShazamIO expects
SAMPLE_DURATION = 5       # seconds for full identification
SAMPLE_RETRY    = 10      # seconds to retry if 5s fails

# ─── Recognition ──────────────────────────────────────────────────────────────
MAX_RETRIES     = 2       # how many times to retry Shazam before giving up
PREFETCH_BEFORE = 30      # seconds before song ends to start prefetching

# ─── Lyrics display ───────────────────────────────────────────────────────────
PAST_LINES        = 1     # how many past lines to show faded above current
MAX_CAPTION_WORDS = 7     # max words per line in unsynced auto-scroll mode
FONT_FAMILY       = "Arial"
FONT_SIZE_CURRENT = 16    # current line — bold and big
FONT_SIZE_PAST    = 11    # past line — small and faded
FONT_SIZE_NEXT    = 11    # next line — small and faded

# ─── Overlay ──────────────────────────────────────────────────────────────────
OVERLAY_WIDTH    = 700    # default width in pixels
OVERLAY_OPACITY  = 0.92   # 0.0 = invisible, 1.0 = fully solid

# ─── Default hotkeys (overridden by settings.json if user changed them) ───────
DEFAULT_TOGGLE_HOTKEY     = "<ctrl>+<shift>+l"
DEFAULT_REIDENTIFY_HOTKEY = "<ctrl>+<shift>+k"