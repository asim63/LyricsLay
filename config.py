import os

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(os.path.expanduser("~"), ".lyricslay")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")

# create the cache folder if it doesn't exist yet
os.makedirs(CACHE_DIR, exist_ok=True)

# ─── Audio ────────────────────────────────────────────────────────────────────
SAMPLE_RATE     = 16000   # Hz — what ShazamIO expects
SAMPLE_DURATION = 5       # seconds to record before sending to Shazam
SAMPLE_RETRY    = 10      # seconds to retry if 5s fails

# ─── Recognition ──────────────────────────────────────────────────────────────
MAX_RETRIES     = 2       # how many times to retry Shazam before giving up
PREFETCH_BEFORE = 30      # seconds before song ends to start prefetching next

# ─── Lyrics display ───────────────────────────────────────────────────────────
PAST_LINES      = 1       # how many past lines to show faded above current
MAX_CAPTION_WORDS = 7     # max words per line in live caption mode
FONT_FAMILY     = "Arial"
FONT_SIZE_CURRENT = 22    # current line — bold and big
FONT_SIZE_PAST    = 14    # past line — small and faded
FONT_SIZE_NEXT    = 14    # next line — small and faded

# ─── Overlay ──────────────────────────────────────────────────────────────────
OVERLAY_WIDTH    = 700      # medium — comfortable reading width
OVERLAY_OPACITY  = 0.92     # 0.0 = invisible, 1.0 = fully solid
OVERLAY_POSITION = ("center", 40)  # top center, 40px from top of screen
# ─── Hotkey ───────────────────────────────────────────────────────────────────
TOGGLE_HOTKEY   = "<ctrl>+<shift>+l"

# ─── Live captions ────────────────────────────────────────────────────────────
WHISPER_MODEL   = "tiny"  # tiny=75MB, base=145MB, small=460MB
                          # tiny is fast enough for real-time on most PCs
