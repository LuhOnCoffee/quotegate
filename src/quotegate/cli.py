"""quotegate command line.

    quotegate run    --model M --items items.jsonl --prompt p.txt --out raw.jsonl
    quotegate doctor --model M [--host 127.0.0.1:11434]
    quotegate sweep  --roster r.toml --items items.jsonl --prompt careful.txt
                     [--eager-prompt eager.txt] (--budget-min N | --tier 1|2|3) --out out.jsonl [--resume]
    quotegate calibrate --roster r.toml --items sample.jsonl --prompt p.txt [--n 5] --write r2.toml
    quotegate check  --report report.json (--items items.jsonl | --docs DIR)
    quotegate expand --facts FACTS.txt | --attach EXPANSION.txt --items items.jsonl --out out.jsonl
"""
import argparse
import json
import sys

from . import __version__


def _think(v):
    return {"on": True, "off": False, "auto": None}.get(v, v)


def cmd_run(a):
    from .backends import Ollama, OpenAICompat
    from .worker import DEFAULT_SCHEMA, run
    items = [json.loads(l) for l in open(a.items) if l.strip()]
    schema = json.load(open(a.schema)) if a.schema else DEFAULT_SCHEMA
    backend = (OpenAICompat(a.host) if a.backend == "openai"
               else Ollama(a.host, num_ctx=a.num_ctx))
    t = run(backend, a.model, open(a.prompt).read(), items, a.out,
            schema=schema, think=_think(a.think), num_predict=a.num_predict)
    print(t.line(len(items)))
    print("-> %s  (every item, with status; read the kept ones before acting)" % a.out)
    return 0 if t.kept else 1


def cmd_sweep(a):
    from . import config
    from .sweep import sweep
    roster = config.load(a.roster)
    items = [json.loads(l) for l in open(a.items) if l.strip()]
    schema = json.load(open(a.schema)) if a.schema else None
    kw = {"schema": schema} if schema else {}
    prior = {}
    if a.resume:
        for line in open(a.out + ".votes.jsonl"):
            if line.strip():
                r = json.loads(line)
                prior.setdefault(r["id"], {})[r["role"]] = r
    with open(a.out + ".votes.jsonl", "a" if a.resume else "w", buffering=1) as raw:
        res = sweep(roster, items, open(a.prompt).read(), prior=prior,
                    budget_s=a.budget_min * 60 if a.budget_min else float("inf"),
                    tier=a.tier, eager_prompt=open(a.eager_prompt).read() if a.eager_prompt else None,
                    raw_fh=raw, on_log=lambda line: print(line, flush=True), **kw)
    with open(a.out, "w") as fh:
        for it in items:
            d = res.decisions.get(it["id"])
            kind = "undecided" if d is None else ("finding" if d[0] == "find" else "none")
            fh.write(json.dumps({"id": it["id"], "decision": kind,
                                 "quote": d[1] if d and d[0] == "find" else None,
                                 "votes": {k: list(v) for k, v in res.votes[it["id"]].items()}}) + "\n")
    print("-> %s  (every vote: %s.votes.jsonl). Read every 'finding' and every "
          "'undecided' - agreement makes a finding likely, not proven." % (a.out, a.out))
    return 0


def cmd_check(a):
    from .check import check, load_docs, load_items, load_report, render
    texts = load_items(a.items) if a.items else load_docs(a.docs)
    results, problems = check(load_report(a.report), texts)
    for line in render(results, problems):
        print(line)
    return 0 if all(r["status"] == "ok" for r in results) and not problems else 1


def cmd_expand(a):
    from .expand import attach_file, prompt
    if a.facts:
        print(prompt(open(a.facts).read()))
        return 0
    if not (a.items and a.out):
        print("--attach needs --items and --out")
        return 2
    n = attach_file(a.attach, a.items, a.out)
    print("%d items -> %s (facts + expansion)" % (n, a.out))
    return 0


def cmd_calibrate(a):
    from . import config
    from .calibrate import time_model, to_toml
    roster = config.load(a.roster)
    items = [json.loads(l) for l in open(a.items) if l.strip()][:a.n]
    prompt = open(a.prompt).read()
    for m in roster.models.values():
        r = time_model(m, items, prompt)
        print("%-28s load %5.1f s   %s s per 1k chars   (%d items timed)"
              % (m.name, r["load_s"], r["s_per_kchar"], r["timed_items"]))
        m.load_s = r["load_s"]
        if r["s_per_kchar"] is not None:
            m.s_per_kchar = r["s_per_kchar"]
    with open(a.write, "w") as fh:
        fh.write(to_toml(roster))
    print("-> %s" % a.write)
    return 0


def cmd_skim(a):
    from .skim import select_terms, skim
    items = [json.loads(l) for l in open(a.items) if l.strip()]
    want = None
    if a.decisions:
        dec = {json.loads(l)["id"]: json.loads(l)["decision"] for l in open(a.decisions) if l.strip()}
        want = {k for k, v in dec.items() if v in a.only.split(",")}
    groups = {}
    for it in items:
        groups.setdefault(it.get("facts", ""), []).append(it)
    for facts, group in groups.items():
        for it in group:
            if want is not None and it["id"] not in want:
                continue
            terms = select_terms(facts, [g["text"] for g in group], a.max_df)
            blocks = skim(it["text"], terms, a.context)
            print("===== %s  (%d blocks)" % (it["id"], len(blocks)))
            for line_no, block, matched in blocks:
                print("--- line %d  [%s]" % (line_no, ", ".join(matched[:6])))
                print(block)
    return 0


def cmd_doctor(a):
    from .doctor import main
    return main(a.host, a.model)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quotegate", description=__doc__.split("\n")[0])
    ap.add_argument("--version", action="version", version="quotegate " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="one model over many items, every answer quote-gated")
    r.add_argument("--model", required=True)
    r.add_argument("--items", required=True, help='JSONL: {"id","text"[,"facts"]} per line')
    r.add_argument("--prompt", required=True, help="template with {{TEXT}} and optional {{FACTS}}")
    r.add_argument("--out", required=True)
    r.add_argument("--schema", help="JSON schema file (default: found/quote/why)")
    r.add_argument("--host", default="127.0.0.1:11434")
    r.add_argument("--backend", default="ollama", choices=["ollama", "openai"],
                   help="openai = any /v1/chat/completions server (llama.cpp, LM Studio, vLLM)")
    r.add_argument("--think", default="auto", choices=["auto", "on", "off", "low", "medium", "high"],
                   help="set it explicitly: model defaults differ and some lose the answer")
    r.add_argument("--num-ctx", type=int, default=16384, dest="num_ctx")
    r.add_argument("--num-predict", type=int, default=4096, dest="num_predict")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("sweep", help="budgeted multi-model sweep (tiers 1-3)")
    s.add_argument("--roster", required=True, help="roster TOML (see examples/)")
    s.add_argument("--items", required=True)
    s.add_argument("--prompt", required=True, help="the careful prompt")
    s.add_argument("--eager-prompt", dest="eager_prompt", help="needed for tier 3 (tripwire)")
    s.add_argument("--schema", help="JSON schema for the careful prompt")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--budget-min", type=float, dest="budget_min")
    g.add_argument("--tier", type=int, choices=[1, 2, 3])
    s.add_argument("--out", required=True)
    s.add_argument("--resume", action="store_true",
                   help="finish an earlier run of this sweep: reuse the answers in OUT.votes.jsonl, "
                        "ask only what is missing, append to it")
    s.set_defaults(fn=cmd_sweep)

    c = sub.add_parser("calibrate", help="time roster models on your items; write a calibrated roster")
    c.add_argument("--roster", required=True)
    c.add_argument("--items", required=True)
    c.add_argument("--prompt", required=True)
    c.add_argument("--n", type=int, default=8,
                   help="items to time; few items on cool cards under-estimate sustained speed")
    c.add_argument("--write", required=True, help="where to write the calibrated roster")
    c.set_defaults(fn=cmd_calibrate)

    k = sub.add_parser("skim", help="print only the lines worth a look, found by terms "
                                    "derived mechanically from each item's facts")
    k.add_argument("--items", required=True)
    k.add_argument("--decisions", help="a sweep's decisions file; skim only --only kinds")
    k.add_argument("--only", default="none", help="comma list: none,finding,undecided")
    k.add_argument("--max-df", type=float, default=0.5, dest="max_df")
    k.add_argument("--context", type=int, default=2)
    k.set_defaults(fn=cmd_skim)

    ck = sub.add_parser("check", help="check a finished report's quotes against the document each "
                                      "is filed under (catches misfiled and invented quotes)")
    ck.add_argument("--report", required=True, help="JSON list, {\"docs\": [...]}, or JSONL of {id, found, quote}")
    src = ck.add_mutually_exclusive_group(required=True)
    src.add_argument("--items", help="items.jsonl with id and text")
    src.add_argument("--docs", help="directory of documents; id = file name without extension")
    ck.set_defaults(fn=cmd_check)

    ex = sub.add_parser("expand", help="expand facts into what an out-of-date document might say "
                                       "(print the prompt, or attach the answer to items)")
    mode = ex.add_mutually_exclusive_group(required=True)
    mode.add_argument("--facts", help="facts file: print the expansion prompt for Claude to answer")
    mode.add_argument("--attach", help="the saved expansion ('- ' lines): append it to every item's facts")
    ex.add_argument("--items")
    ex.add_argument("--out")
    ex.set_defaults(fn=cmd_expand)

    d = sub.add_parser("doctor", help="measure Ollama's silent traps on this install")
    d.add_argument("--model", required=True)
    d.add_argument("--host", default="127.0.0.1:11434")
    d.set_defaults(fn=cmd_doctor)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
