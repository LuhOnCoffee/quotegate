"""Fan one narrow question over many items, and keep only what the gate can prove.

Each item is {"id", "text", optional "facts", ...}. The prompt template uses
{{TEXT}} for the item's document and {{FACTS}} for per-item context. Facts are
deliberately kept OUT of the text the quote is checked against, so a model
cannot pass the gate by quoting the facts back.

Every item produces exactly one record, whatever happened:
  kept     the answer parsed and its quote passed the gate
  dropped  the answer parsed but failed the gate (reason says why)
  error    no usable answer: transport failure, truncation, runaway reasoning,
           answer in the wrong channel - never counted as an answer
A high drop rate is information; zero drops on a hard task is suspicious.
"""
import json
from dataclasses import dataclass

from .backends import BackendError, first_json_object
from .gate import MIN_QUOTE, validate

DEFAULT_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "quote": {"type": "string", "minLength": MIN_QUOTE},
        "why": {"type": "string"},
    },
    "required": ["found", "quote", "why"],
}


def fill(template, item):
    return template.replace("{{FACTS}}", item.get("facts", "")).replace("{{TEXT}}", item["text"])


@dataclass
class Tally:
    kept: int = 0
    dropped: int = 0
    errors: int = 0

    def line(self, n):
        return "in %d | kept %d | dropped %d | errors %d" % (n, self.kept, self.dropped, self.errors)


def ask_one(backend, model, template, item, schema=DEFAULT_SCHEMA, think=None, num_predict=4096):
    """One item -> one record dict (never raises for a model/backend failure)."""
    rec = {"id": item.get("id"), "model": model}
    try:
        reply = backend.ask(model, fill(template, item), schema=schema, think=think,
                            num_predict=num_predict)
    except BackendError as e:
        rec.update(status="error", error="%s: %s" % (type(e).__name__, e),
                   meta=getattr(e, "meta", {}))
        return rec
    rec["meta"] = reply.meta
    try:
        answer = json.loads(reply.content)
    except ValueError:
        answer = first_json_object(reply.content)
    if answer is None:
        rec.update(status="dropped", reason="no JSON object in the reply",
                   answer={"_unparsed": reply.content[:500]})
        return rec
    good, why = validate(answer, item["text"])
    rec.update(status="kept" if good else "dropped", reason=why, answer=answer)
    return rec


def run(backend, model, template, items, out_path, **kw):
    """Run every item; write one JSONL record per item; return the Tally."""
    t = Tally()
    with open(out_path, "w", buffering=1) as fh:
        for item in items:
            rec = ask_one(backend, model, template, item, **kw)
            if rec["status"] == "kept":
                t.kept += 1
            elif rec["status"] == "dropped":
                t.dropped += 1
            else:
                t.errors += 1
            fh.write(json.dumps(rec) + "\n")
    return t
