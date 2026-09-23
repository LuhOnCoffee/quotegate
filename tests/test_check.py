"""quotegate check - the gate applied to a finished report.

The main case is the one measured on the benchmark: right quotes, each filed
under the document before its own (corpus v1, Opus 5.5, arm A, 60/64)."""
import json

from quotegate.check import MISFILED, NOT_HERE, OK, SHORT, check, load_report, render
from quotegate.cli import main

TEXTS = {
    "black-d05": "Black is a formatter. Nothing stale in this one at all.",
    "black-d06": "Currently the runtime requires Python 3.6-3.10.",
    "black-d07": "It can be installed with pip. It requires Python 3.6.2+ to\nrun.",
    "black-d08": "_Black_ runs on Python 3.8 and newer.",
}
SHIFTED = [  # what the report said: every quote one document early
    {"id": "black-d05", "found": True, "quote": "Currently the runtime requires Python 3.6-3.10."},
    {"id": "black-d06", "found": True, "quote": "It requires Python 3.6.2+ to run."},
    {"id": "black-d07", "found": True, "quote": "_Black_ runs on Python 3.8 and newer."},
    {"id": "black-d08", "found": False, "quote": ""},
]


def test_a_shifted_report_is_named_misfiled_with_the_right_home():
    res, _ = check(SHIFTED, TEXTS)
    assert [(r["id"], r["status"], r["elsewhere"]) for r in res] == [
        ("black-d05", MISFILED, ["black-d06"]),
        ("black-d06", MISFILED, ["black-d07"]),     # across a line break: whitespace is normalised
        ("black-d07", MISFILED, ["black-d08"]),
    ]


def test_a_correct_report_passes():
    right = [{"id": "black-d06", "found": True, "quote": "the runtime requires Python 3.6-3.10"},
             {"id": "black-d08", "found": True, "quote": "*Black* runs on Python 3.8 and newer."}]
    res, problems = check(right, TEXTS)
    assert [r["status"] for r in res] == [OK, OK]
    assert problems == ["never reported: black-d05, black-d07"]


def test_an_invented_quote_is_not_verbatim_anywhere():
    res, _ = check([{"id": "black-d06", "found": True, "quote": "Black requires Python 3.6 or newer."}], TEXTS)
    assert res[0]["status"] == NOT_HERE and res[0]["elsewhere"] == []


def test_a_too_short_quote_is_refused_even_when_present():
    # "[pytest]" pointed at the right line on the benchmark, but 8 chars proves nothing
    res, _ = check([{"id": "black-d08", "found": True, "quote": "Python 3.8"}], TEXTS)
    assert res[0]["status"] == SHORT


def test_duplicates_are_reported():
    _, problems = check(SHIFTED + [SHIFTED[0]], TEXTS)
    assert any("more than once: black-d05" in p for p in problems)


def test_report_formats(tmp_path):
    for body in (json.dumps({"docs": SHIFTED}), json.dumps(SHIFTED),
                 "\n".join(json.dumps(e) for e in SHIFTED)):
        f = tmp_path / "r"
        f.write_text(body)
        assert len(load_report(f)) == 4


def test_render_says_where_to_move_it():
    res, problems = check(SHIFTED, TEXTS)
    out = "\n".join(render(res, problems))
    assert "MISFILED     black-d05: the quote is in black-d06" in out


def test_cli_exit_code(tmp_path, capsys):
    items = tmp_path / "items.jsonl"
    items.write_text("\n".join(json.dumps({"id": k, "text": v}) for k, v in TEXTS.items()))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(SHIFTED))
    assert main(["check", "--report", str(bad), "--items", str(items)]) == 1
    good = tmp_path / "good.json"
    good.write_text(json.dumps([{"id": k, "found": False, "quote": ""} for k in TEXTS]))
    assert main(["check", "--report", str(good), "--items", str(items)]) == 0
    docs = tmp_path / "docs"
    docs.mkdir()
    for k, v in TEXTS.items():
        (docs / (k + ".txt")).write_text(v)
    assert main(["check", "--report", str(bad), "--docs", str(docs)]) == 1
