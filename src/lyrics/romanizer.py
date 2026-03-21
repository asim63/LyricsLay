def romanize(text: str) -> str:
    """
    Converts non-Latin scripts to romanized equivalents.
    Supports: Japanese, Korean, Hindi (Devanagari)
    Returns original text if already Latin or unsupported.
    """
    if not text or not text.strip():
        return text

    # if mostly ASCII already — skip
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii < len(text) * 0.3:
        return text

    # detect by Unicode range and romanize
    if _is_japanese(text):
        return _romanize_japanese(text)

    if _is_korean(text):
        return _romanize_korean(text)

    if _is_devanagari(text):
        return _romanize_hindi(text)

    return text  # unsupported script — return original

# ─── Language detection ───────────────────────────────────────────────────────

def _is_japanese(text: str) -> bool:
    """Detects Japanese — Hiragana, Katakana or Kanji."""
    for c in text:
        cp = ord(c)
        if (0x3040 <= cp <= 0x309F or   # Hiragana
                0x30A0 <= cp <= 0x30FF or   # Katakana
                0x4E00 <= cp <= 0x9FFF):    # CJK (Kanji)
            return True
    return False

def _is_korean(text: str) -> bool:
    """Detects Korean — Hangul."""
    for c in text:
        cp = ord(c)
        if 0xAC00 <= cp <= 0xD7A3:  # Hangul syllables
            return True
    return False

def _is_devanagari(text: str) -> bool:
    """Detects Hindi/Devanagari script."""
    for c in text:
        cp = ord(c)
        if 0x0900 <= cp <= 0x097F:  # Devanagari block
            return True
    return False

# ─── Romanizers ───────────────────────────────────────────────────────────────

def _romanize_japanese(text: str) -> str:
    """Japanese → Romaji using pykakasi."""
    try:
        import pykakasi
        kks    = pykakasi.kakasi()
        result = kks.convert(text)
        return " ".join(
            item["hepburn"]
            for item in result
            if item["hepburn"]
        ).strip() or text
    except ImportError:
        print("[Romanizer] pykakasi not installed — pip install pykakasi")
        return text
    except Exception as e:
        print(f"[Romanizer] Japanese error: {e}")
        return text

def _romanize_korean(text: str) -> str:
    """Korean → Romanized using hangul-romanize."""
    try:
        from hangul_romanize import Transliter
        from hangul_romanize.rule import academic
        t = Transliter(academic)
        return t.translit(text)
    except ImportError:
        print("[Romanizer] hangul-romanize not installed — pip install hangul-romanize")
        return text
    except Exception as e:
        print(f"[Romanizer] Korean error: {e}")
        return text

def _romanize_hindi(text: str) -> str:
    """Hindi Devanagari → Latin using indic-transliteration."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        return transliterate(
            text,
            sanscript.DEVANAGARI,
            sanscript.IAST    # IAST = standard Latin for Indian scripts and HK = Harvard-Kyoto, more ASCII-friendly
        )
    except ImportError:
        print("[Romanizer] indic-transliteration not installed — pip install indic-transliteration")
        return text
    except Exception as e:
        print(f"[Romanizer] Hindi error: {e}")
        return text