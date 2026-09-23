"""The quote gate is the whole safety argument, so every rule it enforces has a
test that would FAIL if the rule were removed (the mutations)."""
import math

from quotegate.gate import MIN_QUOTE, norm, same_place, spans, validate, wilson

SRC = ("The bot is STOPPED, DISABLED, and the strategy it would trade\n"
       "is BENCHED. Those are four separate facts.")
MD = "the strategy it would trade is **BENCHED** (`ops/bench.py`)."


def ok(quote, src=SRC):
    return validate({"quote": quote}, src)[0]


# --- what passes -------------------------------------------------------------

def test_verbatim_quote_passes():
    assert ok("the strategy it would trade")


def test_quote_reflowed_across_a_newline_passes():
    assert ok("the strategy it would trade is BENCHED")


def test_dropped_markdown_emphasis_passes():
    # Models drop ** and backticks when quoting; 9 of one run's 15 gate
    # failures were word-for-word exact apart from emphasis.
    assert ok("trade is BENCHED (ops/bench.py)", MD)


# --- the mutations: each must be rejected -------------------------------------

def test_invented_quote_is_rejected():
    assert not ok("the strategy it would trade is LIVE")


def test_plausible_paraphrase_is_rejected():
    assert not ok("the bot is stopped and disabled")


def test_case_is_not_normalised():
    assert not ok("is benched. Those are four")


def test_dropping_emphasis_does_not_license_changing_a_word():
    assert not ok("trade is UNBENCHED (ops/bench.py)", MD)


def test_dropping_emphasis_does_not_license_changing_case():
    assert not ok("trade is benched (ops/bench.py)", MD)


def test_too_short_quote_is_rejected():
    # "STOPPED" IS verbatim in the source, so only the length floor can reject
    # it. (An earlier version used "the bot", which the case rule rejected -
    # the test passed with the floor removed and proved nothing.)
    assert MIN_QUOTE >= 12
    assert "STOPPED" in SRC
    assert not ok("STOPPED")


def test_missing_quote_is_rejected():
    assert not validate({}, SRC)[0]


def test_non_object_answer_is_rejected():
    assert not validate("BENCHED", SRC)[0]
    assert not validate(None, SRC)[0]


def test_rejection_reason_names_the_failure():
    assert "verbatim" in validate({"quote": "nothing like this at all"}, SRC)[1]
    assert "shorter" in validate({"quote": "x"}, SRC)[1]


# --- position matching ----------------------------------------------------------

def test_same_wording_at_two_places_is_two_claims():
    # Two different sentences can share wording; matching by wording once
    # merged them and denied credit for the second (found 2026-09-21).
    doc = ("Early: backups A and B remain unused after this document. "
           + "filler " * 300 + "Late: Reserve untouched: backups A and B remain unused.")
    early, late = "backups A and B remain unused after this document", "Reserve untouched: backups A and B remain unused"
    assert not same_place(early, late, doc)
    assert same_place(late, "Reserve untouched: backups A and B", doc)


def test_short_overlap_on_the_same_line_is_one_claim():
    # "bot STOPPED, DISABLED." vs the key's "STOPPED, DISABLED. No trade ever
    # booked." share only 18 chars of wording but sit on one line.
    doc = "state:\nbot        STOPPED, DISABLED. No trade ever booked.\nnext line"
    assert same_place("bot        STOPPED, DISABLED.", "STOPPED, DISABLED. No trade ever booked.", doc)


def test_quote_not_in_source_matches_nothing():
    assert spans("not in the document at all", SRC) == []
    assert not same_place("not in the document at all", "STOPPED, DISABLED", SRC)


def test_norm_collapses_whitespace_and_emphasis_only():
    assert norm("  **a**\n\t`b`   c ") == "a b c"
    assert norm("Case Stays") == "Case Stays"


# --- intervals -----------------------------------------------------------------

def test_wilson_interval_is_sane():
    lo, hi = wilson(60, 64)
    assert 0.84 < lo < 0.86 and 0.97 < hi < 0.99      # 85-98% in RESULTS.md
    assert wilson(0, 0) == (0.0, 0.0)
    lo, hi = wilson(0, 20)
    assert lo == 0.0 and 0.1 < hi < 0.2
    lo, hi = wilson(20, 20)
    assert math.isclose(hi, 1.0) and lo > 0.8
