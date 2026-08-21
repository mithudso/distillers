import re

topics = {
    "Extraction Techniques": [
        r'\btek\b', r'\bfasa\b', r'\bfasi\b', r'\bfasw\b', r'\bnaphtha\b', r'\bheptane\b', r'\blimonene\b', 
        r'\bacetone\b', r'\blime\b', r'\bcarbonate\b', r'\bbicarbonate\b', r'\bprecipitate\b', r'\bevaporate\b', 
        r'\byields?\b', r'\bpulls?\b', r'\bfreeze\b', r'\bdecant\b', r'\bfilter\b', r'\bscrape\b', r'\bsolvent\b',
        r'\bstb\b', r'\ba/b\b', r'\blye\b', r'\bacid\b', r'\bbase\b', r'\bvinegar\b', r'\bsalt\b', r'\btek\b'
    ],
    "Botany & Plant Species": [
        r'\broot\s*bark\b', r'\bmhrb\b', r'\bmimosa\b', r'\bhostilis\b', r'\bacacia\b', r'\bphalaris\b', 
        r'\bpsychotria\b', r'\bviridis\b', r'\byuremamine\b', r'\bvirola\b', r'\bphyllodes\b', r'\bpods\b', 
        r'\bseeds?\b', r'\bglabrous\b', r'\bhabitat\b', r'\bprovince\b', r'\bshredded\b', r'\bbotanical\b'
    ],
    "Administration & Hardware": [
        r'\bmachine\b', r'\bbubbler\b', r'\bvaporize[dr]?\b', r'\bmesh\b', r'\blighter\b', r'\bflame\b', 
        r'\bsmoking\b', r'\bpipe\b', r'\bbong\b', r'\binhale\b', r'\blungs\b', r'\bglass\b'
    ],
    "Experiences & Psychology": [
        r'\btrip\b', r'\bhyperspace\b', r'\banxiety\b', r'\bentity\b', r'\bentities\b', r'\bpsychedelic\b',
        r'\bdosage\b', r'\bthreshold\b', r'\bmg\b', r'\beuphoric\b', r'\bhallucinogen\b', r'\bvisuals\b',
        r'\bego\b', r'\bdeath\b', r'\bbreakthrough\b'
    ],
    "Chemistry & Pharmacology": [
        r'\balkaloids?\b', r'\bpka\b', r'\bmolecule\b', r'\breagent\b', r'\bph\b', r'\bfumarate\b', 
        r'\bfreebase\b', r'\bharmala\b', r'\bmaoi\b', r'\bcaapi\b', r'\bayahuasca\b', r'\bspectrum\b',
        r'\bchanga\b', r'\bbeta-carboline\b', r'\bserotonin\b', r'\breceptor\b'
    ],
    "Wiki Boilerplate": [
        r'jump to: navigation', r'retrieved from\s+views', r'about dmt-nexus wiki'
    ]
}

# Compile regexes
compiled_topics = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in topics.items()}

categorized_data = {k: {"Actionables": [], "Questions": [], "Statements": []} for k in topics.keys()}
categorized_data["Uncategorized"] = {"Actionables": [], "Questions": [], "Statements": []}

current_type = "Statements"

with open("wiki.dmt-nexus.me/bulk_master.md", "r") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        
        if line.startswith("## Actionables"):
            current_type = "Actionables"
            continue
        elif line.startswith("## Questions"):
            current_type = "Questions"
            continue
        elif line.startswith("## Statements"):
            current_type = "Statements"
            continue
            
        if not line.startswith("- "): continue
        
        # Determine category
        assigned_cat = "Uncategorized"
        
        # Check Boilerplate first
        is_boilerplate = False
        for p in compiled_topics["Wiki Boilerplate"]:
            if p.search(line):
                assigned_cat = "Wiki Boilerplate"
                is_boilerplate = True
                break
                
        if not is_boilerplate:
            for cat, patterns in compiled_topics.items():
                if cat == "Wiki Boilerplate": continue
                if any(p.search(line) for p in patterns):
                    assigned_cat = cat
                    break
                    
        categorized_data[assigned_cat][current_type].append(line)

out_file = "dmt_categorized.md"
with open(out_file, "w") as f:
    f.write("# DMT Categorized Knowledge Base\n\n")
    
    for cat in ["Extraction Techniques", "Botany & Plant Species", "Administration & Hardware", 
                "Chemistry & Pharmacology", "Experiences & Psychology", "Uncategorized", "Wiki Boilerplate"]:
        
        f.write(f"## {cat}\n\n")
        
        for ttype in ["Actionables", "Questions", "Statements"]:
            lines = categorized_data[cat][ttype]
            if lines:
                f.write(f"### {ttype}\n\n")
                f.write("\n".join(lines))
                f.write("\n\n")

print("Done categorization.")

