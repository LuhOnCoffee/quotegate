#!/usr/bin/env python3
"""Build the blind-keying input and the benchmark items from projects/.

    python3 anonymise.py

Writes keyinput/<project>/<project>-dNN.txt (documents under neutral ids,
shuffled per project with a fixed seed, so a keyer cannot read the kind from
the filename), keyinput/<project>/FACTS.txt, items.jsonl (what models see:
id, project, text, facts) and construction_key.json (id -> kind and the
inserted sentence; never shown to keyers or models)."""
import json, pathlib, random

root = pathlib.Path("projects"); outd = pathlib.Path("keyinput"); outd.mkdir(exist_ok=True)
mapping, items = {}, []
rng = random.Random(20260921)
for proj in sorted(p.name for p in root.iterdir() if p.is_dir()):
    m = json.load(open(root / proj / "manifest.json"))
    facts = json.load(open(root / proj / "facts.json"))["facts"]
    fact_text = "\n".join(f"- {f['fact']}" for f in facts)
    docs = list(m["docs"]); rng.shuffle(docs)
    (outd / proj).mkdir(exist_ok=True)
    (outd / proj / "FACTS.txt").write_text(fact_text + "\n")
    if pathlib.Path("expansion.json").exists():     # v4: what an out-of-date doc might say
        exp = json.load(open("expansion.json"))["projects"][proj]
        (outd / proj / "EXPANSION.txt").write_text(
            "What an out-of-date document might still say, show or tell the reader to do\n"
            "(patterns that would be wrong now - not facts, not an exhaustive list):\n"
            + "".join(f"- {line}\n" for f in facts for line in exp[f["id"]]))
    for i, d in enumerate(docs, 1):
        did = f"{proj}-d{i:02d}"
        text = (root / proj / d["file"]).read_text()
        (outd / proj / f"{did}.txt").write_text(text)
        mapping[did] = {"project": proj, "file": d["file"], "kind": d["kind"],
                        "inserted": d["inserted"], "inserted_fact": d["inserted_fact"]}
        items.append({"id": did, "project": proj, "path": str(root / proj / d["file"]),
                      "text": text, "facts": fact_text})
json.dump(mapping, open("construction_key.json", "w"), indent=1)
open("items.jsonl", "w").write("".join(json.dumps(i) + "\n" for i in items))
print(len(items), "items")
