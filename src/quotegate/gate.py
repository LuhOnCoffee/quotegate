"""The quote gate: the only thing standing between a local model's guess and the record.

An answer is kept only if its `quote` is literally in the source after
normalising whitespace and markdown emphasis (`*`, `_`, backtick). Nothing else
is normalised: a changed word or changed case is a failed quote. Case matters
because "BENCHED" and "benched" can be different claims.
"""
import math
import re

MIN_QUOTE = 12                      # shorter than this and any file "contains" it
_EMPHASIS = re.compile(r"[*_`]")


def norm(s):
    """Emphasis first, then whitespace, so "**a** b" and "a b" meet."""
    return re.sub(r"\s+", " ", _EMPHASIS.sub("", s or "")).strip()


def validate(answer, source):
    """(ok, reason) for one answer dict against its source text."""
    if not isinstance(answer, dict):
        return False, "not an object"
    q = answer.get("quote")
    if not isinstance(q, str) or len(norm(q)) < MIN_QUOTE:
        return False, "quote missing or shorter than %d chars" % MIN_QUOTE
    if norm(q) not in norm(source):
        return False, "quote is not verbatim in the source"
    return True, ""


def spans(quote, source):
    """Every [start, end) where the normalised quote sits in the normalised source."""
    q, s = norm(quote), norm(source)
    out, i = [], (s.find(q) if q else -1)
    while i >= 0:
        out.append((i, i + len(q)))
        i = s.find(q, i + 1)
    return out


def same_place(a, b, source, min_shared=8):
    """True when two quotes cover overlapping text IN THE DOCUMENT.

    Compared by position, not wording: two different sentences can share
    wording (two "remain unspent" claims 8,000 chars apart), and two quotes of
    one sentence can share little (a model's "bot STOPPED, DISABLED." vs a
    key's "STOPPED, DISABLED. No trade ever booked.")."""
    sa, sb = spans(a, source), spans(b, source)
    return any(min(e1, e2) - max(s1, s2) >= min_shared
               for s1, e1 in sa for s2, e2 in sb)


def wilson(k, n, z=1.96):
    """95% Wilson interval for k of n - honest at small n."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
