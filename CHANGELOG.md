# Changelog

All notable changes. Benchmark results live in RESULTS.md; the reasoning
behind each measured design is in DECISIONS.md.

## 0.0.4 - 2026-09-23 (pre-release)

- The skill's review of undecided items reads the banner and the passages the
  local models proposed (from the `votes` field) instead of the whole
  document, with written rules for "dated record or current claim?". On a
  real 152-document audit: every stale document found, none wrong, 66% of the
  Claude tokens of full reads (one job; the rules were refined on it).

- A roster model can list several `hosts` (the same model on several GPUs);
  its sweep stage is split across them, one worker per host pulling from a
  shared queue, and its time estimate is divided accordingly. On the
  benchmark rig this lets the first stage use the idle Quadro: measured 1.9x
  faster on 30 real documents (342 s -> 182 s), 29 of 30 decisions the same.
- `calibrate` no longer drops a model's `backend` or `hosts` when it writes
  the calibrated roster.
- The sweep re-plans from its measured pace: after each stage it compares
  wall time with the roster's estimate, logs the ratio when it moves by more
  than 20%, and plans later stages at that pace - so a stage that no longer
  fits is skipped openly instead of running into the deadline. On a real job
  (long prompts: facts plus an expansion) the first stage ran at 1.7x the
  roster's estimate.
- `quotegate sweep` prints its log live instead of only at the end.
- `quotegate sweep --resume` finishes a stopped or budget-capped sweep: it
  reuses the answers already in OUT.votes.jsonl and asks only what is missing.

## 0.0.3 - 2026-09-22 (pre-release)

- `quotegate expand`: prints the measured fact-expansion prompt, and attaches
  the answer to every item's facts; the skill runs it before a sweep when the
  facts describe changes.
  Measured on corpus v4: local errors 35.6% -> 25.0%; quotegate + skim 57 ->
  59 of 64 at the same Claude-token cost (one run each).

## 0.0.2 - 2026-09-22 (pre-release)

- `quotegate check`: the quote gate applied to a finished report. Every
  finding is checked against the document it is filed under; a real quote
  filed under the wrong document is named MISFILED with the document it
  belongs to. The skill now makes it the last step before reporting.
- Corpus v4 (consequence-heavy implied staleness, single-keyed) and the
  measured effect of expanding facts into what an out-of-date document might
  say (RESULTS.md).
- Every Claude token arm re-run on Claude Opus 5.5; each arm file records its
  model and `bench/check_claims.py` enforces it.
- `bench/replay_sweep.py`: tiers 1-3 replayed from a live sweep's votes.

## 0.0.1 - 2026-09-22 (pre-release)

- The quote gate, the staged cascade (first / second opinion / cross-family
  tie-break / eager-prompt tripwire), budgeted tier selection, `run`,
  `sweep`, `calibrate`, `doctor`, `skim`.
- Ollama and OpenAI-compatible backends, with the silent-failure defences
  (context truncation, reasoning disabled by /api/generate, answers written
  into the thinking channel, runaway reasoning).
- Claude Code plugin: skill, opt-in large-read nudge hook.
- Public corpora v1-v3 with blind double-keyed answer keys.
