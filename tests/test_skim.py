"""The mechanical skim: version spellings, code tokens, and noise control."""
from quotegate.skim import older_versions, select_terms, skim, terms_from_facts, version_spellings

FACTS = "- Black requires Python 3.10 or newer.\n- The `--experimental-string-processing` flag was removed."


def test_older_version_spellings_include_the_tox_form_grep_missed():
    terms = terms_from_facts(FACTS)
    assert {"3.9", "py39", "cp39", "2.7"} <= set(terms)       # the `tox -e py39` miss
    assert "3.10" not in terms                                # the CURRENT version is not a hit


def test_code_tokens_come_through():
    assert "--experimental-string-processing" in terms_from_facts(FACTS)


def test_skim_finds_the_py39_line_with_context():
    doc = "intro\nsetup\n(.venv)$ tox -e py39 # oldest supported\nafter\nend"
    blocks = skim(doc, terms_from_facts(FACTS), context=1)
    assert len(blocks) == 1 and "tox -e py39" in blocks[0][1]
    assert "py39" in blocks[0][2]


def test_common_words_are_dropped_as_noise():
    facts = "- HTTPX does not follow redirects by default; the client needs follow_redirects."
    siblings = ["the client does x"] * 9 + ["other"]
    terms = select_terms(facts, siblings, max_df=0.5)
    assert "client" not in terms                             # in 90% of sibling docs
    assert "follow_redirects" in terms                       # code tokens always kept


def test_versions_and_older_set():
    assert (3, 9) in older_versions(3, 10) and (2, 7) in older_versions(3, 10)
    assert "py3.9" in version_spellings(3, 9)
