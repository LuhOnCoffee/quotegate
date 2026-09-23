# Decisions log

Judgement calls made without the owner present, for review. Each entry: what,
why, and how to undo it. Irreversible or outward-facing actions (pushing,
deleting data, anything touching the owner's other running systems) are never
taken here; they wait for the owner.

## 2026-09-22 overnight session

The owner's brief (03:25): work on milestone 3 (the Claude Code plugin);
use GPUs and disk freely; Claude spend for the token-savings test: modest (one
64-doc audit each way); on a blocker, decide conservatively, log it, move on.

- **D1 - Token-savings test runs after the plugin.** The owner picked only
  milestone 3 as overnight work but also set a spend for the token test.
  Read as: permitted, lower priority. It runs only if the plugin is done, at
  the approved modest scale. Undo: ignore/delete its results.

- **D2 - The large-read hook is opt-in via an environment variable, not
  plugin userConfig.** The docs confirm plugins can declare `userConfig`, but
  I could not verify how a hook script reads its values, so the hook checks
  `QUOTEGATE_NUDGE=1` (verified live: nudge received with it, nothing without
  it). Undo: switch to userConfig once its hook interface is confirmed.
- **D3 - The repository root is the plugin root.** The skill runs the CLI as
  `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/src python3 -m quotegate`, which only works
  if src/ is inside the plugin; a separate plugin/ folder would break it.
  Verified live: a fresh Claude Code instance ran `doctor` from the skill's
  instructions with nothing installed.
- **D4 - The savings footer is an ESTIMATE and says so.** Undecided items
  counted as read in full, findings as 1,500 chars around the quote, "none"
  as free, at 4 chars/token. The real number needs the milestone-4
  experiment; the footer must never be quoted as a measurement.
- **D5 - README states results with their limits** ("one machine and one task;
  re-run bench/"), and names prior art (Minions, LangExtract, cascades,
  claude-ollama-skills, token_save_mcp) as the survey recommended.
- **D6 - Token-savings experiment design, fixed BEFORE results.** Corpus v2,
  64 docs, the same stale-claim task. Arm A: one Claude agent reads every
  doc. Arm B: one Claude agent starts from the live tier-3 sweep output
  (corpus/v2/sweep-live), reads undecided docs in full, checks findings only
  around their quotes, and accepts "none". Each arm is its own single-agent
  workflow so its token count stands alone; both scored with the same key and
  scorer. Reported: Claude tokens per arm, accuracy per arm, and the local
  GPU time arm B needed (the 25.1-minute sweep). n=1 run per arm: a first
  number, not a distribution.

## 2026-09-22 early morning (owner asleep until 10:00)

Brief (03:40): the skim-"none" variant; Claude budget up to ~2M tokens;
user-space installs allowed.

- **D7 - Skim-variant design, fixed BEFORE results.** Arm C = arm B plus a
  skim: for every doc the sweep decided "none", Claude derives search terms
  from FACTS.txt (version numbers, option/command/dependency names), greps the
  doc for them, reads only the matched lines with a little context, and flags
  the doc only if a matched line is stale. Undecided docs are read in full and
  findings checked around their quotes, exactly as in arm B.
  Measured: arm C twice on corpus v2 (to see run-to-run variation), and all
  three arms (A Claude alone, B quotegate, C quotegate + skim) once on corpus
  v1 after a LIVE tier-3 sweep on v1. Each arm is its own single-agent
  workflow; all scored with the same key and scorer. Expected spend ~750k
  tokens, within the ~2M budget. Undo: ignore corpus/*/savings/arm_c*.
- **D8 - Add a "Claude + grep, no local models" control arm, fixed BEFORE its
  results.** On corpus v1, arm A ("Claude alone", same instructions as on v2)
  did NOT read every document: it chose to grep each project for fact-derived
  terms and read around the matches, scoring 64/64 at 72,480 tokens - cheaper
  than the skim arm (81,523) and more accurate than both quotegate arms
  (63/64). On v2 the same instructions led it to read everything (239,157).
  So the skim arm's result may be mostly grep, not quotegate. Arm D: Claude
  alone, told to use exactly the skim arm's grep strategy on EVERY document
  (no pre-pass), on corpus v2 - the harder corpus, where the local models'
  errors were shared misses. If D matches C's 64/64 at similar or lower cost,
  quotegate adds little for this task type, and that must be reported.
  One run. Undo: ignore corpus/v2/savings/arm_d*.
- **D9 - `quotegate skim` (mechanical terms) and arm E, fixed BEFORE arm E's
  result.** Grep's weakness was the terms Claude picks (it never searched
  `py39` for "3.10 or newer"; whether it searched "redirect" varied by run).
  `quotegate skim` derives terms from the facts: older-version spellings (3.9,
  py39, cp39, 2.7 ...), code-like tokens, and content words that appear in at
  most half of the project's documents. That max-df of 0.5 was CHOSEN ON v2
  (it surfaced all 3 misses the local models shared, at 21% of the "none"
  docs' lines) - tuned on the corpus it is then scored on; v1 has no stale
  "none" docs to validate recall. Arm E = arm B plus: for "none" docs, read
  the precomputed `quotegate skim` output (corpus/v2/sweep-live/skim-none.txt)
  instead of grepping. One run on v2. Undo: ignore arm_e*.
  RESULT (recorded after): arm E 63/64 at 114,241 tokens - no better than
  arm C (64/64, ~109k). The skim showed the httpx-d03 line; Claude judged
  the implied claim not stale. Reported as a negative result.
- **D10 - Corpus v3 (implied claims), design fixed BEFORE results.** The one
  case every method failed was an IMPLIED claim (httpx-d03: "pass
  follow_redirects=False to see the 302" presupposes redirects are followed).
  v3 tests exactly that. Same 8 projects and facts, HEAD docs only, one
  insertion per doc:
    stale (32): instruction that presupposes a removed/changed behaviour (11);
      a code/config example that only makes sense under the old behaviour,
      with no explicit claim (11); a consequence that only holds under the old
      behaviour (10). NONE states the stale fact outright.
    not stale (32): conditional, hypothetical, paraphrase, clean (8 each).
  Blind double-keyed as before. Then: live tier-3 sweep, and three Claude arms
  (A alone, D grep-only, C quotegate + skim). If quotegate does not beat grep
  here, the owner's instruction (2026-09-22) is to report it and narrow the
  pitch to the method and the benchmark. Expected spend ~500k tokens.
  RESULT (recorded after): quotegate beats grep here. C 62, 61 / 64 at
  122k, 117k tokens; D 55, 56 / 64 at 88k, 82k; A 63/64 at 217k. Paired run 1,
  C right / D wrong on 7 docs, the reverse on 0 (sign test p 0.016). The pitch
  is NOT narrowed; README now shows all three corpora side by side.
- **D11 - Second runs of C and D on v3, added AFTER run 1's result.** Same
  prompts, fresh agents; v2 had two runs of each, so v3 gets the same, to show
  run-to-run spread rather than a single point. Cost ~200k tokens (v3 total
  ~625k, within the ~2M budget). The per-kind table in RESULTS is a post-hoc
  breakdown by the construction key's "kind" field, not a pre-registered test.
- **D12 - Every v1 and v2 Claude arm re-run on Opus 5.5, fixed BEFORE the
  re-run's results.** The owner asked (2026-09-22) for every token arm to be
  on the current model; v1/v2 ran on Opus 5, v3 on Opus 5.5. Re-run from the
  original workflow scripts, unchanged prompts, same inputs (same saved
  sweeps, same skim file): v1 A, B, C; v2 A, B, C x2, D x2, E - ten agents,
  ~1M tokens expected. The Opus 5.5 runs become the headline tables; the Opus 5
  runs move to `corpus/*/savings/opus5/` and are reported once, as a
  same-prompt model comparison, not averaged in.
  RESULT (recorded after): the arms that follow a fixed method (B-E) moved by
  at most 13k tokens and one answer, and missed the same documents, on both
  models. Claude alone changed METHOD on v1 (Opus 5 grepped, 72k, 64/64; Opus
  5.5 read everything, 230k, 60/64 - three right quotes filed under the
  neighbouring document, caught by the gate). ~1.22M tokens.
- **D13 - Corpus v4 and two accuracy upgrades, design fixed BEFORE any v4
  result.** Owner (2026-09-22): test (1) expanding the facts into their
  consequences and (2) making every finding name the fact it contradicts;
  up to ~1M Claude tokens. Every remaining quotegate miss on v3 was a
  consequence of old behaviour.
  Corpus v4: same 8 projects and facts, NEW HEAD documents (none used by
  v1-v3), 8 per project: stale = consequence x2, instruction x1, example x1;
  not stale = conditional, hypothetical, CURRENT consequence (a consequence
  that is true under today's behaviour - the trap an over-eager expansion
  falls into), clean. 32/32. Blind double-keyed as v3.
  Expansion: ONE Claude agent, given only the 8 FACTS lists, writes for each
  fact what a document written before the change might say, show or tell the
  reader to do that is now wrong. Written and committed BEFORE the corpus is
  built; corpus builders and keyers never see it.
  Local sweeps (tier 3, same roster): BASE = prompt_careful_v2 + plain facts
  (the v3 setup); EXP = the same prompt + facts + expansion; V4 = a new prompt
  that also asks for the fact id + facts with ids + expansion. EXP vs BASE
  isolates the expansion; V4 vs EXP isolates naming the fact.
  Claude arms (Opus 5.5, one run each): A alone; D grep, plain facts;
  D+ grep, facts + expansion (the control: does the expansion help grep as
  much?); C quotegate BASE + skim; C+ quotegate V4 + skim with the expansion.
  Every report is scored raw AND after `quotegate check` moves misfiled quotes
  (reported separately, never merged).
  Success, stated now: C+ beats C on stale documents without more wrong
  findings on the 32 not-stale documents, AND C+ beats D+ on the same
  documents. Anything else is reported as is. If the build and keying cost more
  than ~450k tokens, arm A is dropped (v3's A stands as the reference) and
  that is said.
  AMENDMENT (2026-09-22, before any v4 result): the corpus build cost 916k
  tokens (v3's had cost 864k; the ~1M estimate never checked it). The owner
  chose a lean finish: ONE blind keyer instead of two (4 agents, 2 projects
  each), checked against the construction key; the 3 local sweeps; Claude
  arms C, C+, D, D+ only - arm A dropped as D13 already provided, v3's A is
  the reference. Single-keyed means the v4 key is weaker than v1-v3's;
  RESULTS says so.
  RESULT (recorded after): local sweeps BASE 35.6% wrong, EXP 25.0%, V4 4.2%
  but 40 of 64 sent to Claude (the fact-id prompt made the gemma models write
  "none" into the quote; the gate dropped them). Claude arms: D 55, D+ 56, C
  57, C+ 62 of 64; no arm flagged a not-stale doc. C+ vs C 5-0 (p 0.062), C+
  vs D+ 6-0 (p 0.031). Of C+'s 5 gains over C, 2 are the expansion's, 2 came
  from the extra full reads V4's dropped answers forced, 1 is Claude's
  judgement. C+'s first launch was stopped and relaunched because its prompt
  also reworded the stale definition - a second change D13 did not name
  (34,565 tokens discarded). Total v4 ~1.80M tokens.
- **D14 - The clean test of the expansion, fixed BEFORE its result.** Arm
  C-exp: quotegate on the EXP sweep (v2 prompt, facts + expansion; 20
  undecided, the same as BASE's 19 give or take one), skim terms from facts +
  expansion, wording identical to C+ (which differs from C only by the
  EXPANSION.txt line and the skim terms). One run, Opus 5.5, ~150k tokens,
  owner-approved 2026-09-22. Compared paired against C (same wording minus
  the expansion). If C-exp beats C by about what C+ did without the extra
  full reads, the expansion carries the gain; if it matches C, it does not.
  RESULT (recorded after): C-exp 59/64 at 142,204 tokens vs C 57/64 at
  142,377. Paired 3-1 (p 0.63): black-d06 and pytest-d04 reproduced,
  requests-d08 accepted, black-d08 lost. The expansion is worth ~2 docs at no
  token cost - directional, not significant.

- **D15 - Cutting the review cost, fixed BEFORE either result.** The first
  real job (152 private docs) cost 834,044 Claude tokens to review, far over
  the estimate: 66 undecided long docs read in full, and 35 of 40 local
  findings were dated records. Reference = that review (9 stale docs). It is
  ONE Claude run, not an answer key: any disagreement with it is adjudicated
  by reading the quoted sentence, and each adjudication is recorded.
  (b) SKIM FIRST, Claude side only: re-review the SAME sweep output with one
  change - an undecided doc is skimmed first (terms from facts + expansion,
  the top banner, matching lines with context) and read in full only when the
  skim leaves it open. Same 6-agent split. Measured: tokens, stale docs found
  vs the reference. Expected ~300-400k tokens, owner-approved.
  (a) DATE-AWARE LOCAL PASS, GPU only: a second tier-3 sweep whose items add
  one line to the facts for docs with a date in their file name ("this
  document is dated D; statements describing that day are dated history").
  Everything else identical (prompt, roster; the first stage split across both
  GPUs). Measured without Claude: local findings the reference rejected,
  undecided count, and whether each of the 9 stale docs still reaches Claude
  (finding or undecided). A stale doc turned "none" is counted as a risk.
  RESULT (recorded after): (b) skim-first 500,306 tokens (-40%) but 5 of the
  9 adjudicated stale docs, plus 2 wrong - its misses were judgement ("dated
  history") on lines it did read. (a) date-aware sweep: local findings that
  were not stale 35 -> 18, all 9 stale docs still routed exactly as before,
  but undecided 66 -> 88 (988k -> 1,238k chars for Claude to read) - cleaner
  findings, MORE review cost. Sweep 122 min (first stage split across both
  GPUs, 2x; the one-card tie-break had 123 docs). Neither is adopted.
  Adjudication of the 6 disputed docs: jobs dir, d15b/ADJUDICATION.md.

- **D16 - Targeted reading plus written dated-vs-current rules, fixed BEFORE
  its result.** Same sweep output and 6-group split as the reference review.
  Two changes, together: (1) an undecided doc is judged from its top banner
  (~40 lines) and the passages ANY local model proposed (verbatim quotes from
  the votes, given to the reviewer), with a full read only when no model
  proposed anything or the passages leave it open; (2) the review prompt
  states the rules the D15 adjudication used - a banner or note that does not
  carry its own date speaks for today; one that states its date is a dated
  record; a document edited after the date in its name is living; a dated
  session record describing its own day is not stale. Scored against the 9
  adjudicated stale docs (new disagreements adjudicated the same way) and the
  reference's 834,044 tokens. Adopted as the skill's review method if it finds
  all 9 with no more wrong findings at <= ~60% of the tokens. Expected
  ~450-550k tokens, owner-approved 2026-09-23.
  RESULT (recorded after): 553,582 tokens (66% of the reference); 13 findings,
  all verbatim. Adjudication REVERSED two of the D15 rulings (two dated
  session notes whose banners END with "Banner added <date>" - dated, not
  stale; I had read only the top of each banner) and confirmed two stale docs
  the reference missed (the project's living state page, and a state snapshot
  later edited in place). Corrected set: 9.
  Reference 7/9 found + 2 wrong; skim-first 5/9 + 2 wrong; D16 **9/9** + 4
  wrong (3 = rule 3 over-applied to APPENDED dated sections, 1 = a pointer).
  Fails its own bar (more wrong findings; 66% > 60%) - NOT adopted as is. The
  refinement it points to - a dated section appended below a frozen body does
  not make the body living - is untested.

- **D17 - D16 plus one rule, fixed BEFORE its result.** Identical to D16
  (same sweep output, groups, proposed passages, targeted reading, rules 1-5)
  with rule 3 narrowed and one rule added: an in-place edit of a document's
  body after the date in its name makes it living; a section APPENDED with
  its own date (an "Update" heading with its own date, or an appendix that
  says nothing above was rewritten) does NOT make the frozen body above it
  living; and a pointer to
  another page is not itself a contradiction of a fact. Scored against the
  corrected set of 9 (d16/ADJUDICATION.md); new disagreements adjudicated the
  same way, reading every banner to its last line. Adopted as the skill's
  review method if it finds all 9 with <= 2 wrong. ~550k tokens (D16 measured
  553,582), owner-approved 2026-09-23.
  NOTE (before the run): the rule's examples were first written with phrases
  quoted from two of the scored documents; replaced with generic ones. Even
  so, D17's rule was derived from D16's errors on THESE documents, so its
  score here is optimistic - it needs a fresh set of documents before the
  skill states it as measured.
  RESULT (recorded after): 553,434 tokens (66% of the reference); 9 findings,
  all 9 of the corrected set, 0 wrong. One document was never reported by its
  agent (a planning document) - `quotegate check` named it; all
  three local models, all three earlier reviews and a term grep say not
  stale. Meets its bar: ADOPTED as the skill's review method, with the
  optimism caveat above stated in the skill.

- **D18 - D17 on a fresh set, fixed BEFORE its result.** The only unaudited
  documents on this machine that the same 7 facts apply to: the project's 5 docs
  outside docs/ (CLAUDE.md, README.md, ops/systemd/README.md,
  research/out/README.md, .attic/README.md) and 7 of the orchestrator's memory
  notes about the project and the rig. Same facts (re-verified 2026-09-23),
  expansion, prompt, two-GPU tier-3 sweep, and the D17 review prompt word for
  word (one agent). Read-only. Scored by adjudication - by the orchestrator,
  who also wrote the memory notes (stated as a limit); every ruling recorded.
  12 documents can show whether D17's rules transfer, not prove its accuracy.
  ~60-120k tokens, owner-approved 2026-09-23.
  RESULT (recorded after): sweep 9.9 min (2 findings, 6 none, 4 undecided);
  review 79,707 tokens, 4 findings, all verbatim. Adjudicated: 3 stale
  (the project's CLAUDE.md and README.md, one memory note), 1 not stale
  by the rules (a line inside a bullet dated 2026-09-14), 0 missed on a grep
  of the 8 cleared documents. The rules transferred to documents they were not
  refined on; 12 documents are too few to call its accuracy measured.

