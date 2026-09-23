#!/usr/bin/env python3
"""Score the token-savings arms against a corpus key.

    python3 bench/score_arms.py [--corpus corpus/v2]

Reads every <corpus>/savings/arm_*.json ({"arm", "subagent_tokens", "docs":
[{"id","found","quote"}]}) and prints Claude tokens, correct/64 with a Wilson
interval, and every error. Same outcome rules as bench/score.py.
"""
import argparse, glob, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from quotegate.gate import wilson                     # noqa: E402
from score import load, outcome                       # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", default=str(ROOT / "corpus" / "v2"))
a = ap.parse_args()
corpus = pathlib.Path(a.corpus)
items, claims, judged = load(corpus)
print(f"{'arm':34s} {'Claude tokens':>13s}  correct   [95% CI]   errors")
for f in sorted(glob.glob(str(corpus / "savings" / "arm_*.json"))):
    arm = json.load(open(f))
    counts, errors = {}, []
    for d in arm["docs"]:
        q = d["quote"] if d["found"] else items[d["id"]]["text"][:40]
        o = outcome({"id": d["id"], "status": "ok", "answer": {"found": d["found"], "quote": q}},
                    items, claims, judged)
        counts[o] = counts.get(o, 0) + 1
        if o not in ("TP", "TN"):
            errors.append("%s %s %s" % (o, d["id"], (d["quote"] or "")[:60]))
    ok = counts.get("TP", 0) + counts.get("TN", 0)
    lo, hi = wilson(ok, len(arm["docs"]))
    print(f"{arm['arm']:34s} {arm['subagent_tokens']:>13,}  {ok:2d}/{len(arm['docs'])}  [{100*lo:3.0f}-{100*hi:3.0f}%]  "
          + ("; ".join(errors) if errors else "-"))
