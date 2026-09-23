"""`quotegate skim`: the lines of each document worth a human (or Claude) look,
found by terms derived MECHANICALLY from the facts - so the skim does not
depend on which search terms a reader happens to pick.

Measured on corpus v2 (2026-09-22): Claude choosing its own grep terms missed
staleness written in other words - `tox -e py39` when the fact says "3.10 or
newer" - in both runs, and whether it caught a redirect-default claim depended
on whether it thought to search "redirect". This module:

  - takes every version number in the facts and adds the OLDER versions a
    stale document would name instead, in the spellings documentation uses:
    "3.9", "py39", "py3.9", "cp39" (a fact "3.10 or newer" yields 3.5..3.9 and
    2.7 variants);
  - takes code-like tokens from the facts (backticked text, dotted/dashed/
    underscored identifiers, --flags, ALL_CAPS names, URLs and hosts);
  - takes content words of 6+ letters, stemmed crudely, so "redirects" also
    matches "follow_redirects";
and prints each matching line with a little context.
"""
import re

STOP = {"version", "versions", "python", "supported", "support", "supports", "current",
        "currently", "longer", "anymore", "instead", "default", "defaults", "project",
        "projects", "documentation", "official", "officially", "should", "because",
        "through", "installed", "install", "installing", "available", "separate",
        "removed", "deprecated", "newer", "older", "requires", "require", "required",
        "running", "command", "commands", "option", "options"}
_VER = re.compile(r"\b(\d)\.(\d{1,2})\b")
_CODE = re.compile(r"`([^`]+)`|(--?[A-Za-z][\w-]+)|\b([A-Z][A-Z0-9_]{2,})\b|"
                   r"\b([\w.-]+\.(?:org|com|io|py|toml|cfg|ini|json|txt))\b|"
                   r"\b(\w+(?:[_.-]\w+)+)\b")
_WORD = re.compile(r"[A-Za-z]{6,}")


def older_versions(major, minor):
    """Versions older than major.minor that stale docs typically name."""
    out = set()
    if major == 3:
        for m in range(max(0, minor - 6), minor):
            out.add((3, m))
        out.add((2, 7))
    return out


def version_spellings(major, minor):
    v = "%d.%d" % (major, minor)
    return {v, "py%d%d" % (major, minor), "py%d.%d" % (major, minor),
            "cp%d%d" % (major, minor), "python%d.%d" % (major, minor)}


def terms_from_facts(facts_text):
    terms = set()
    for mj, mn in _VER.findall(facts_text):
        mj, mn = int(mj), int(mn)
        for a, b in older_versions(mj, mn):
            terms |= version_spellings(a, b)
    for m in _CODE.finditer(facts_text):
        tok = next(g for g in m.groups() if g)
        tok = tok.strip().strip(".,;:()")
        if len(tok) >= 3 and not _VER.fullmatch(tok):
            terms.add(tok)
    for w in _WORD.findall(facts_text):
        w = w.lower()
        if w not in STOP:
            terms.add(w[:-1] if w.endswith("s") else w)   # crude stem: redirects -> redirect
    return sorted(terms, key=str.lower)


def select_terms(facts_text, sibling_texts, max_df=0.5):
    """Terms for one group of documents sharing the same facts.

    Versions and code-like tokens are always kept. Plain words are kept only
    if they appear in at most `max_df` of the sibling documents: a word in most
    of a project's docs ("client", "configuration") matches everywhere and
    only adds noise. max_df 0.5 was CHOSEN ON corpus v2 (showed all 3 misses
    the local models shared, at 21% of the "none" docs' lines) - it is tuned on
    that corpus, not validated on a held-out one."""
    terms = terms_from_facts(facts_text)
    word = re.compile(r"[a-z]{5,}")
    low = [s.lower() for s in sibling_texts] or [""]
    keep = []
    for t in terms:
        if word.fullmatch(t):
            if sum(t in s for s in low) / len(low) > max_df:
                continue
        keep.append(t)
    return keep


def skim(text, terms, context=2):
    """[(first_line_no, block_text, matched_terms)] for lines matching any term."""
    lines = text.splitlines()
    low = [l.lower() for l in lines]
    hits = {}
    for i, l in enumerate(low):
        found = [t for t in terms if t.lower() in l]
        if found:
            hits[i] = found
    blocks, done = [], set()
    for i in sorted(hits):
        if i in done:
            continue
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        done.update(range(lo, hi))
        matched = sorted({t for j in range(lo, hi) for t in hits.get(j, [])})
        blocks.append((lo + 1, "\n".join(lines[lo:hi]), matched))
    return blocks
