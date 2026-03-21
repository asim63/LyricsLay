from src.core.settings import get
from src.core.cache import is_cached, load_cache

# check romanization setting
print(f"Romanize ON: {get('romanize_lyrics')}")
print()

# check all cached songs
cache = load_cache()
print(f"Total cached: {len(cache)}")
print()

for sid, data in cache.items():
    has_rom = is_cached(f"{sid}_rom")
    print(f"{data['title']} by {data['artist']}")
    print(f"  Original ({sid}): ✅")
    print(f"  Romanized ({sid}_rom): {'✅' if has_rom else '❌ not yet'}")
    print()