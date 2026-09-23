#!/usr/bin/env python3
"""Simulate staged sweep policies on saved runs - no GPU, no model calls.

    python3 bench/tiers.py [--corpus corpus/v2]  # the standard tiers
    python3 bench/tiers.py --first A --second B --tiebreak C --tripwire D

Arguments are run names (or unique substrings) from corpus/runs. Policy, as in
the skill's sweep.py: FIRST answers every item; SECOND answers every item and
agreement (same sentence, or both "none") decides; TIEBREAK runs only where
they disagree and sides with whichever it agrees with; TRIPWIRE runs only on
items decided "none" and, if it finds anything, sends the item to Claude.
Undecided items are Claude's. Time = sum of measured per-item seconds of the
stages each item actually went through.
"""
import argparse, glob, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from quotegate import policy                           # noqa: E402
from quotegate.gate import validate                     # noqa: E402
from score import load, outcome                         # noqa: E402

CORPUS = ROOT / "corpus"
if "--corpus" in sys.argv:
    _i = sys.argv.index("--corpus"); CORPUS = pathlib.Path(sys.argv[_i + 1]).resolve()
    del sys.argv[_i:_i + 2]
items, claims, judged = load(CORPUS)
RUNS = {pathlib.Path(p).name.replace(".raw.jsonl", ""): p
        for p in glob.glob(str(CORPUS / "runs/*.raw.jsonl"))}


def pick(sub):
    hits = [n for n in RUNS if sub in n]
    if len(hits) != 1:
        sys.exit("run %r matches %d runs: %s" % (sub, len(hits), hits))
    return hits[0]


def answers(name):
    out, secs = {}, {}
    for l in open(RUNS[name]):
        r = json.loads(l); a = r.get("answer") or {}; m = r.get("meta") or {}
        text = items[r["id"]]["text"]
        if r["status"] == "error" or not validate(a, text)[0]:
            out[r["id"]] = ("drop", None)
        else:
            out[r["id"]] = ("find", a["quote"]) if a.get("found") else ("none", None)
        secs[r["id"]] = ((m.get("total_duration") or 0) - (m.get("load_duration") or 0)) / 1e9
    return out, secs


def correct(dec, doc):
    fake = {"id": doc, "status": "ok",
            "answer": {"found": dec[0] == "find", "quote": dec[1] or items[doc]["text"][:40]}}
    return outcome(fake, items, claims, judged) in ("TP", "TN")


def simulate(first, second=None, tiebreak=None, tripwire=None):
    """The same rules as the live sweep: quotegate.policy is the only copy."""
    A = {k: answers(k) for k in (first, second, tiebreak, tripwire) if k}
    r = w = u = 0; t = 0.0
    for doc in items:
        text = items[doc]["text"]
        p = A[first][0][doc]; t += A[first][1][doc]
        if not second:
            dec = policy.after_first(p)
        else:
            s = A[second][0][doc]; t += A[second][1][doc]
            dec, needs = policy.after_second(p, s, text)
            if needs and tiebreak:
                t += A[tiebreak][1][doc]
                dec = policy.after_tiebreak(p, s, A[tiebreak][0][doc], text)
            if tripwire and policy.needs_tripwire(dec):
                t += A[tripwire][1][doc]
                dec = policy.after_tripwire(dec, A[tripwire][0][doc])
        if dec is None:
            u += 1
        elif correct(dec, doc):
            r += 1
        else:
            w += 1
    return r, w, u, t / len(items)


def row(label, **kw):
    r, w, u, s = simulate(**kw)
    print(f"{label:52s} {r+w:7d} {r:5d} {w:5d} {100*w/max(r+w,1):5.1f}% {u:6d} {s:7.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k in ("first", "second", "tiebreak", "tripwire"):
        ap.add_argument("--" + k)
    a = ap.parse_args()
    print(f"{'policy':52s} {'decided':>7s} {'right':>5s} {'wrong':>5s} {'err':>6s} {'Claude':>6s} {'s/item':>7s}")
    if a.first:
        row("custom", **{k: pick(v) for k, v in vars(a).items() if v})
    else:
        g12, g26 = pick("gemma4_12b-it-qat_ep-chat_think-off_fmt-schema_2080ti_careful"), pick("gemma4_26b-a4b-it-qat_ep-chat_think-off_fmt-schema_dual_careful")
        oss, q38e = pick("gpt-oss_20b_ep-chat_think-auto_fmt-schema_quadro_careful"), pick("qwen3.8_27b_ep-chat_think-off_fmt-schema_dual_eager")
        q38 = pick("qwen3.8_27b_ep-chat_think-off_fmt-schema_dual_careful")
        row("tier 1  fast     gemma4:12b careful", first=g12)
        row("tier 2  checked  + gemma4:26b, gpt-oss tie-break", first=g12, second=g26, tiebreak=oss)
        row("tier 3  strict   + qwen3.8 eager tripwire", first=g12, second=g26, tiebreak=oss, tripwire=q38e)
        row("single  gemma4:26b careful", first=g26)
        row("single  qwen3.8:27b careful", first=q38)
