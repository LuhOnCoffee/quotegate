#!/usr/bin/env python3
"""Replay tiers 1-3 from the votes a live tier-3 sweep recorded, and score them.

    python3 bench/replay_sweep.py corpus/v3/sweep-live/tier3.decisions.jsonl.votes.jsonl --corpus corpus/v3

A tier-3 sweep asks every model it needs, so its votes also say what tiers 1
and 2 would have decided - through the same policy code the sweep uses. The
tier-3 line must equal bench/score_sweep.py on the live output; if it does not,
the replay is wrong, not the sweep.
"""
import argparse, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from quotegate.policy import (FIND, after_first, after_second, after_tiebreak,  # noqa: E402
                              after_tripwire, needs_tripwire, to_vote)
from score import load, outcome                                                 # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("votes")
ap.add_argument("--corpus", default=str(ROOT / "corpus" / "v2"))
a = ap.parse_args()
items, claims, judged = load(pathlib.Path(a.corpus))
votes = {}
for line in open(a.votes):
    r = json.loads(line)
    votes.setdefault(r["id"], {})[r["role"]] = r

tiers = {1: {}, 2: {}, 3: {}}
for i, v in votes.items():
    text = items[i]["text"]
    first = to_vote(v["first"], text)
    tiers[1][i] = after_first(first)
    second = to_vote(v["second"], text)
    dec, tb = after_second(first, second, text)
    if tb:
        dec = after_tiebreak(first, second, to_vote(v["tiebreak"], text), text) if "tiebreak" in v else None
    tiers[2][i] = dec
    tiers[3][i] = (after_tripwire(dec, to_vote(v["tripwire"], text))
                   if needs_tripwire(dec) and "tripwire" in v else dec)

for t, decs in tiers.items():
    d = w = u = 0
    for i, x in decs.items():
        if x is None:
            u += 1
            continue
        d += 1
        rec = {"id": i, "status": "kept",
               "answer": {"found": x[0] == FIND, "quote": x[1] or items[i]["text"][:40]}}
        w += outcome(rec, items, claims, judged) not in ("TP", "TN")
    print("tier %d  decided %2d  wrong %2d (%4.1f%%)  to Claude %2d" % (t, d, w, 100 * w / d, u))
