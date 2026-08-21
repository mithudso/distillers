import re
import math

def categorize(text):
    if text.endswith('?'): return "Questions"
    if re.search(r'\b(should|must|need to|run|add|ensure)\b', text, re.I): return "Actionables"
    return "Statements"

actionables = []
questions = []
statements = []

with open("wiki.dmt-nexus.me/bulk_master.md", "r") as f:
    for line in f:
        if not line.startswith("- "): continue
        
        # Regex to extract text before the _sources_ part
        match = re.match(r'- (.*?) _.*?_(\s+\[x\d+\])?\s*$', line)
        if match:
            text = match.group(1).strip()
        else:
            text = line.strip()[2:]
            
        cat = categorize(text)
        if cat == "Actionables":
            actionables.append(line)
        elif cat == "Questions":
            questions.append(line)
        else:
            statements.append(line)

def write_chunks(prefix, lines, chunk_size=50000):
    if len(lines) <= chunk_size:
        with open(f"wiki.dmt-nexus.me/{prefix}.md", "w") as f:
            f.writelines(lines)
    else:
        for i in range(math.ceil(len(lines) / chunk_size)):
            with open(f"wiki.dmt-nexus.me/{prefix}_part_{i+1}.md", "w") as f:
                f.writelines(lines[i*chunk_size : (i+1)*chunk_size])

write_chunks("bulk_master_Actionables", actionables)
write_chunks("bulk_master_Questions", questions)
write_chunks("bulk_master_Statements", statements)

print(f"Actionables: {len(actionables)}")
print(f"Questions: {len(questions)}")
print(f"Statements: {len(statements)}")
