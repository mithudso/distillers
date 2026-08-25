import os
import glob
import re

# Define what constitutes a media file extension in this wiki scrape
media_exts = re.compile(r'_(jpg|jpeg|png|gif|pdf|JPG|JPEG|PNG|GIF|PDF)\.html$')

for md_file in glob.glob("wiki.dmt-nexus.me/bulk_master_*.md"):
    with open(md_file, "r") as f:
        lines = f.readlines()
        
    cleaned_lines = []
    for line in lines:
        if not line.startswith("- "):
            cleaned_lines.append(line)
            continue
            
        # Check if it has a high concentration of non-ascii or non-printable chars
        text_part = line.rsplit("_", 2)[0] if "_" in line else line
        # If more than 20% of the characters are weird symbols, drop it
        weird_chars = sum(1 for c in text_part if not (32 <= ord(c) <= 126 or c.isspace()))
        if len(text_part) > 10 and weird_chars / len(text_part) > 0.15:
            continue
            
        # Check if the sources are exclusively media files
        match = re.search(r'_(.*?)_(\s+\[x\d+\])?\s*$', line)
        if match:
            sources = match.group(1).split(", ")
            if all(media_exts.search(src) for src in sources):
                continue
                
        cleaned_lines.append(line)
        
    with open(md_file, "w") as f:
        f.writelines(cleaned_lines)
        
    print(f"Cleaned {md_file}: {len(lines)} -> {len(cleaned_lines)}")

