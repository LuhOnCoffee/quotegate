"""The worker and the Ollama defences, tested against a fake backend - no GPU.

Each defence is tested with the exact numbers of the failure it was built for,
so the test fails if the defence is removed."""
import json

import pytest

from quotegate.backends import (AnswerInThinking, BackendError, Ollama, Reply, Runaway,
                                Truncated, first_json_object, truncated)
from quotegate.worker import ask_one, fill, run

DOC = "Requests officially supports Python 2.7 and 3.4+. It runs great on PyPy."
ITEM = {"id": "d1", "text": DOC, "facts": "- Requests supports Python 3.10+."}
TEMPLATE = "FACTS:\n{{FACTS}}\nDOC:\n{{TEXT}}"


class Fake:
    """Returns a scripted Reply or raises a scripted error, recording prompts."""
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.prompts = reply, error, []

    def ask(self, model, prompt, schema=None, think=None, num_predict=4096):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.reply


def reply(obj, **meta):
    return Reply(json.dumps(obj) if not isinstance(obj, str) else obj, meta=meta)


# --- truncation guard: measured 2026-09-21 --------------------------------------

def test_full_read_is_not_truncated():
    assert not truncated(12789, 4167)          # 3.07 chars/token


def test_default_context_cut_is_truncated():
    assert truncated(12789, 2050)              # Ollama default: ~half of 4096


def test_num_ctx_2048_cut_is_truncated():
    assert truncated(12789, 1026)              # 12.5 chars/token


def test_check_refuses_a_truncated_reply():
    r = Reply('{"found": false, "quote": "x"}', meta={"prompt_eval_count": 1026, "done_reason": "stop"})
    with pytest.raises(Truncated):
        Ollama.check(r, "x" * 12789, used_schema=True)


# --- answer in the wrong channel (qwen3.5, 20 of 20 documents) ------------------

def test_answer_in_thinking_is_named():
    r = Reply("", thinking='{"found": true, "quote": "supports Python 2.7", "why": "x"}',
              meta={"prompt_eval_count": 4000, "done_reason": "stop"})
    with pytest.raises(AnswerInThinking):
        Ollama.check(r, "x" * 12000, used_schema=True)


def test_runaway_with_a_json_fragment_is_a_runaway_not_misrouting():
    # A run that hit the cap mid-thought can contain {...}; that is a runaway.
    r = Reply("", thinking='maybe {"found": true} ... still thinking',
              meta={"prompt_eval_count": 4000, "done_reason": "length", "eval_count": 8192})
    with pytest.raises(Runaway):
        Ollama.check(r, "x" * 12000, used_schema=True)


def test_a_good_reply_passes_check():
    r = Reply('{"found": false, "quote": "It runs great on PyPy.", "why": ""}',
              meta={"prompt_eval_count": 4000, "done_reason": "stop"})
    assert Ollama.check(r, "x" * 12000, used_schema=True) is r


def test_bare_host_gets_a_scheme():
    assert Ollama("127.0.0.1:11434").host == "http://127.0.0.1:11434"
    assert Ollama("http://h:1/").host == "http://h:1"


# --- the worker ----------------------------------------------------------------

def test_facts_go_in_the_prompt_but_not_in_the_checked_text():
    fake = Fake(reply({"found": True, "quote": "Requests supports Python 3.10+.", "why": "x"}))
    rec = ask_one(fake, "m", TEMPLATE, ITEM)
    assert "Requests supports Python 3.10+." in fake.prompts[0]
    assert rec["status"] == "dropped"          # quoting the FACTS back fails the gate


def test_verbatim_finding_is_kept():
    rec = ask_one(Fake(reply({"found": True, "quote": "officially supports Python 2.7 and 3.4+", "why": "x"})),
                  "m", TEMPLATE, ITEM)
    assert rec["status"] == "kept"


def test_fabricated_quote_is_dropped_with_reason():
    rec = ask_one(Fake(reply({"found": True, "quote": "Requests supports Python 3.6 and newer", "why": "x"})),
                  "m", TEMPLATE, ITEM)
    assert rec["status"] == "dropped" and "verbatim" in rec["reason"]


def test_prose_wrapped_json_is_extracted():
    text = 'Here you go:\n```json\n{"found": true, "quote": "officially supports Python 2.7", "why": "x"}\n```'
    rec = ask_one(Fake(Reply(text)), "m", TEMPLATE, ITEM)
    assert rec["status"] == "kept"


def test_reply_with_no_json_is_dropped_not_guessed():
    rec = ask_one(Fake(Reply("I could not find anything.")), "m", TEMPLATE, ITEM)
    assert rec["status"] == "dropped" and "_unparsed" in rec["answer"]


def test_backend_failure_is_an_error_never_an_answer():
    rec = ask_one(Fake(error=Runaway("hit num_predict")), "m", TEMPLATE, ITEM)
    assert rec["status"] == "error" and "Runaway" in rec["error"]


def test_run_writes_one_record_per_item_and_counts(tmp_path):
    items = [ITEM, {**ITEM, "id": "d2"}, {**ITEM, "id": "d3"}]

    class Script:
        def __init__(self):
            self.i = 0

        def ask(self, model, prompt, **kw):
            self.i += 1
            if self.i == 1:
                return reply({"found": True, "quote": "It runs great on PyPy.", "why": ""})
            if self.i == 2:
                return reply({"found": True, "quote": "invented sentence here", "why": ""})
            raise BackendError("down")
    out = tmp_path / "raw.jsonl"
    t = run(Script(), "m", TEMPLATE, items, out)
    assert (t.kept, t.dropped, t.errors) == (1, 1, 1)
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    assert [r["status"] for r in recs] == ["kept", "dropped", "error"]


def test_first_json_object_skips_a_broken_brace():
    assert first_json_object('bad { not json } then {"a": 1}') == {"a": 1}
    assert first_json_object("no object") is None


def test_fill_substitutes_both_placeholders():
    assert fill("{{FACTS}}|{{TEXT}}", {"text": "T", "facts": "F"}) == "F|T"
    assert fill("{{FACTS}}|{{TEXT}}", {"text": "T"}) == "|T"


# --- the OpenAI-compatible backend ------------------------------------------------

class FakeOAI:
    """An OpenAI-compatible server whose one response is scripted."""
    def __init__(self, payload):
        self.payload, self.sent = payload, None

    def post(self, body):
        self.sent = body
        return self.payload


def oai(payload):
    from quotegate.backends import OpenAICompat
    b = OpenAICompat("127.0.0.1:1")
    f = FakeOAI(payload)
    b._post = f.post
    return b, f


def resp(content="", reasoning="", finish="stop", ptok=4000, ctok=50):
    return {"choices": [{"finish_reason": finish,
                         "message": {"content": content, "reasoning": reasoning}}],
            "usage": {"prompt_tokens": ptok, "completion_tokens": ctok}}


def test_openai_backend_returns_a_reply_and_sends_a_json_schema():
    from quotegate.worker import DEFAULT_SCHEMA
    b, f = oai(resp('{"found": false, "quote": "x"}'))
    r = b.ask("m", "x" * 12000, schema=DEFAULT_SCHEMA)
    assert r.content.startswith("{")
    assert f.sent["response_format"]["type"] == "json_schema"
    assert f.sent["temperature"] == 0


def test_openai_backend_refuses_a_truncated_prompt():
    b, _ = oai(resp('{"found": false, "quote": "x"}', ptok=1026))
    with pytest.raises(Truncated):
        b.ask("m", "x" * 12789)


def test_openai_backend_names_a_runaway_and_an_answer_in_reasoning():
    b, _ = oai(resp("", reasoning="thinking...", finish="length", ctok=4096))
    with pytest.raises(Runaway):
        b.ask("m", "x" * 12000)
    b2, _ = oai(resp("", reasoning='{"found": true, "quote": "aaaaaaaaaaaaaaaa"}', finish="stop"))
    from quotegate.worker import DEFAULT_SCHEMA
    with pytest.raises(AnswerInThinking):
        b2.ask("m", "x" * 12000, schema=DEFAULT_SCHEMA)


def test_openai_backend_passes_reasoning_effort_only_for_levels():
    b, f = oai(resp('{"found": false, "quote": "x"}'))
    b.ask("m", "x" * 12000, think="low")
    assert f.sent["reasoning_effort"] == "low"
    b2, f2 = oai(resp('{"found": false, "quote": "x"}'))
    b2.ask("m", "x" * 12000, think=False)
    assert "reasoning_effort" not in f2.sent
