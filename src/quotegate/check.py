"""Check a finished report - usually Claude's own - with the same gate as the local models.

    quotegate check --report report.json --items items.jsonl
    quotegate check --report report.json --docs path/to/docs/

The gate stops a local model from filing an invented quote. The same failure
happens one step later, in whoever writes the final report: on the benchmark,
Claude read 64 documents correctly and then filed three right quotes under the
document BEFORE each one's own (black-d06's sentence reported as black-d05's,
and so on), scoring 60/64 on work it had done right. Nothing in the report
looked wrong.

So every finding in the report is checked against the document it is filed
under. A quote that is not there is named, and if it IS in another document,
that document is named too - a misfiled finding is fixed by moving it, not by
re-reading.
"""
import json
import pathlib

from .gate import MIN_QUOTE, norm, validate

OK, SHORT, NOT_HERE, MISFILED, NO_DOC = "ok", "too-short", "not-verbatim", "misfiled", "unknown-id"


def load_report(path):
    """[{id, found, quote}] from a JSON list, a JSON {"docs": [...]}, or JSONL."""
    text = pathlib.Path(path).read_text()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = [json.loads(l) for l in text.splitlines() if l.strip()]
    if isinstance(data, dict):
        data = data.get("docs") or data.get("findings") or []
    return [dict(e, found=e.get("found", bool(e.get("quote")))) for e in data]


def load_items(path):
    return {r["id"]: r["text"] for r in map(json.loads, open(path)) if r.get("id")}


def load_docs(root, exts=(".txt", ".md", ".rst")):
    """id = file name without extension, from every file under root."""
    out = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        if p.is_file() and p.suffix in exts:
            out[p.stem] = p.read_text(errors="replace")
    return out


def check(entries, texts):
    """One result per finding, plus report-level problems.

    Returns (results, problems): results is [{id, status, quote, elsewhere}];
    problems lists ids reported twice and documents the report never covers."""
    results, seen, dup = [], set(), []
    for e in entries:
        i = e.get("id")
        if i in seen:
            dup.append(i)
        seen.add(i)
        if not e.get("found"):
            continue
        q = e.get("quote") or ""
        if i not in texts:
            results.append({"id": i, "status": NO_DOC, "quote": q, "elsewhere": []})
            continue
        ok, _ = validate({"quote": q}, texts[i])
        if ok:
            results.append({"id": i, "status": OK, "quote": q, "elsewhere": []})
            continue
        if len(norm(q)) < MIN_QUOTE:
            results.append({"id": i, "status": SHORT, "quote": q, "elsewhere": []})
            continue
        nq = norm(q)
        elsewhere = [j for j, t in texts.items() if j != i and nq in norm(t)]
        results.append({"id": i, "status": MISFILED if elsewhere else NOT_HERE,
                        "quote": q, "elsewhere": elsewhere})
    problems = []
    if dup:
        problems.append("reported more than once: " + ", ".join(sorted(set(dup))))
    missing = sorted(set(texts) - seen)
    if missing and len(missing) < len(texts):
        problems.append("never reported: " + ", ".join(missing))
    return results, problems


def render(results, problems):
    bad = [r for r in results if r["status"] != OK]
    lines = ["%d findings checked: %d verbatim in their own document, %d not"
             % (len(results), len(results) - len(bad), len(bad))]
    for r in bad:
        q = norm(r["quote"])
        q = q if len(q) <= 70 else q[:67] + "..."
        if r["status"] == MISFILED:
            lines.append("  MISFILED     %s: the quote is in %s, not here - move it   \"%s\""
                         % (r["id"], ", ".join(r["elsewhere"]), q))
        elif r["status"] == SHORT:
            lines.append("  TOO SHORT    %s: quote under %d chars cannot be checked - quote the whole line   \"%s\""
                         % (r["id"], MIN_QUOTE, q))
        elif r["status"] == NO_DOC:
            lines.append("  UNKNOWN ID   %s: no such document   \"%s\"" % (r["id"], q))
        else:
            lines.append("  NOT VERBATIM %s: not in this document or any other - re-read and quote exactly   \"%s\""
                         % (r["id"], q))
    lines += ["  " + p for p in problems]
    return lines
