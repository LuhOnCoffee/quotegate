# Results

Four public corpora and one private one, same task: *given a project's
current facts, does this document state as current something that contradicts
them? Quote it.* Every quote is checked by the gate before it counts.
Reproduce the public numbers with `bench/score.py`, `bench/tiers.py`,
`bench/replay_sweep.py` and `bench/score_arms.py` (no GPU needed; the saved
model answers are in `corpus/*/runs/` and `corpus/*/sweep-live/`), and check
every headline figure with `bench/check_claims.py`.

Setup: Ollama 0.34.2 in WSL2, temperature 0, 16,384-token context, `/api/chat`
with a JSON schema, thinking set explicitly per model. Quadro RTX 5000 16 GB
and RTX 2080 Ti 11 GB; "both GPUs" means one model split across the two.
Seconds are per document, excluding model load, on warm (throttling) cards.

## Public corpus v1 - 64 docs, 8 OSS projects (2026-09-22)

32 documents with an uncorrected stale claim (16 organic old-version docs,
16 with one planted stale sentence), 32 without (16 with a planted
dated-history distractor, 16 clean). Blind double-keyed; see `corpus/`.

### Single models

usable = correct finding + correct "none", out of 64 (95% Wilson interval).
"false" = a verbatim quote that is not stale. "fab" = quote failed the gate.

| model | prompt | found (of 32) | correct none (of 32) | false | fab | usable | s/doc |
|---|---|---|---|---|---|---|---|
| qwen3.8:27b (both GPUs) | careful | 32 | 28 | 1 | 3 | **60 (85-98%)** | 9.8 |
| gemma4:26b-a4b (both GPUs) | careful | 30 | 30 | 2 | 1 | **60 (85-98%)** | 3.6 |
| gpt-oss:20b | eager | 32 | 27 | 1 | 3 | 59 (83-97%) | 11.7 |
| qwen3.8:27b | eager | 32 | 27 | 2 | 3 | 59 (83-97%) | 9.6 |
| gemma4:12b | careful | 31 | 26 | 5 | 2 | 57 (79-95%) | 6.0 |
| gemma4:26b-a4b | eager | 32 | 23 | 8 | 1 | 55 (75-92%) | 2.1 |
| gpt-oss:20b | careful | 30 | 22 | 1 | 8 | 52 (70-89%) | 17.3 |
| gemma4:12b | eager | 31 | 19 | 12 | 2 | 50 (67-86%) | 3.5 |

(gpt-oss careful also had 3 errors - reasoning ran to the 8,192-token cap.)

### Staged tiers (simulated from the saved answers)

| tier | stages | decided | wrong | to Claude | s/doc |
|---|---|---|---|---|---|
| 1 fast | gemma4:12b careful | 62 | 5 (8.1%) | 2 | 6.0 |
| 2 checked | + gemma4:26b opinion, gpt-oss tie-break on disagreement | 63 | **1 (1.6%)** | 1 | 11.3 |
| 3 strict | + qwen3.8 eager tripwire on "none" | 62 | 1 (1.6%) | 2 | 17.2 |

### What held, and what did not

- **The careful prompt cuts false findings for non-reasoning models**
  (gemma4:12b 12 -> 5, gemma4:26b 8 -> 2). It does not help gpt-oss, whose
  own reasoning appears to do the prompt's job; the careful prompt made it
  fabricate more quotes (8 vs 3).
- **The distractors work**: 15 of the 32 false findings across all runs were
  the planted dated-history sentences.
- **Cross-checking works**: tier 2 decided 63 of 64 with one error.
- **The tripwire adds nothing here.** Its value on the private corpus came
  from misses that every model shared; this corpus has none. It is kept, but
  no general claim is made for it until a corpus shows it mattering.
- **This corpus is too easy to rank the good configurations**: every one of
  them is at 92%+ with overlapping intervals. Planted claims are blunt
  ("supports Python 3.6 and newer"). See corpus v2 below.

## Public corpus v2 - 64 SUBTLE docs, same 8 projects (2026-09-22)

v1 was too easy to rank the good configurations, so v2 plants only subtle
staleness: an instruction that presupposes a removed feature (implicit), a
stale line only inside a code block (code), a present-tense claim inside an
admonition (note), one off-by-one claim among correct ones (multi) - 8 each -
against traps that must NOT be flagged: conditionals, hypotheticals, and
paraphrases of the current facts (8 each), plus 8 clean excerpts. All from
current HEAD docs; the only staleness is the insertion. Blind double-keyed:
both keyers keyed all 32 stale insertions and none of the 32 traps/clean docs.
Careful prompt: `bench/prompt_careful_v2.txt` (extended to implied claims and
code lines, matching what the key counts).

### Single models

| model | prompt | found (of 32) | correct none (of 32) | false | fab | usable | s/doc |
|---|---|---|---|---|---|---|---|
| qwen3.8:27b (both GPUs) | careful | 26 | 28 | 2 | 4 | **54 (74-91%)** | 13.9 |
| gemma4:12b | careful | 25 | 27 | 5 | 4 | 52 (70-89%) | 6.6 |
| gemma4:26b-a4b (both GPUs) | careful | 25 | 26 | 1 | 9 | 51 (68-88%) | 4.2 |
| qwen3.8:27b | eager | 26 | 24 | 5 | 5 | 50 (67-86%) | 6.7 |
| gpt-oss:20b | eager | 25 | 24 | 4 | 5 | 49 (65-85%) | 10.6 |
| gemma4:26b-a4b | eager | 26 | 22 | 9 | 3 | 48 (63-84%) | 2.2 |
| gemma4:12b | eager | 27 | 18 | 16 | 1 | 45 (58-80%) | 3.9 |
| gpt-oss:20b | careful | 20 | 22 | 2 | 8 | 42 (53-76%) | 17.8 |

(gpt-oss careful: 5 more errors, reasoning ran to the cap.)

### Where models fail (all 8 runs, 64 answers per kind)

| kind | correct | | kind | correct |
|---|---|---|---|---|
| implicit (stale) | 78% | | conditional (trap) | **64%** |
| code (stale) | **66%** | | hypothetical (trap) | **66%** |
| note (stale) | 89% | | paraphrase (trap) | 91% |
| multi (stale) | 80% | | clean | 78% |

Conditionals and hypotheticals are the most-failed kinds: models flag "if you
are still on Python 2.7..." and "were X ever to return..." as stale. Among real
staleness, a stale line inside a code block is the most often missed.

### Staged tiers - here they separate

| tier | decided | wrong | to Claude | s/doc |
|---|---|---|---|---|
| 1 fast (gemma4:12b careful) | 60 | 8 (13.3%) | 4 | 6.6 |
| 2 checked (+ gemma4:26b, gpt-oss tie-break) | 57 | 4 (7.0%) | 7 | 17.0 |
| 3 strict (+ qwen3.8 eager tripwire) | 51 | **3 (5.9%)** | 13 | 20.9 |

**Every error left at tier 3 is a miss shared by the models**, not a false
finding: a presupposed redirect default (implicit), the retired
`install-poetry.py` URL in a curl command (code), and one off-by-one claim
among correct ones (multi). That is the same pattern the private corpus showed
- residual errors are misses the models share - now on public, reproducible
data. The tripwire's gain here is modest (4 -> 3 wrong, 7 -> 13 to Claude).

## Public corpus v3 - 64 IMPLIED docs, same 8 projects (2026-09-22)

Built to test the one case every method failed on v2: staleness that is only
implied. Design fixed before any result (DECISIONS.md D10). HEAD docs only, one
insertion per doc, blind double-keyed. **No insertion states the stale fact
outright.**

- stale (32): an instruction that presupposes a removed or changed behaviour
  (11); a code/config example that only makes sense under the old behaviour
  (11); a consequence that only holds under the old behaviour (10).
- not stale (32): conditional, hypothetical, paraphrase, clean (8 each).

### Staged tiers (replayed from the live tier-3 sweep's votes)

| tier | decided | wrong | to Claude |
|---|---|---|---|
| 1 fast (gemma4:12b careful) | 59 | 10 (16.9%) | 5 |
| 2 checked (+ gemma4:26b, gpt-oss tie-break) | 60 | 9 (15.0%) | 4 |
| 3 strict (+ qwen3.8 eager tripwire) | 55 | **7 (12.7%)** | 9 |

`bench/replay_sweep.py` replays tiers 1-3 through the sweep's own policy code.
Its tier-3 line matches the live sweep exactly (55 / 7 / 9; 26.2 min on two
GPUs), and run on v2's live votes it reproduces v2's tier table exactly. Implied staleness is harder for the local models than v2's subtle
staleness (5.9% wrong at tier 3): five of the seven errors are "none" verdicts
on stale docs, the same shared-miss pattern as before, just more of it.

## Public corpus v4 - consequences, and two accuracy upgrades (2026-09-22)

Designed and fixed before any result (DECISIONS.md D13 and its amendment).
Every remaining quotegate miss on v3 was a *consequence* of old behaviour, so
v4 is built around them, on NEW HEAD documents of the same 8 projects and
facts: stale = consequence x2, instruction, example per project (16/8/8);
not stale = conditional, hypothetical, *current* consequence (true today - the
trap for a reader who flags every consequence) and clean, 8 each.

**Keyed by ONE blind agent**, not two (the build cost 916k tokens against an
estimate that never checked v3's 864k; the owner chose a lean finish). The
keyer found 31 of the 32 planted stale passages and flagged none of the 32
not-stale ones. The 32nd (click-d07: advice that is outdated but still works)
and two arguable upstream passages were ruled by the orchestrator as neither
right nor wrong (`corpus/v4/key.json`, "borderline"). So v4 scores 31 stale,
32 not stale and 1 either way. Its key is weaker than v1-v3's.

**Threat to validity:** the expansion and the planted passages were written by
the same model (Opus 5.5) from the same facts, though the builders never saw
the expansion and were told to root each insertion in its document's own
context. Real-world stale docs may resemble the expansion less. The grep arm
given the same expansion (D+) is the partial control.

### The two upgrades

- **Expansion**: one agent, given only the 40 facts, wrote 2-5 lines per fact
  on what an out-of-date document might say, show or tell the reader to do
  (`corpus/v4/expansion.json`, 137 lines). It goes to the local models after
  the facts, and to the skim as extra search terms.
- **Findings name their fact**: `bench/prompt_careful_v4.txt` differs from v2
  only in asking for the id of the contradicted fact ("none" if nothing).

### Local sweeps (tier 3, same roster; replayed = live for all three)

| sweep | decided | wrong | to Claude | min |
|---|---|---|---|---|
| BASE - v2 prompt, plain facts (the v3 setup) | 45 | 16 (35.6%) | 19 | 37.2 |
| EXP - v2 prompt, facts + expansion | 44 | **11 (25.0%)** | 20 | 34.2 |
| V4 - v4 prompt, facts with ids + expansion | 24 | 1 (4.2%) | **40** | 36.7 |

Consequence-heavy staleness is far harder for the local models than v3's
(12.7% wrong at tier 3). **The expansion cut their errors by almost a third.**
**Asking for the fact id backfired**: told to put "none" in `fact` when
nothing is stale, the gemma models also wrote "none" into the quote
(`"none/none_found"`), the gate dropped those answers (37 of the first
model's 64), and V4 sent 40 documents back to Claude. What it did decide was
right - because only the easy cases survived. Not fixed and re-run: that would
tune the prompt on the test corpus. A future prompt should leave `fact` empty
rather than say "none".

### Claude arms (Opus 5.5, one run each)

| arm | Claude tokens | correct (of 64) | stale found (of 31) | consequences (of 16) |
|---|---|---|---|---|
| D Claude + grep, plain facts | 91,924 | 55 | 22 | 13 |
| D+ Claude + grep, facts + expansion | 86,080 | 56 | 23 | 13 |
| C quotegate BASE + skim, plain facts | 142,377 | 57 | 24 | 12 |
| C+ quotegate V4 + skim with the expansion | 167,874 | **62** | **29** | **16** |
| C-exp quotegate EXP + skim with the expansion (D14, run after) | 142,204 | 59 | 26 | 15 |

Every arm got all 33 not-stale documents right. (C and C+ also needed their
sweep; C+'s run was restarted once, after its first prompt was found to add a
second change D13 did not name - 34,565 tokens spent on the discarded start.)
`quotegate check` on these reports: no misfiled quotes; it flags D's and D+'s
`[pytest]` as too short to check - quoted in full they would be 56 and 57.

Pre-registered tests: **C+ vs C** 5-0 on the same documents (sign test
p 0.062, not significant at 0.05) with no extra wrong findings; **C+ vs D+**
6-0 (p 0.031). Both in C+'s direction.

**But the win has three parts, not one** (from how each document was routed):

| C+ gained over C on | routed by | credit |
|---|---|---|
| black-d06, pytest-d04 | BASE "none" (wrong); EXP and V4 "undecided" | the expansion |
| requests-d01, requests-d07 | "none" in BASE and EXP; "undecided" only in V4 | the V4 prompt's dropped answers - more full reads |
| requests-d08 | "finding" in all three | Claude confirming a finding C rejected |

So: the expansion helps (fewer local errors; 2 of the 5 gains; +1 for grep),
fact-naming as prompted does not, and part of C+'s margin was bought by reading
more (+26k tokens).

**The clean test (D14, fixed before its result):** C-exp is C+ with the EXP
sweep instead of V4 - so it differs from C only by the expansion. **59/64 at
142,204 tokens, against C's 57/64 at 142,377**: the same cost. Paired against
C it is 3-1 (p 0.63, not significant): the two expansion-routed documents
(black-d06, pytest-d04) reproduced, it accepted requests-d08, and it lost
black-d08, a Python 2 `print` example C had caught - Claude's judgement varying
between runs. C+'s other gains (requests-d01, requests-d07) did not appear
without the extra full reads. **Net: the expansion is worth about two
documents in 64 on this corpus, at no Claude-token cost; not significant with
one run.** Total v4 spend: ~1.95M Claude tokens (build 916k, key 331k, arms
630k, expansion 34k, discarded start 35k).

## A real job: auditing a private project's docs (2026-09-22), aggregate only

The installed plugin, used as its skill says, on 152 living documents of the
private project behind the 60-doc corpus - no benchmark, no answer key; the
documents are not published. 7 dated facts, each checked against the code or
the running system; an expansion written from the facts alone; a tier-3
sweep; a Claude review (every finding checked, every undecided doc read, every
"none" skimmed); `quotegate check` on the final report.

| step | result | time / cost |
|---|---|---|
| local sweep, tier 3 | 40 findings, 46 none, 66 undecided | 113.0 min (2 GPUs) |
| Claude review, 6 agents in parallel | 9 reported; after adjudication 7 right, 2 wrong, 2 missed (below); 35 of 40 local findings rejected | 4.3 min, 834,044 Claude tokens |
| `quotegate check` | 9/9 quotes verbatim in their own document; **1 document never reported** | seconds |

What it taught:
- **Local models over-flag dated records.** 35 of 40 local findings were
  sentences true on the day their document was written (a dated plan saying
  some data is still unused, on the day it was). The two local
  models disagreed on 107 of 152 documents (70%; 35% on the benchmark).
  Claude's check is what makes the findings usable.
- **The skim of 46 "none" documents found nothing**; the 9 stale documents
  came from 5 confirmed findings and 4 undecided documents read in full.
- **`quotegate check` earned its place on first use**: a review agent silently
  dropped one of its 25 documents, and the check named it.
- **Cost was far above the estimate** (~150-300k quoted, 834k measured): 66
  undecided documents at ~12k characters each, read by six agents that each
  carried their own context. On long, history-heavy documents the local
  pre-pass sends much more back to Claude than on the benchmark.
- **The sweep ran 1.7x slower than the roster predicted** - the roster was
  calibrated on benchmark prompts, and facts plus an expansion lengthen every
  prompt. The sweep now re-plans from its measured pace and says so.

### Cutting the review cost (D15, D16)

The job's stale set, after adjudicating every disagreement between three
reviews by reading the passage in context (recorded with the job): **9
documents** - and not the first review's 9: two of its findings were dated
banners ("Banner added 2026-09-14"), and it missed two living state pages.

| review | Claude tokens | stale found (of 9) | wrong |
|---|---|---|---|
| first review (full reads of undecided docs) | 834,044 | 7 | 2 |
| D15(b) skim undecided docs first | 500,306 | 5 | 2 |
| D16 read only the banner + the passages any local model proposed, with written dated-vs-current rules | 553,582 | **9** | 4 |
| D17 = D16 with "appended dated sections do not make the body living" | 553,434 | **9** | **0** |

D15(a), telling the local models each document's date, halved their false
findings (35 -> 18) but left 25% more text undecided - cleaner, not cheaper.

The hard part is the judgement "dated record or current claim?", and it is
not stable: the first review and I both misread two banners whose date sat on
their last line. Writing the rules down (D16) found every stale document at
66% of the cost, but over-applied "edited later = living" to documents whose
later parts are appended with their own date. D17 narrowed that one rule and
found all 9 with no wrong findings at the same cost - **adopted as the skill's
review method**, with a caveat: its rule was refined on these same
documents, so this score is optimistic until it is repeated on a fresh set.
In 2 of the 5 review runs (the first review and D17) an agent silently
skipped one document; `quotegate check` named it both times. One run each.

**On a fresh set (D18):** the same method, unchanged, on the only unaudited
documents the same facts cover - 5 project files outside the audited folder
(including its CLAUDE.md) and 7 of the orchestrator's own memory notes. Sweep
9.9 min, review 79,707 tokens; 3 of 3 stale documents found, 1 wrong (a line
inside a bullet with its own date), none missed on a term grep of the rest.
Adjudicated by the orchestrator, who wrote the memory notes. It shows the
rules carry over to documents they were not tuned on; 12 documents are not
enough to measure accuracy.

## Two GPUs, one model (2026-09-22)

The first stage (gemma4:12b, 7.7 GB) fits either card. Measured on 30 of the
real job's documents above, same prompt, tier 1:

| hosts | wall time | items per host | same decision as one host |
|---|---|---|---|
| 2080 Ti only | 342 s | 30 | - |
| 2080 Ti + Quadro | **182 s (1.9x faster)** | 19 + 11 | 29 of 30 |

The Quadro is the slower card here, so the shared queue gave it fewer items.
One decision in 30 differed: the same model at temperature 0 is not
bit-identical across two GPUs.

## Claude tokens: does quotegate save them, and against what? (2026-09-22)

The same stale-claim task, done by fresh Claude agents that could not see the
key. **Every arm below ran on Claude Opus 5.5 (`claude-opus-5-5`)**, read from
each agent's transcript. v1 and v2 were first run on Opus 5 and re-run on Opus
5.5 with unchanged prompts and inputs (DECISIONS.md D12); the Opus 5 runs are
compared in a table below and kept in `corpus/*/savings/opus5/`.
Every design was fixed in DECISIONS.md (D6-D8, D10-D12) before its results.
Arms:

- **A - Claude alone**: told the task; free to choose how to read.
- **B - quotegate**: starts from a live tier-3 sweep; reads undecided docs in
  full, checks findings around their quotes, accepts "none" unread.
- **C - quotegate + skim**: B, but each "none" doc is skimmed: grep for terms
  taken from the facts, read only the matches.
- **D - Claude + grep, no local models**: C's grep strategy on EVERY document.

### Corpus v3 (implied staleness)

| arm | Claude tokens | correct (of 64) | errors |
|---|---|---|---|
| A Claude alone (read everything) | 217,067 | **63** | 1 miss: a `requires-python = ">=3.9"` line in an example |
| C quotegate + skim, run 1 | 121,800 | **62** | 2 misses, both consequences |
| C quotegate + skim, run 2 | 116,653 | 61 | 3 misses, all consequences |
| D Claude + grep, run 1 | 87,875 | 55 | 8 misses + 1 quote too short to check (`[pytest]`) |
| D Claude + grep, run 2 | 82,092 | 56 | 7 misses + the same short quote |

(C also needed the 26.2 min tier-3 sweep.) Paired on run 1, C was right where
D was wrong on 7 documents and the reverse on none (exact sign test p = 0.016);
A against C: 2 against 1, no difference. D's `[pytest]` finding points at the
right line but is under the 12-character quote minimum, so it scores as
unverifiable; counted leniently D is 56 and 57.

By kind of claim (correct, run 1 / run 2 where there are two):

| kind | A alone | C quotegate + skim | D grep |
|---|---|---|---|
| instruction (11) | 11 | 11 / 11 | 11 / 11 |
| example (11) | 10 | 11 / 11 | 8 / 8 |
| consequence (10) | **10** | 8 / 7 | **4 / 5** |
| traps and clean (32) | 32 | 32 / 32 | 32 / 32 |

Grep fails where the stale text shares no words with the facts: a consequence
("expect snapshots to start failing on every upgrade" when the fact is that
formatting is stable within a year) or a line of example config. The local
models catch all the examples and most consequences; the consequences they
share a miss on are the three Claude-with-skim also misses. Only Claude
reading everything caught every consequence, at 1.8x C's tokens.

### Corpus v2 (subtle staleness)

| arm | Claude tokens | correct (of 64) | errors |
|---|---|---|---|
| A Claude alone (read everything) | 248,593 | **64** | - |
| B quotegate | 92,746 | 61 | 3 misses the local models shared |
| C quotegate + skim, run 1 | 106,349 | **64** | - |
| C quotegate + skim, run 2 | 110,244 | **64** | - |
| D Claude + grep, run 1 | 78,359 | 62 | 2 misses: `tox -e py39` twice |
| D Claude + grep, run 2 | 88,930 | 63 | 1 miss: `tox -e py39` in prose |
| E quotegate + `quotegate skim` (mechanical terms) | 117,080 | **64** | - |

(B, C and E also needed the tier-3 sweep: 25.1 min on two local GPUs.)

### Corpus v1 (blunter, keyword-rich staleness)

| arm | Claude tokens | correct (of 64) | errors |
|---|---|---|---|
| A Claude alone (read everything) | 229,894 | 60 | 3 right quotes filed under the wrong document, 1 miss as a result |
| B quotegate | 64,968 | **64** | - |
| C quotegate + skim | 85,497 | 63 | confirmed the sweep's one false finding |

(B and C also needed a 20.0 min sweep. The live v1 sweep matched its
simulation exactly: 62 decided, 1 wrong, 2 undecided.)

Arm A's four errors on v1 are one slip: it found the stale sentences of
black-d06, d07 and d08 and reported each under the document before it (d05,
d06, d07), leaving d08 empty. The reading was right; the bookkeeping was not.
The quote gate is what catches this - each quote is checked against the
document it is filed under, and failed.

### Same prompts, Opus 5 against Opus 5.5

| corpus | arm | Opus 5 | Opus 5.5 |
|---|---|---|---|
| v1 | A Claude alone | 64/64, 72k (chose to grep) | 60/64, 230k (read everything) |
| v1 | B quotegate | 63/64, 58k | 64/64, 65k |
| v1 | C quotegate + skim | 63/64, 82k | 63/64, 85k |
| v2 | A Claude alone | 64/64, 239k | 64/64, 249k |
| v2 | B quotegate | 61/64, 95k | 61/64, 93k |
| v2 | C quotegate + skim (2 runs) | 64, 64 at 109k, 109k | 64, 64 at 106k, 110k |
| v2 | D Claude + grep (2 runs) | 62, 61 at 91k, 76k | 62, 63 at 78k, 89k |
| v2 | E quotegate + mechanical skim | 63/64, 114k | 64/64, 117k |

Every arm that follows a fixed method (B-E) landed within 13k tokens and one
answer of itself across the two models, and missed the same documents. The one arm free to choose its own method (A) changed method on v1,
and its cost moved 3x.

### What this says

- **On implied staleness (v3), quotegate beats grep.** 61-62/64 against
  55-56/64, paired 7-0 on the same documents, for ~35k more Claude tokens;
  and it matches Claude reading everything (63/64) at ~55% of its tokens. What
  remains are consequences of old behaviour that no model and no keyword
  finds - they need a full read.
- **The two local-free strategies and quotegate fail differently.** Grep
  misses staleness written without the facts' own words (`tox -e py39` when
  the fact says "3.10 or newer"); the local models read the whole text and
  catch those. The local models' misses were shared ones that DID contain the
  facts' keywords, which the skim catches. On v2 the combination (C) was fully
  correct in both runs at -56% Claude tokens against reading everything, and
  +21-28k tokens against grep alone (run for run) for 1-2 more correct answers.
- **The mechanical skim (arm E) ties Claude's own skim, no better.** `quotegate
  skim` derives terms from the facts (older-version spellings like `py39`,
  code tokens, rarer content words; max-df 0.5 chosen on this corpus) and
  surfaces every line it needs to. On Opus 5 Claude then judged the one
  implied claim (pass `follow_redirects=False`, presupposing redirects are
  followed by default) not stale (63/64); on Opus 5.5 it judged it stale
  (64/64). Either way the skim text costs as many tokens as Claude's own
  targeted greps. Kept as a tool that removes term-choice variance; no claim
  that it is cheaper. One run per model.
- **Where staleness is keyword-findable, the cheapest good answer is grep.**
  On v1 Opus 5, left to choose, grepped and got 64/64 at 72k; Opus 5.5 read
  everything instead (230k) and slipped. quotegate (B) got 64/64 at 65k - but
  so can a Claude told to grep. The honest claim is narrow: quotegate earns
  its GPU time on staleness that is not findable by keyword - implied claims,
  reworded versions, config lines.
- **"Claude alone" is not a fixed baseline.** Same instructions, same corpus:
  Opus 5 grepped v1 (72k), Opus 5.5 read it all (230k). Any savings figure
  depends on which Claude you compare against, and "read everything" flatters
  any tool.
- **Checking findings is not a perfect filter.** On v1 the quotegate arms
  confirmed the sweep's one false finding (pip-d03, a borderline sentence
  about VCS installs) in 3 of 4 runs across both models; Claude alone never
  flagged it.
- Limits: one task, four corpora, one to two runs per arm per model,
  token totals not split into cached and uncached input. Token counts are the
  agent's final context size from its transcript; for the Opus 5.5 re-run the
  ten per-agent counts sum to 0.2% more than the workflow's own total
  (1,222,660 vs 1,220,147). Per-arm answers: `corpus/*/savings/`.

## Private corpus - 60 docs (2026-09-21), aggregate only

Measured on 60 internal project-state documents that cannot be published.
**Not reproducible by anyone else**; reported only because it is where the
harness failures and the tripwire were found. 22 documents with an
uncorrected stale claim, 5 whose stale claims are corrected later in the same
document, 33 clean.

| configuration | usable of 60 | false findings |
|---|---|---|
| gemma4:12b, eager prompt | 24 | 29 |
| gemma4:12b, careful prompt | 45 | 5 |
| qwen3.8:27b, careful prompt | 48 | 0 |

| tier (same policy as above) | wrong among decided | to Claude |
|---|---|---|
| 1 fast | 16.7% | 6 |
| 2 checked | 8.2% | 11 |
| 3 strict (tripwire) | 2.9% | 26 |

There, all remaining errors after voting were misses every model shared,
caused by the careful prompt's "dated history does not count" rule; a
different-prompt tripwire removed most of them. Public corpus v1 did not
reproduce that pattern (it had no shared misses); v2 did - its residual errors
are shared misses too - though there the tripwire's gain was smaller.

## Harness findings (all corpora)

1. Ollama's default context silently cut a 4,167-token prompt to 2,050 - it
   keeps about half of `num_ctx` when the prompt exceeds it. Detect by
   chars/token, not by "near the limit". `quotegate doctor` measures it live:
   the same prompt read as 2,050 tokens at the default context and 7,944 at
   num_ctx 32768 (2026-09-22).
2. `/api/generate` with a JSON schema silently disables reasoning (qwen3: 0
   thinking chars; gpt-oss: empty response). `/api/chat` does not.
   `quotegate doctor` measures it live: 0 chars of thinking on generate, 1,963
   on chat (qwen3:8b, 2026-09-22).
3. Thinking defaults differ per model; two lost the answer entirely at their
   default (gemma4 empty output; qwen3.5 JSON written into the thinking field).
4. Models drop markdown emphasis when quoting; 9 of one run's 15 gate failures
   were exact apart from `**`.
