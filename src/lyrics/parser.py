import re

def parse_lrc(lrc_text: str) -> list:
    """
    Parses .lrc format lyrics into our timed format.

    .lrc format looks like this:
    [00:14.20] Good things don't last
    [00:17.80] Life moves so fast
    [00:21.10] The road winds on and on

    We convert it to:
    [
        {"t": 14.2,  "line": "Good things don't last"},
        {"t": 17.8,  "line": "Life moves so fast"},
        {"t": 21.1,  "line": "The road winds on and on"},
    ]
    """
    lines = []

    for raw_line in lrc_text.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # match timestamp pattern [MM:SS.xx]
        match = re.match(r"\[(\d+):(\d+\.\d+)\](.*)", raw_line)
        if not match:
            continue

        minutes  = int(match.group(1))
        seconds  = float(match.group(2))
        text     = match.group(3).strip()

        # convert MM:SS to total seconds
        total_seconds = (minutes * 60) + seconds

        # skip empty lines but keep them as blank spacers
        lines.append({
            "t":    round(total_seconds, 2),
            "line": text
        })

    return lines