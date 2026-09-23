"""Expand the facts into what an out-of-date document might say - measured on corpus v4.

    quotegate expand --facts FACTS.txt                      # print the prompt to answer
    quotegate expand --attach EXPANSION.txt --items items.jsonl --out items_exp.jsonl

A fact like "output is stable within a calendar year" does not share a word with
the stale sentence "expect every upgrade to reformat your code". Local models
and grep both miss that kind of consequence. Writing out, once per fact list,
what a document written before the change might still say, show or tell the
reader to do - and giving that to the local models after the facts - cut their
errors on corpus v4 from 35.6% to 25.0% (RESULTS.md).

The expansion is written by Claude (or a subagent), from the facts ALONE: the
first form prints the prompt that was measured. The second form appends the
answer to every item's facts under the heading the measured sweep used.
"""
import json

PROMPT = """Below are the CURRENT facts of a project. Each fact records something that
changed at some point (a version floor, a removed option, a changed default, a
moved command).

For EVERY fact, write 2-5 short lines describing what a document written BEFORE
the change might still say, show or tell the reader to do - things that are
wrong NOW because of the fact. Cover the indirect forms, not only the literal
old statement:
 - consequences the reader is told to expect ("you will need to...", "this will
   fail unless...", "expect X to happen on every upgrade") that only hold under
   the old behaviour;
 - instructions or steps that presuppose the old behaviour (a command that no
   longer exists, a setup step that is no longer needed or no longer works);
 - code or config that only works under the old behaviour (removed arguments,
   keys, section names, file names, old version pins or interpreter names);
 - advice that follows from the old state (e.g. keeping code compatible with a
   version that is no longer supported).
Each line should be concrete enough that a reader scanning a document would
recognise the pattern, and short (under 25 words). Do not repeat the fact
itself. Write the lines as a plain list, one "- " line each.

Work from the facts alone - do not read the documents being audited.

FACTS:
{facts}
"""

HEADING = ("WHAT AN OUT-OF-DATE DOCUMENT MIGHT STILL SAY, SHOW OR TELL THE READER TO DO\n"
           "(examples of patterns that would be wrong now - not facts, and not an exhaustive list):")


def prompt(facts_text):
    return PROMPT.format(facts=facts_text.strip())


def attach(expansion_text, item):
    """The item with the expansion appended to its facts, as the EXP sweep saw it."""
    lines = [l.strip() for l in expansion_text.splitlines() if l.strip().startswith("- ")]
    if not lines:
        raise ValueError("the expansion has no '- ' lines")
    facts = (item.get("facts") or "").rstrip()
    return dict(item, facts=facts + "\n\n" + HEADING + "\n" + "\n".join(lines))


def attach_file(expansion_path, items_path, out_path):
    exp = open(expansion_path).read()
    n = 0
    with open(out_path, "w") as fh:
        for line in open(items_path):
            if line.strip():
                fh.write(json.dumps(attach(exp, json.loads(line))) + "\n")
                n += 1
    return n
