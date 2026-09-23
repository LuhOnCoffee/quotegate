"""The staged decision rules - one implementation, used by the live sweep and by
the offline simulator (bench/tiers.py), so the two cannot drift apart.

A vote is ("find", quote) | ("none", None) | ("drop", None). "drop" means the
model gave no usable answer: its quote failed the gate, or the request failed.

  first    answers every item
  second   answers every item; agreement decides
           (both "none", or both quote the same place in the document)
  tiebreak runs only where first and second disagree; sides with whichever it
           agrees with, else the item is undecided
  tripwire runs only on items decided "none"; if it finds anything the item
           becomes undecided - Claude reads it

Why a tripwire and not a fourth voter: the residual errors on both the private
corpus and public corpus v2 were misses every model SHARED, caused by one
prompt biasing all of them the same way. More voters with the same prompt
cannot out-vote that; a different prompt can.
"""
from .gate import same_place, validate

FIND, NONE, DROP = "find", "none", "drop"


def to_vote(record, text):
    """A worker record -> a vote. Anything not kept by the gate is a drop."""
    if record.get("status") != "kept":
        return (DROP, None)
    a = record.get("answer") or {}
    if not validate(a, text)[0]:
        return (DROP, None)
    return (FIND, a["quote"]) if a.get("found") else (NONE, None)


def agree(a, b, text):
    if a[0] == b[0] == NONE:
        return True
    return a[0] == b[0] == FIND and same_place(a[1], b[1], text)


def after_first(first):
    """Tier 1: take the first model's vote unless it was dropped."""
    return first if first[0] != DROP else None


def after_second(first, second, text):
    """Returns (decision or None, needs_tiebreak)."""
    if agree(first, second, text) and first[0] != DROP:
        return first, False
    return None, True


def after_tiebreak(first, second, tb, text):
    if tb[0] == DROP:
        return None
    for v in (first, second):
        if v[0] != DROP and agree(v, tb, text):
            return v
    return None


def needs_tripwire(decision):
    return decision is not None and decision[0] == NONE


def after_tripwire(decision, trip):
    """A tripwire that finds anything sends a 'none' back to Claude."""
    return None if trip[0] == FIND else decision
