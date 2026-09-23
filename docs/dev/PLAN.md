# quotegate — plan

**Verified local offload for Claude Code.** Claude orchestrates; local models do
high-volume narrow document questions; every local answer must carry an exact
quote that is mechanically checked against the source, and whatever the local
models cannot settle is handed back to Claude. The project's evidence is an
open, answer-keyed benchmark and a budgeted multi-model sweep measured on it.

Origin: the `local-offload` Claude Code skill (2026-09-21), measured on a
private 60-document corpus. Nothing from that corpus ships here.

## Decisions (2026-09-21, by the owner)

| decision | choice |
|---|---|
| name | **quotegate** (PyPI and npm free; two unrelated 0-star GitHub repos use the word for sales quotes) |
| public corpus | **real open-source docs with planted stale claims** |
| license | **Apache-2.0** |
| first milestone | **new local repo, corpus first**; nothing is pushed to GitHub until the owner says so |
| git identity | the owner's GitHub no-reply address (a private email blocks pushes: GH007) |
| prompts (2026-09-22) | **frozen** for the benchmark (`prompt_careful`, `prompt_careful_v2`, `prompt_eager`); any improvement is a separately labelled v3 experiment, never tuned on the corpus it is reported on |
| publishing (2026-09-22) | **nothing pushed until the owner has reviewed README/RESULTS**; then a PRIVATE GitHub repo first |
| skill vs repo (2026-09-22) | **the repo is the source of truth**; `~/.claude/skills/local-offload` gets bug fixes only until the plugin built from this repo replaces it |

## Positioning (from the 2026-09-21 prior-art survey)

- Plain "Claude + Ollama saves tokens" is crowded (~10 small MCP servers and
  skills) and none of them validates answers or publishes an accuracy number.
  We lead with the trust layer, not with savings.
- Closest prior art, credited in the README: Minions (HazyResearch, same
  architecture, citations not mechanically checked), LangExtract (source
  grounding, fuzzy by default), claude-ollama-skills (mechanical checks for dev
  chores), token_save_mcp (the hook that makes delegation actually happen),
  FrugalGPT / RouteLLM / AutoMix (cascades).
- Novel as a packaged combination: exact-quote gate wired into routing; an
  answer-keyed benchmark with intervals; a budgeted cross-family cascade with a
  different-prompt tripwire for shared misses; the Ollama findings (silent
  truncation to ~half of num_ctx; /api/generate + schema disables reasoning).
- Say "whitespace- and emphasis-normalised exact match", never "no
  hallucinations". Measure Claude tokens against a Claude-only baseline before
  claiming savings.
- No "Claude"/"Anthropic" in the name; "a plugin for Claude Code" in text; a
  not-affiliated disclaimer; never touch Claude credentials, never route through
  a user's subscription, never train on Claude outputs.

## Milestone 1 — the public corpus (current)

The task stays the one the method was measured on, generalised: *given the
CURRENT FACTS about a project, does this document state, as current, something
that contradicts them? Quote it.*

1. **Sources.** Permissively licensed projects with long documentation
   histories and version facts that changed (minimum Python, CLI names,
   defaults, config file names, deprecations). Record project, license, tag and
   path for every document in `corpus/SOURCES.md`; keep the licenses' notice
   requirements.
2. **Facts.** For each project, 3-6 current facts taken from its LATEST docs,
   each with a verbatim supporting quote from those docs (so the facts are
   themselves checkable).
3. **Documents.** Three kinds, roughly balanced:
   - *organic stale*: older-version docs that contradict the current facts
     naturally (realistic prose, key found by keyers);
   - *planted*: current docs with one stale sentence inserted (key known by
     construction), plus near-miss **distractors** - dated history that must
     NOT count ("in 2.0, Python 2.6 was still supported"), which is exactly
     where the private benchmark's shared misses came from;
   - *clean*: current docs, no plant.
4. **Key.** Double-keyed by two independent Claude agents plus the planting
   record; every key quote validated; disagreements resolved and logged;
   borderline rulings recorded with reasons.
5. **Rerun** every configuration from the private benchmark; publish per-item
   JSONL with model digests, Ollama version, num_ctx and think settings.

## Milestone 1b - corpus v2: harder items (current)

Corpus v1 (64 docs) is too easy to rank the good configurations: every one of
them scored 92%+ with overlapping intervals, and the tripwire added nothing
because no miss was shared by all models (RESULTS.md). The private corpus, where
it mattered, was full of SUBTLE staleness. v2 adds items of the kinds that
caused real misses:
  - implicit claims (a stale fact implied by an instruction or example, not
    stated: "run `poetry shell` to activate the environment");
  - stale statements inside code blocks and config examples;
  - present-tense banners with a date in them ("2026-09-11: THE SERVICE IS
    STOPPED") - the pattern every model misread as history;
  - claims corrected elsewhere in the same doc (explicitly and implicitly);
  - conditionals and hypotheticals that must NOT count;
  - multi-fact documents where only one of several claims is stale.
Keep v1 as-is (published, pinned); v2 is a separate set with its own key, and
the headline table reports both.

## Later milestones

2. Core library + CLI: backend interface (Ollama first, OpenAI-compatible
   second), config-driven roster with roles and model families, `calibrate`,
   `doctor` (live-checks the truncation and reasoning traps), `sweep --budget`,
   `bench`, unit tests + GPU-free CI with recorded fixtures.
3. Claude Code plugin: plugin.json + marketplace.json, generalised SKILL.md,
   one slash command, an opt-in large-read hook, a savings/rejections footer.
4. Claude-token baseline and a head-to-head with MinionS on the corpus.
5. Optional MCP server over the same core.
