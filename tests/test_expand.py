"""quotegate expand - the measured v4 expansion, as a reusable step."""
import json

import pytest

from quotegate.cli import main
from quotegate.expand import HEADING, attach, prompt

FACTS = "- Black is stable: output is stable within a calendar year.\n"
EXP = "Some preamble the model wrote.\n- Expect every upgrade to reformat your code.\n- Pin an exact Black version.\n"


def test_prompt_carries_the_facts_and_forbids_reading_the_documents():
    p = prompt(FACTS)
    assert FACTS.strip() in p and "do not read the documents" in p


def test_attach_appends_only_the_list_lines_under_the_measured_heading():
    it = attach(EXP, {"id": "d1", "text": "T", "facts": FACTS})
    assert it["facts"].startswith(FACTS.strip())
    assert HEADING in it["facts"] and "preamble" not in it["facts"]
    assert it["facts"].endswith("- Pin an exact Black version.")
    assert it["text"] == "T"


def test_attach_refuses_an_empty_expansion():
    with pytest.raises(ValueError):
        attach("no list here", {"id": "d1", "text": "T", "facts": FACTS})


def test_heading_matches_the_v4_exp_items():
    # the sweep that measured 25.0% saw exactly this heading
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    first = json.loads(open(root / "corpus/v4/items_exp.jsonl").readline())
    assert HEADING in first["facts"]


def test_cli(tmp_path, capsys):
    f = tmp_path / "FACTS.txt"; f.write_text(FACTS)
    assert main(["expand", "--facts", str(f)]) == 0
    assert "FACTS:" in capsys.readouterr().out
    e = tmp_path / "EXP.txt"; e.write_text(EXP)
    items = tmp_path / "items.jsonl"; items.write_text(json.dumps({"id": "d1", "text": "T", "facts": FACTS}) + "\n")
    out = tmp_path / "out.jsonl"
    assert main(["expand", "--attach", str(e), "--items", str(items), "--out", str(out)]) == 0
    assert HEADING in json.loads(out.read_text())["facts"]
