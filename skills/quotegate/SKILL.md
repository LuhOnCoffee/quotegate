---
name: quotegate
description: Offload many repetitions of one narrow, quotable question over many documents (a doc audit, "does this file state X / contradict these facts? quote it", classification or extraction with evidence) to local Ollama models, where every answer must carry a verbatim quote that is checked against the source, and whatever the local models cannot settle comes back to you. Use when the work is high-volume and each answer can be CHECKED rather than believed. Do not use for judgement calls, adversarial review, summaries, or anything whose failure would be silent.
---

# quotegate: verified local offload

You orchestrate; local models do the reading. The point is to move work whose
answers are **checkable** onto hardware that costs nothing, and keep the work
whose answers are **believable-but-unverifiable** with you.

## The rule that makes it safe

Every local answer carries a quote, and the quote must be literally in the
document (whitespace and markdown emphasis normalised, nothing else). A quote
that is not there is discarded and counted. That turns a small model's worst
failure - a confident, invented citation - into lost yield instead of a wrong
record.

**It does not make the survivors right.** A real sentence can be quoted for a
wrong conclusion. Read every finding before acting on it.

## When NOT to bother

If the thing you are looking for is **findable by keyword** - the stale
version number, the removed flag's name, the old URL all appear literally -
just grep the documents yourself and read the matches. On the benchmark's
keyword-rich corpus that beat every quotegate arm on both accuracy and
tokens. quotegate earns its GPU time where the target is NOT keyword-findable:
implied claims, reworded versions (`tox -e py39` when the fact says "3.10 or
newer"), instructions that presuppose a removed feature. Grep alone missed
exactly those.

## When to use it, and when not

Use it for: one narrow question asked of many items, where the answer is a
quote plus a yes/no or a label - "does this doc still claim X?", "which of
these 200 files mention Y, quote it", "classify each item, with the evidence".

Never for: adversarial verification (the "try to refute this" pass), judgement
(should this be deleted, is this safe), summaries or drafts (nothing to quote),
or anything where a wrong answer looks exactly like a right one.

## Running it

The plugin runs the CLI from its own directory; nothing to install beyond
Python 3.11+ and a running Ollama:

    QG="env PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/src python3 -m quotegate"
    $QG doctor --model <model>          # once per install: checks two silent Ollama traps
    $QG run --model <model> --items items.jsonl --prompt careful.txt --think off --out raw.jsonl
    $QG sweep --roster roster.toml --items items.jsonl --prompt careful.txt \
              --eager-prompt eager.txt --budget-min 30 --out decisions.jsonl

`items.jsonl` has one `{"id": ..., "text": <the document>, "facts": <optional
context>}` per line. The prompt template uses `{{TEXT}}` and `{{FACTS}}`. Facts
are kept out of the text the quote is checked against, so a model cannot pass
by quoting them back.

**When the facts describe changes** (a removed option, a changed default, a
raised version floor), expand them first - it is the measured fix for the
hardest misses, consequences of old behaviour that share no words with the
facts ("expect every upgrade to reformat your code" against "output is stable
within a year"):

    $QG expand --facts FACTS.txt            # prints a prompt: answer it yourself, or
                                            # hand it to a subagent, from the facts alone
    # save the answer's "- " lines as EXPANSION.txt, then:
    $QG expand --attach EXPANSION.txt --items items.jsonl --out items_exp.jsonl

Sweep `items_exp.jsonl`, and add the expansion's distinctive words to the
skim terms for every "none". Measured on corpus v4 (consequence-heavy): the
local models' wrong verdicts fell from 35.6% to 25.0%, and quotegate + skim
went from 57 to 59 of 64 at the same Claude-token cost (one run each - a
direction, not proof). Write the expansion
from the facts only, never from the documents being audited. Do NOT ask the
local models to name the fact they found (tried on v4: told to write "none"
in a fact field, they wrote "none" into the quote too and lost the answer).

Calibrate on the job's own items, with the facts and expansion already in
them: a longer prompt is a slower prompt (a real job ran 1.7x the speed a
benchmark-calibrated roster predicted). The sweep re-plans from its measured
pace after each stage and says so in its log, but a good first plan picks the
right tier.

`sweep` needs a roster (models, hosts, roles). Start from
`${CLAUDE_PLUGIN_ROOT}/examples/roster-single-gpu.toml`; `quotegate calibrate`
times the models on the user's own items and writes a calibrated copy.

## Writing the prompts - this matters more than the model

Measured on a public, answer-keyed benchmark: a careful prompt more than
halved false findings for non-reasoning models (gemma4:12b: 16 -> 5 false
findings on 64 docs). Write TWO prompts:

- **careful** (start from `${CLAUDE_PLUGIN_ROOT}/bench/prompt_careful_v2.txt`):
  says exactly what counts and what does not, names the traps (dated history,
  conditionals, hypotheticals, paraphrases of the truth), says "many documents
  contain no such passage; saying so is a correct answer", and puts an
  `analysis` field FIRST in the schema (`bench/schema_careful.json`) so the
  model reasons before it commits.
- **eager** (`bench/prompt_eager.txt`): the same question, "find ONE". Used
  only as the tripwire in tier 3: it catches misses that every model shares
  because the careful prompt biased them all the same way.

## Choosing a tier

    tier 1  fast     one model                        cheapest; most errors
    tier 2  checked  + second opinion, tie-break      errors roughly halve
    tier 3  strict   + eager-prompt tripwire          fewest errors, most sent back to you

Give `sweep` a time budget and it picks the most accurate tier that fits. On
the benchmark's hard corpus the tiers went 13.3% -> 7.0% -> 5.9% wrong among
the items they decided, sending back 4 -> 7 -> 13 of 64.

## Reading the results

`decisions.jsonl` gives each item `finding` (with the quote), `none`, or
`undecided`. Then:

1. **Judge every `undecided` item yourself** - that is the hand-back. Its
   `votes` field holds each model's proposed quote. Read the document's top
   banner (to its LAST line - dates often sit there) and each proposed
   passage with a few lines of context; read the whole document only when no
   model proposed anything or the passages leave it open. On a real 152-doc
   audit this found every stale document at 66% of the tokens of full reads
   (553k vs 834k), with no wrong findings - one job, and the rules below were
   refined on it, so treat it as promising, not proven.
2. **Check every `finding`** before acting: grep or read around its quote,
   not the whole document.
3. **Skim every `none`**, do not trust it blind: from the facts or criteria,
   take the concrete terms (version numbers, option/command/flag/config names,
   dependencies, URLs), grep the document for them case-insensitively, and read
   only the matching lines with a little context. Measured on the benchmark's
   hard corpus: trusting "none" blind scored 61/64; skimming scored 64/64 in
   both runs, for 15-19% more Claude tokens - still 56% fewer than reading
   every document (Opus 5.5).
4. **Check your own report before handing it in.** Write it as JSON - a list
   of `{"id", "found", "quote"}` - and run

       $QG check --report report.json --items items.jsonl     # or --docs DIR

   It applies the same gate to YOUR quotes, against the document each is filed
   under. Fix every line it prints: `MISFILED` means the quote is real but
   belongs to the document it names - move it; `TOO SHORT` means quote the
   whole line; `NOT VERBATIM` means re-read and quote exactly. Measured: a
   Claude that read all 64 documents correctly filed three right quotes under
   the neighbouring document and scored 60/64; this check names all three.

**Dated or current?** For audits of documentation with dated records
(session logs, pre-registrations, handoffs), the costly judgement is whether a
sentence is history or a claim about now. Write these rules into the review:

- a banner or note that does not carry its own date speaks for today;
- a banner or note that states its own date is a dated record of that date;
- a document whose body was edited in place after the date in its name is
  living - its "current position" statements are current claims;
- a section appended with its own date below an unchanged body does NOT make
  the body living;
- a dated record describing its own day is not stale; a pointer to another
  page is not itself a contradiction.

Without them, two reviews of the same 152 documents disagreed on 6.

Report the yield line honestly (kept / dropped / errors). A drop rate of zero
on a hard task is the suspicious reading.

## Things that fail silently (all handled - do not undo them)

- Ollama's default context silently cuts long prompts to about half; quotegate
  always sends `num_ctx` and refuses a reply whose prompt was cut.
- `/api/generate` with a JSON schema silently switches reasoning off;
  quotegate uses `/api/chat`.
- Thinking defaults differ per model; some lose the answer at their default.
  Set `--think` explicitly (`off` for most models with a schema).
