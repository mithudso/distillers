import json
import re

media_exts = re.compile(r'_(jpg|jpeg|png|gif|pdf|JPG|JPEG|PNG|GIF|PDF)\.html$')

print("Loading index...")
with open("wiki.dmt-nexus.me/.bulk_distill_index.json", "r") as f:
    index = json.load(f)

print(f"Original items: {len(index['unique_units'])}")

keys_to_delete = []
for h, u in index["unique_units"].items():
    text = u["text"]
    
    # Garbage check
    weird_chars = sum(1 for c in text if not (32 <= ord(c) <= 126 or c.isspace()))
    if len(text) > 10 and weird_chars / len(text) > 0.15:
        keys_to_delete.append(h)
        continue
        
    # Source check
    if all(media_exts.search(src) for src in u["sources"]):
        keys_to_delete.append(h)
        continue

for h in keys_to_delete:
    del index["unique_units"][h]

print(f"Cleaned items: {len(index['unique_units'])}")

print("Saving index...")
with open("wiki.dmt-nexus.me/.bulk_distill_index.json", "w") as f:
    json.dump(index, f)
print("Done.")

