from src.core.cache import load_cache, save_cache

cache = load_cache()
# find and delete Smooth Operator
to_del = [sid for sid, d in cache.items() 
          if 'smooth' in d['title'].lower()]
for sid in to_del:
    print(f"Deleting: {cache[sid]['title']}")
    del cache[sid]

with open(r"C:\Users\Asim\.lyricslay\cache.json", 
          "w", encoding="utf-8") as f:
    import json
    json.dump(cache, f, ensure_ascii=False, indent=2)
print("Done")