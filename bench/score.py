#!/usr/bin/env python3
"""Score every run in corpus/runs against corpus/key.json.

    python3 bench/score.py [--corpus corpus] [--unkeyed]

Outcome per document (one answer per document):
  TP       verbatim quote at the same place as a keyed stale claim
  WRONG    verbatim quote that is not stale (a judged verdict in key.json)
  UNKEYED  verbatim quote matching no key entry and no verdict - READ it,
           then record a verdict; the key has been incomplete before
  FAB      quote not verbatim: dropped by the gate
  FN / TN  found=false on a document that does / does not have a stale claim
  ERR      request failed, truncation guard, or reasoning ran to the cap
usable = TP + TN, the answers a pipeline can act on without a human.
"""
import argparse, glob, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quotegate.gate import norm, same_place, validate, wilson   # noqa: E402

COLS = ["TP", "WRONG", "UNKEYED", "FAB", "FN", "TN", "ERR"]


def load(corpus):
    items = {json.loads(l)["id"]: json.loads(l) for l in open(corpus / "items.jsonl")}
    key = json.load(open(corpus / "key.json"))
    return items, key["docs"], key.get("judged", {})


def outcome(r, items, claims, judged):
    doc = r["id"]; text = items[doc]["text"]
    stale = any(not c["corrected_in_doc"] for c in claims.get(doc, []))
    if r["status"] == "error":
        return "ERR"
    a = r.get("answer") or {}
    if not validate(a, text)[0]:
        return "FAB"
    if not a.get("found"):
        return "FN" if stale else "TN"
    if any(same_place(a["quote"], c["quote"], text) for c in claims.get(doc, [])):
        return "TP"
    return {"correct": "TP", "wrong": "WRONG"}.get(judged.get(doc, {}).get(norm(a["quote"])), "UNKEYED")


def score_run(path, items, claims, judged):
    counts, secs, toks, gen, n, unkeyed = {}, 0.0, 0, 0.0, 0, []
    for l in open(path):
        r = json.loads(l); m = r.get("meta") or {}
        o = outcome(r, items, claims, judged)
        counts[o] = counts.get(o, 0) + 1
        if o == "UNKEYED":
            unkeyed.append((r["id"], r["answer"]["quote"]))
        secs += ((m.get("total_duration") or 0) - (m.get("load_duration") or 0)) / 1e9
        toks += m.get("eval_count") or 0
        gen += (m.get("eval_duration") or 0) / 1e9
        n += 1
    return counts, n, secs / max(n, 1), (toks / gen if gen else 0), unkeyed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus"))
    ap.add_argument("--unkeyed", action="store_true", help="list unkeyed answers")
    a = ap.parse_args()
    corpus = pathlib.Path(a.corpus)
    items, claims, judged = load(corpus)
    n_stale = sum(1 for d in items if any(not c["corrected_in_doc"] for c in claims.get(d, [])))
    print(f"corpus: {len(items)} docs, {n_stale} with an uncorrected stale claim\n")
    print(f"{'run':60s} " + " ".join(f"{c:>5s}" for c in COLS)
          + "  usable [95% CI]      prec   s/doc  tok/s")
    todo = []
    for p in sorted(glob.glob(str(corpus / "runs/*.raw.jsonl"))):
        c, n, sdoc, tps, unk = score_run(p, items, claims, judged)
        use = c.get("TP", 0) + c.get("TN", 0)
        lo, hi = wilson(use, n)
        tpw = c.get("TP", 0) + c.get("WRONG", 0)
        prec = "%4.0f%%" % (100 * c.get("TP", 0) / tpw) if tpw else "   -"
        name = pathlib.Path(p).name.replace(".raw.jsonl", "")
        print(f"{name:60s} " + " ".join(f"{c.get(k, 0):5d}" for k in COLS)
              + f"  {use:2d}/{n} [{100*lo:3.0f}-{100*hi:3.0f}%]  {prec}  {sdoc:5.1f}  {tps:5.1f}")
        todo += [(name, d, q) for d, q in unk]
    if todo:
        print(f"\n{len(todo)} UNKEYED answers need a verdict (read them first)")
        if a.unkeyed:
            for name, d, q in todo:
                print(f"  {name} | {d} | {q[:150]}")


if __name__ == "__main__":
    main()
