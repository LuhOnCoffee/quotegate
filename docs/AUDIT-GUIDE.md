# Running a real documentation audit

The steps below are the ones used on a real 152-document audit (RESULTS.md,
"A real job"), with what each one cost there. The question asked of every
document: *does it state or imply, as current, something that contradicts
these facts? Quote it.*

## 1. Write the facts - and check each one against the source of truth

One line per fact, numbered, each true **today** and each checked against the
code or the running system, not against another document or memory:

    - F1: The service is RUNNING; it has been live since 2026-09-19.
    - F2: ...

Keep a second file saying where each fact was checked (a file and line, a
command and its output). Facts are the only thing the whole audit trusts; a
wrong fact produces a confident wrong audit.

## 2. Expand the facts (a few thousand tokens, once)

    quotegate expand --facts FACTS.txt       # prints a prompt

Answer it yourself or hand it to a subagent - **from the facts alone, never
from the documents being audited** - and save the "- " lines as
`EXPANSION.txt`. It lists what an out-of-date document might still say
("restart the bot before Monday"), which catches staleness that shares no
words with the facts. Measured on corpus v4: local errors 35.6% -> 25.0%.

## 3. Build the items

`items.jsonl`, one `{"id", "text", "facts"}` per document, then attach the
expansion to every item:

    quotegate expand --attach EXPANSION.txt --items items.jsonl --out items_exp.jsonl

Use `bench/prompt_careful_v2.txt` as the prompt. If the documents carry
banners or correction notes, add one line to its "do NOT count" list: text the
document itself marks as superseded or corrected.

## 4. Calibrate on these items, then sweep

    quotegate calibrate --roster roster.toml --items items_exp.jsonl --prompt prompt.txt --write roster-cal.toml
    quotegate sweep --roster roster-cal.toml --items items_exp.jsonl --prompt prompt.txt \
        --eager-prompt bench/prompt_eager.txt --budget-min 120 --out decisions.jsonl

- Calibrate on the job's own items: facts plus expansion make every prompt
  longer, and a roster calibrated elsewhere ran 1.7x slow. The sweep re-plans
  from its measured pace anyway and says so in its live log.
- A model that fits more than one GPU can list `hosts = [...]` in the roster;
  its stage is split across them (measured 1.9x on the first stage).
- If a sweep is stopped or hits its budget, `--resume` finishes it without
  asking anything twice.
- On the real job: 152 documents averaging 12k characters took 113 minutes
  at tier 3 on two GPUs; the two local models disagreed on 70% of them.

## 5. Review what the sweep hands back

`decisions.jsonl` gives each document `finding`, `none` or `undecided`.

- **finding** - read around the quote (and the document's banner) and
  confirm or reject it. On the real job 35 of 40 local findings were
  rejected: sentences true on the day their document was written.
- **undecided** - read the banner (to its last line) and every passage the
  local models proposed (in `votes`); read the whole document only when no
  model proposed anything.
- **none** - skim: grep for the facts' and expansion's terms, read the
  matches with context and the banner.

Put the dated-versus-current rules in the review prompt (they are in the
skill). Without them, two reviews of the same 152 documents disagreed on 6.

Split the review across agents of ~25 documents each. Cost on the real job:
**~3.6k Claude tokens per document** with this method (553k for 152), against
834k when undecided documents were read in full; 80k for a 12-document set.

## 6. Check the report

    quotegate check --report report.json --items items.jsonl

Every quote must be verbatim in the document it is filed under, and every
document must be reported. In 2 of 5 review runs an agent silently
skipped a document; the check named it both times.

## 7. Settle disagreements by reading, and record the rulings

Where two passes (two reviews, or a review and your own grep) disagree, read
the passage in context - every banner to its last line, where its date often
is - and write the ruling and its reason down. Two of the first review's nine
"stale" documents turned out to be dated records whose date sat on the
banner's last line.

## 8. Fix without breaking citations

If other files cite the documents by line number, add each correction on the
same line as the stale sentence (for example `[CORRECTED <date>: ...]`), so no
line number moves. Leave dated records as records.
