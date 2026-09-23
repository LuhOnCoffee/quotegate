#!/usr/bin/env python3
"""Every number claimed in README.md and RESULTS.md, recomputed from the saved
data and checked to still appear in the text.

    python3 bench/check_claims.py

A results file drifts from its evidence quietly; this makes it loud. It checks
the headline figures only - the rest of each table is printed by bench/score.py
and bench/tiers.py, which CI also runs.
"""
import glob, json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from score import load, outcome                            # noqa: E402

fails, checks = [], 0


def claim(text, needle, why):
    """Formatting is ignored: the tables bold their headline numbers."""
    global checks
    checks += 1
    flat = text.replace("**", "")
    if needle not in flat:
        fails.append("%s: %r not found (%s)" % (why, needle, why))


def arm(corpus, name):
    """(tokens, correct) recomputed from the saved per-arm answers."""
    items, claims_, judged = load(corpus)
    for f in glob.glob(str(corpus / "savings" / "arm_*.json")):   # the headline (Opus 5.5) runs
        a = json.load(open(f))
        if a["arm"] != name:
            continue
        ok = sum(outcome({"id": d["id"], "status": "ok",
                          "answer": {"found": d["found"],
                                     "quote": d["quote"] if d["found"] else items[d["id"]]["text"][:40]}},
                         items, claims_, judged) in ("TP", "TN") for d in a["docs"])
        return a["subagent_tokens"], ok
    raise SystemExit("no saved arm %r in %s" % (name, corpus))


readme = (ROOT / "README.md").read_text()
results = (ROOT / "RESULTS.md").read_text()
v2 = ROOT / "corpus" / "v2"

v1 = ROOT / "corpus"
V2_ARMS = [("claude-only", "Claude alone"), ("with-quotegate", "quotegate"),
           ("with-quotegate+skim (run 1)", "skim run 1"), ("with-quotegate+skim (run 2)", "skim run 2"),
           ("claude+grep, no local models", "grep run 1"),
           ("claude+grep, no local models (run 2)", "grep run 2"),
           ("with-quotegate+mechanical skim", "mechanical skim")]
V1_ARMS = [("claude-only", "Claude alone"), ("with-quotegate", "quotegate"),
           ("with-quotegate+skim", "skim")]
for corpus, arms, where in ((v2, V2_ARMS, "v2"), (v1, V1_ARMS, "v1")):
    for name, label in arms:
        tok, ok = arm(corpus, name)
        claim(results, "%s,%03d" % (tok // 1000, tok % 1000), "%s %s tokens" % (where, label))
        claim(results, "| %d |" % ok, "%s %s correct" % (where, label))
for needle in ("64/64 at 249k", "64/64 at 106-110k", "62-63/64 at 78-89k", "60/64 at 230k", "63/64 at 85k"):
    claim(readme, needle, "README v1/v2 row")

v3 = ROOT / "corpus" / "v3"
for name, label in [("claude-only", "Claude alone"),
                    ("with-quotegate+skim (run 1)", "skim run 1"),
                    ("with-quotegate+skim (run 2)", "skim run 2"),
                    ("claude+grep, no local models", "grep run 1"),
                    ("claude+grep, no local models (run 2)", "grep run 2")]:
    tok, ok = arm(v3, name)
    claim(results, "%s,%03d" % (tok // 1000, tok % 1000), "v3 %s tokens" % label)
    claim(results, "| %d |" % ok, "v3 %s correct" % label)
for needle in ("63/64 at 217k", "61-62/64 at 117-122k", "55-56/64 at 82-88k"):
    claim(readme, needle, "README v3 row")

v4 = ROOT / "corpus" / "v4"
for name, label in [("claude+grep, plain facts", "grep"), ("claude+grep, facts + expansion", "grep+exp"),
                    ("with-quotegate+skim (base sweep, plain facts)", "C"),
                    ("with-quotegate+skim (V4 sweep, facts + expansion)", "C+"),
                    ("with-quotegate+skim (EXP sweep, facts + expansion)", "C-exp")]:
    tok, ok = arm(v4, name)
    claim(results, "%s,%03d" % (tok // 1000, tok % 1000), "v4 %s tokens" % label)
    claim(results, "| %d |" % ok, "v4 %s correct" % label)
for needle in ("62/64 at 168k", "56/64 at 86k", "from 35.6%\nto 25.0%", "from 57 to 59 of 64"):
    claim(readme.replace("\n", " "), needle.replace("\n", " "), "README v4")

# every headline arm ran on the model the texts name
for f in sorted(glob.glob(str(ROOT / "corpus" / "**" / "savings" / "arm_*.json"), recursive=True)):
    checks += 1
    if json.load(open(f)).get("model") != "claude-opus-5-5":
        fails.append("%s: headline arm not on claude-opus-5-5" % f)

# the corpora are what the texts say they are
for corpus, n_stale, where in ((ROOT / "corpus", 32, "v1"), (v2, 32, "v2"), (v3, 32, "v3"), (v4, 31, "v4")):
    key = json.load(open(corpus / "key.json"))["docs"]
    stale = sum(1 for d in key.values() if any(not c["corrected_in_doc"] for c in d))
    checks += 1
    if stale != n_stale:
        fails.append("%s: %d docs with an uncorrected stale claim, texts say %d" % (where, stale, n_stale))

# tests and structure still pass
for cmd in ([sys.executable, "-m", "pytest", "-q"],
            [sys.executable, str(ROOT / "corpus/verify_corpus.py"), "--corpus", str(ROOT / "corpus"), "--structure-only"],
            [sys.executable, str(ROOT / "corpus/verify_corpus.py"), "--corpus", str(v2), "--structure-only"],
            [sys.executable, str(ROOT / "corpus/verify_corpus.py"), "--corpus", str(v3), "--structure-only"],
            [sys.executable, str(ROOT / "corpus/verify_corpus.py"), "--corpus", str(v4), "--structure-only"]):
    checks += 1
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fails.append("command failed: %s" % " ".join(cmd[-3:]))

print("%d claims checked, %d failures" % (checks, len(fails)))
for f in fails:
    print("  FAIL " + f)
sys.exit(1 if fails else 0)
