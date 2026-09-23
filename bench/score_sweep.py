#!/usr/bin/env python3
"""Score a `quotegate sweep` output file against a corpus key.

    python3 bench/score_sweep.py <sweep-out.jsonl> [--corpus corpus/v2]

Prints decided / right / wrong / undecided - the same columns as bench/tiers.py,
so a live sweep can be checked against the offline simulation of the same tier.
"""
import argparse, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from score import load, outcome                          # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--corpus", default=str(ROOT / "corpus"))
a = ap.parse_args()
items, claims, judged = load(pathlib.Path(a.corpus))
r = w = u = 0
for line in open(a.out):
    x = json.loads(line)
    if x["decision"] == "undecided":
        u += 1
        continue
    rec = {"id": x["id"], "status": "kept",
           "answer": {"found": x["decision"] == "finding",
                      "quote": x["quote"] or items[x["id"]]["text"][:40]}}
    o = outcome(rec, items, claims, judged)
    if o in ("TP", "TN"):
        r += 1
    else:
        w += 1
        print("  WRONG %-9s %s | %s" % (x["decision"], x["id"], (x["quote"] or "")[:90]))
print("decided %d  right %d  wrong %d (%.1f%%)  undecided %d"
      % (r + w, r, w, 100 * w / max(r + w, 1), u))
