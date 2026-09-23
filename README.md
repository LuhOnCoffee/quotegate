# quotegate

**Verified local offload for Claude Code.** Claude orchestrates; local models
(Ollama) answer one narrow question over many documents; **every answer must
carry a quote that is checked against the source** before anyone trusts it; and
whatever the local models cannot settle is handed back to Claude.

A plugin for Claude Code, plus a small Python CLI with no dependencies outside
the standard library. Not affiliated with or endorsed by Anthropic.

> Status: pre-release (0.0.4). Measured on a public, answer-keyed benchmark
> (below); not yet used outside its author's machine.

## What it is for

High-volume, narrow, **checkable** questions: "does this doc still claim X?",
"which of these files mention Y - quote it", "classify each item, with the
evidence". The answer is a quote plus a yes/no or a label, so it can be
verified mechanically instead of believed.

Not for: summaries or drafts (nothing to quote), judgement calls, adversarial
review, or anything where a wrong answer looks exactly like a right one.

## How it decides

    items ─▶ first model ─┐
                          ├─ agree (same sentence, or both "none")? ──▶ decided
             second model ┘            │ no
                                       ▼
                          cross-family tie-break ──▶ decided, or undecided
    decided "none" ─▶ eager-prompt tripwire ── fires? ──▶ undecided
    undecided ─────────────────────────────────────────▶ back to Claude

- **The quote gate**: a quote that is not literally in the document (after
  normalising whitespace and markdown emphasis - nothing else) is dropped and
  counted. An invented citation becomes lost yield, never a record.
- **Independent votes**: models never see each other's answers; agreement only
  counts if they quote the same place in the document. The tie-breaker must be
  a different model family - related models make related mistakes.
- **The tripwire**: the errors that survive voting are misses every model
  shares, because one prompt biases them all the same way. A second, eager
  prompt re-checks everything voted "none".
- **The same gate on the final report**: `quotegate check` verifies every
  quote in the finished report - usually Claude's own - against the document
  it is filed under, and names the right document when a real quote is
  misfiled (measured: a Claude report that scored 60/64 had three).
- **A time budget**: `sweep --budget-min N` runs the most accurate tier that
  fits, from speeds measured on your hardware (`calibrate`).

## Results (public corpora - reproducible, see RESULTS.md)

Corpus v2: 64 documents from 8 open-source projects (requests, flask, click,
pytest, black, httpx, poetry, pip), 32 with a subtle stale claim, 32 traps or
clean; blind double-keyed.

| tier | wrong among decided | sent back to Claude | s/doc (2 GPUs) |
|---|---|---|---|
| 1 fast - one model | 13.3% | 4 / 64 | 6.6 |
| 2 checked - + second opinion, tie-break | 7.0% | 7 / 64 | 17.0 |
| 3 strict - + eager-prompt tripwire | 5.9% | 13 / 64 | 20.9 |

A live tier-3 sweep reproduced the simulated result exactly. On corpus v3,
where every stale claim is only implied, tier 3 was 12.7% wrong - the local
models alone are not enough there, which is why Claude checks what they say.

**Claude tokens - measured, with the uncomfortable parts.** Three strategies
for the same audit, on four corpora, all on Claude Opus 5.5 (RESULTS.md):

| corpus | Claude reads everything | quotegate + grep skim of "none" | Claude + grep, no local models |
|---|---|---|---|
| v3 implied staleness | 63/64 at 217k | 61-62/64 at 117-122k | 55-56/64 at 82-88k |
| v2 subtle staleness | 64/64 at 249k | 64/64 at 106-110k (x2) | 62-63/64 at 78-89k |
| v1 keyword-rich | 60/64 at 230k (3 right answers filed under the wrong doc) | 63/64 at 85k | - |
| v4 consequences, with the fact expansion | not run | 62/64 at 168k | 56/64 at 86k |

Grep misses staleness that shares no words with the facts - a consequence of
old behaviour, a line of example config, `tox -e py39` when the fact says "3.10
or newer". The local models catch most of those (on v3, 7 documents right where
grep was wrong, none the other way). Where the staleness IS findable by
keyword, grep is enough: on v1 an earlier model (Opus 5), left to choose,
grepped its way to 64/64 at 72k. So: **quotegate pays off where what you are
looking for is not findable by keyword; where it is, just grep.** A few
consequences of old behaviour were missed by every cheap strategy - only a full
read found them. And "Claude alone" is not a fixed baseline: with the same
instructions Opus 5 grepped v1 and Opus 5.5 read all of it, a 3x difference in
cost. Numbers are from one task, four corpora and one or two runs per arm.

**Accuracy upgrade, measured (corpus v4):** expanding each fact into what an
out-of-date document might say ("expect every upgrade to reformat your code"
for "output is stable within a year") cut the local models' errors from 35.6%
to 25.0%; with Claude on top, quotegate + skim went from 57 to 59 of 64 at the
same token cost (one run each, not significant). Asking the local models to name the contradicted fact
backfired - they wrote "none" into the quote and lost the answer. v4 was keyed
by one agent, not two; see RESULTS.md for the caveats.

The prompt mattered more than the model: a careful prompt cut one model's false
findings from 16 to 5. Numbers are from one machine and one task; re-run `bench/` before trusting them for yours.

## Install

Requirements: Python 3.11+, [Ollama](https://ollama.com), and at least one
model pulled (e.g. `ollama pull gemma4:12b-it-qat`).

**As a Claude Code plugin** (from a local clone):

    /plugin marketplace add /path/to/quotegate
    /plugin install quotegate@quotegate

The skill `quotegate:quotegate` then loads when a task fits. Optional nudge on
large whole-file reads: set `QUOTEGATE_NUDGE=1` (and `QUOTEGATE_NUDGE_LINES`,
default 400) in the environment Claude Code runs in. It never blocks a read.

**As a CLI**, nothing to install:

    export PYTHONPATH=/path/to/quotegate/src
    python3 -m quotegate doctor --model gemma4:12b-it-qat     # checks two silent Ollama traps
    python3 -m quotegate run --model gemma4:12b-it-qat --items items.jsonl \
        --prompt careful.txt --think off --out raw.jsonl
    python3 -m quotegate sweep --roster examples/roster-single-gpu.toml \
        --items items.jsonl --prompt careful.txt --budget-min 20 --out decisions.jsonl
    python3 -m quotegate check --report report.json --items items.jsonl   # your own final quotes
    python3 -m quotegate expand --facts FACTS.txt                         # prompt for the fact expansion

The example rosters in `examples/` name the benchmark's models; change `name`
(and `host`) to models you have pulled - `ollama list` shows them - then run
`quotegate calibrate` on a few of your own items.

**Tests** (no GPU, no model, no network):

    python -m pip install -e ".[dev]"      # or: uv venv && uv pip install -e ".[dev]"
    python -m pytest -q
    python bench/check_claims.py           # every number in README/RESULTS vs the saved data

**Running a real audit** - facts, expansion, sweep, review, check, fixes, with
what each step cost on a 152-document job: [docs/AUDIT-GUIDE.md](docs/AUDIT-GUIDE.md).

## Findings about Ollama worth knowing even if you never use this

1. Ollama's default context silently cuts a prompt longer than `num_ctx` to
   about half - 2,050 of 7,944 tokens here, with no error. Always send
   `num_ctx`. `quotegate doctor` measures it on your install.
2. `/api/generate` with a JSON schema silently disables reasoning (0 chars of
   thinking vs 1,963 on `/api/chat`, same model and prompt).
3. Thinking defaults differ per model, and some lose the answer at their
   default. Set it explicitly.

## Prior art

Same architecture: [Minions](https://github.com/HazyResearch/minions)
(HazyResearch; local models answer with citations, the cloud model aggregates -
citations not mechanically checked). Source grounding:
[LangExtract](https://github.com/google/langextract) (fuzzy alignment by
default). Cascades: FrugalGPT, RouteLLM, AutoMix. Mechanical checks on local
output for dev chores: [claude-ollama-skills](https://github.com/hadeelsharaf/claude-ollama-skills).
The large-read hook follows [token_save_mcp](https://github.com/Habartru/token_save_mcp).

## Policy

quotegate runs inside your own Claude Code session and talks only to your
local Ollama. It never handles Claude credentials, never routes requests
through anyone's subscription, and never uses Claude's outputs to train models.

## License

Apache-2.0. Benchmark documents are excerpts of the projects listed in
`corpus/SOURCES.md`, under their own licenses.
