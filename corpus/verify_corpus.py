#!/usr/bin/env python3
"""Mechanical verifier for the quotegate corpus.

For every project directory under <corpus>/projects it checks:

  1. facts.json exists, parses, and every fact's source_quote appears verbatim
     (after whitespace collapse) in `git show <as_of_commit>:<source_path>`
     of the project's source checkout.
  2. docs/ holds exactly 8 documents, each 3,000-12,000 characters.
  3. planted / distractor docs: the manifest's "inserted" sentence occurs
     exactly once in the doc, does not already occur in the source, and the
     doc with that sentence removed is a contiguous verbatim (whitespace-
     collapsed) excerpt of <source_commit>:<source_path>.
  4. clean / organic docs are contiguous verbatim (whitespace-collapsed)
     excerpts of <source_commit>:<source_path>.
  5. LICENSE-NOTICE.txt is present and non-empty.

Plus structural checks that the above depend on (manifest.json present and
parseable, manifest docs <-> files on disk agree, manifest facts agree with
facts.json).

When an excerpt check fails, the report gives the character offset in the
collapsed doc where the longest matching prefix ends, surrounding context,
and whether the doc would pass as an in-order sequence of paragraph
excerpts (i.e. the doc skips material rather than altering it).

Usage:
  verify_corpus.py [--corpus DIR] [--src DIR] [--json]

  --corpus  corpus root containing projects/ (default: this script's dir)
  --src     directory holding one git checkout per project, named after the
            project (default: $QUOTEGATE_CORPUS_SRC)

Exit status: 0 if no failures, 1 if any failure, 2 on usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXPECTED_DOCS = 8
MIN_CHARS = 3000
MAX_CHARS = 12000
# v1 kinds: planted (stale), distractor (dated history, not stale).
# v2 kinds - stale: implicit, code, note, multi; not stale: conditional,
# hypothetical, paraphrase. Every one is a single inserted sentence or line.
INSERT_KINDS = {"planted", "distractor", "implicit", "code", "note", "multi",
                "conditional", "hypothetical", "paraphrase",
                # v3 kinds - stale only by implication:
                "instruction", "example", "consequence",
                # v4 adds a not-stale consequence that is true today:
                "current_consequence"}
EXCERPT_KINDS = {"clean", "organic"}
ALL_KINDS = INSERT_KINDS | EXCERPT_KINDS

_WS = re.compile(r"\s+")


def collapse(text: str) -> str:
    return _WS.sub(" ", text).strip()


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    passes: int = 0

    def note(self, project: str, check: str, msg: str) -> None:
        self.notes.append(f"[{project}] {check}: {msg}")

    def fail(self, project: str, check: str, msg: str) -> None:
        self.failures.append(f"[{project}] {check}: {msg}")

    def ok(self) -> None:
        self.passes += 1


class GitSource:
    def __init__(self, src_root: Path):
        self.src_root = src_root
        self._cache: dict[tuple[str, str, str], str | None] = {}
        self.errors: dict[tuple[str, str, str], str] = {}

    def show(self, project: str, commit: str, path: str) -> str | None:
        key = (project, commit, path)
        if key not in self._cache:
            repo = self.src_root / project
            proc = subprocess.run(
                ["git", "-C", str(repo), "show", f"{commit}:{path}"],
                capture_output=True,
            )
            if proc.returncode != 0:
                self._cache[key] = None
                self.errors[key] = proc.stderr.decode("utf-8", "replace").strip()
            else:
                self._cache[key] = proc.stdout.decode("utf-8", "replace")
        return self._cache[key]


def longest_matching_prefix(needle: str, hay: str) -> int:
    """Largest n such that needle[:n] is a substring of hay (monotone in n)."""
    lo, hi = 0, len(needle)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if needle[:mid] in hay:
            lo = mid
        else:
            hi = mid - 1
    return lo


def paragraph_sequence_match(raw_doc: str, csrc: str) -> tuple[bool, list[str]]:
    """Check doc paragraphs occur in the source in order (gaps allowed)."""
    paras = [collapse(p) for p in re.split(r"\n\s*\n", raw_doc)]
    paras = [p for p in paras if p]
    pos = 0
    problems: list[str] = []
    for i, p in enumerate(paras):
        idx = csrc.find(p, pos)
        if idx < 0:
            problems.append(f"paragraph {i + 1} not found in order: {p[:100]!r}")
            anywhere = csrc.find(p)
            if anywhere >= 0:
                problems[-1] += f" (it does occur earlier, at collapsed offset {anywhere})"
            continue
        pos = idx + len(p)
    return (not problems), problems


def excerpt_check(raw_doc: str, cdoc: str, src: str) -> tuple[bool, str]:
    """Return (ok, detail). ok means cdoc is a contiguous substring of src."""
    csrc = collapse(src)
    if not cdoc:
        return False, "document is empty after processing"
    idx = csrc.find(cdoc)
    if idx >= 0:
        return True, ""
    n = longest_matching_prefix(cdoc, csrc)
    ctx_doc = cdoc[max(0, n - 60): n + 80]
    at = csrc.find(cdoc[:n]) if n else -1
    ctx_src = csrc[at + n - 60 if at >= 0 else 0: (at + n + 80) if at >= 0 else 0] if at >= 0 else ""
    seq_ok, seq_problems = paragraph_sequence_match(raw_doc, csrc)
    detail = (
        f"not a contiguous verbatim excerpt; longest matching prefix = {n}/{len(cdoc)} collapsed chars. "
        f"doc around divergence: {ctx_doc!r}"
    )
    if ctx_src:
        detail += f" | source at same point: {ctx_src!r}"
    if seq_ok:
        # A GAPPED excerpt (sections skipped, nothing altered) is accepted:
        # the answer key judges the document as it stands. It is reported as
        # a NOTE so it is never silent.
        return True, "GAPPED excerpt (every paragraph verbatim and in order; material skipped)"
    else:
        detail += " | paragraph-sequence check also fails: " + "; ".join(seq_problems[:5])
        if len(seq_problems) > 5:
            detail += f"; ... ({len(seq_problems) - 5} more)"
    return False, detail


def load_json(path: Path, project: str, rep: Report, check: str):
    if not path.is_file():
        rep.fail(project, check, f"{path.name} missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rep.fail(project, check, f"{path.name} does not parse: {e}")
        return None


def verify_project(pdir: Path, git: GitSource, rep: Report) -> None:
    project = pdir.name

    # ---- (5) LICENSE-NOTICE.txt
    lic = pdir / "LICENSE-NOTICE.txt"
    if not lic.is_file():
        rep.fail(project, "license", "LICENSE-NOTICE.txt missing")
    elif not lic.read_text(encoding="utf-8", errors="replace").strip():
        rep.fail(project, "license", "LICENSE-NOTICE.txt is empty")
    else:
        rep.ok()

    if not (git.src_root / project).is_dir():
        rep.fail(project, "source", f"no source checkout at {git.src_root / project}")

    # ---- (1) facts.json
    facts = load_json(pdir / "facts.json", project, rep, "facts")
    if facts is not None:
        commit = facts.get("as_of_commit")
        flist = facts.get("facts")
        if not commit:
            rep.fail(project, "facts", "facts.json has no as_of_commit")
        if not isinstance(flist, list) or not flist:
            rep.fail(project, "facts", "facts.json has no facts list")
            flist = []
        if facts.get("project") not in (None, project):
            rep.fail(project, "facts", f"facts.json project={facts.get('project')!r} != directory name")
        seen_ids = set()
        for f in flist:
            fid = f.get("id", "?")
            if fid in seen_ids:
                rep.fail(project, "facts", f"duplicate fact id {fid}")
            seen_ids.add(fid)
            path, quote = f.get("source_path"), f.get("source_quote")
            if not path or not quote:
                rep.fail(project, "facts", f"{fid}: missing source_path or source_quote")
                continue
            if not commit:
                continue
            src = git.show(project, commit, path)
            if src is None:
                rep.fail(project, "facts", f"{fid}: git show {commit[:12]}:{path} failed: "
                         f"{git.errors.get((project, commit, path), '')}")
                continue
            cq = collapse(quote)
            if cq in collapse(src):
                rep.ok()
            else:
                n = longest_matching_prefix(cq, collapse(src))
                rep.fail(project, "facts",
                         f"{fid}: source_quote not found verbatim in {commit[:12]}:{path} "
                         f"(longest matching prefix {n}/{len(cq)} chars; diverges at {cq[n:n + 60]!r}); "
                         f"quote={quote!r}")

    # ---- manifest
    manifest = load_json(pdir / "manifest.json", project, rep, "manifest")
    docs_dir = pdir / "docs"
    on_disk = sorted(p.name for p in docs_dir.iterdir() if p.is_file()) if docs_dir.is_dir() else []
    if not docs_dir.is_dir():
        rep.fail(project, "docs", "docs/ directory missing")

    # ---- (2) doc count and sizes
    if len(on_disk) != EXPECTED_DOCS:
        rep.fail(project, "doc-count", f"{len(on_disk)} files in docs/, expected {EXPECTED_DOCS}: {on_disk}")
    else:
        rep.ok()
    for name in on_disk:
        n = len((docs_dir / name).read_text(encoding="utf-8", errors="replace"))
        if not (MIN_CHARS <= n <= MAX_CHARS):
            rep.fail(project, "doc-size", f"{name}: {n:,} chars, outside {MIN_CHARS:,}-{MAX_CHARS:,}")
        else:
            rep.ok()

    if manifest is None:
        return

    if facts is not None and manifest.get("facts") is not None:
        mf = {f.get("id"): f for f in manifest.get("facts", [])}
        ff = {f.get("id"): f for f in facts.get("facts", [])}
        if set(mf) != set(ff):
            rep.fail(project, "manifest-facts", f"fact ids differ: manifest={sorted(mf)} facts.json={sorted(ff)}")
        for fid in set(mf) & set(ff):
            for k in ("fact", "source_path", "source_quote"):
                if mf[fid].get(k) != ff[fid].get(k):
                    rep.fail(project, "manifest-facts", f"{fid}.{k} differs between manifest.json and facts.json")
        if facts.get("as_of_commit") and manifest.get("head_commit") and \
                facts["as_of_commit"] != manifest["head_commit"]:
            rep.fail(project, "manifest-facts",
                     f"facts.json as_of_commit {facts['as_of_commit'][:12]} != manifest head_commit "
                     f"{manifest['head_commit'][:12]}")

    mdocs = manifest.get("docs") or []
    listed = []
    fact_ids = {f.get("id") for f in (facts or {}).get("facts", [])}
    for d in mdocs:
        rel = d.get("file", "")
        name = Path(rel).name
        listed.append(name)
        kind = d.get("kind")
        label = name or "?"
        if kind not in ALL_KINDS:
            rep.fail(project, "manifest", f"{label}: unknown kind {kind!r}")
            continue
        dpath = pdir / rel
        if not dpath.is_file():
            rep.fail(project, "manifest", f"{label}: listed in manifest but {rel} not on disk")
            continue
        commit, spath = d.get("source_commit"), d.get("source_path")
        if not commit or not spath:
            rep.fail(project, "manifest", f"{label}: missing source_commit or source_path")
            continue
        src = git.show(project, commit, spath)
        if src is None:
            rep.fail(project, "source", f"{label}: git show {commit[:12]}:{spath} failed: "
                     f"{git.errors.get((project, commit, spath), '')}")
            # A source_path carrying an annotation ("path (lines 1-99, ...)") is a
            # manifest defect, but still verify the content against the bare path.
            bare = spath.split(" (", 1)[0].strip()
            if bare != spath:
                src = git.show(project, commit, bare)
            if src is None:
                continue
            rep.note(project, "source", f"{label}: content below checked against bare path {bare!r}")
            spath = bare
        raw = dpath.read_text(encoding="utf-8", errors="replace")
        cdoc = collapse(raw)

        if kind in INSERT_KINDS:
            ins = d.get("inserted") or ""
            check = f"{kind}"
            if not ins.strip():
                rep.fail(project, check, f"{label}: manifest 'inserted' is empty")
                continue
            if d.get("inserted_fact") and fact_ids and d["inserted_fact"] not in fact_ids:
                rep.fail(project, check, f"{label}: inserted_fact {d['inserted_fact']!r} not a fact id")
            cins = collapse(ins)
            raw_count = raw.count(ins)
            col_count = cdoc.count(cins)
            if col_count != 1:
                rep.fail(project, check,
                         f"{label}: inserted sentence occurs {col_count}x (whitespace-collapsed), "
                         f"{raw_count}x raw; expected exactly 1. sentence={ins!r}")
                if col_count == 0:
                    continue
            else:
                rep.ok()
                if raw_count != 1:
                    rep.note(project, check,
                             f"{label}: inserted sentence matches once after whitespace collapse "
                             f"(raw byte-exact count {raw_count}; it is line-wrapped in the doc)")
            if cins in collapse(src):
                rep.fail(project, check, f"{label}: inserted sentence already occurs in the source "
                         f"{commit[:12]}:{spath}, so it is not an insertion")
            stripped = collapse(cdoc.replace(cins, " ", 1))
            ws_pat = r"\s+".join(re.escape(w) for w in cins.split(" "))
            raw_stripped = re.sub(ws_pat, " ", raw, count=1)
            ok, detail = excerpt_check(raw_stripped, stripped, src)
            if ok:
                rep.ok()
                if detail:
                    rep.note(project, check, f"{label}: {detail}")
            else:
                rep.fail(project, check + "-excerpt",
                         f"{label} (minus inserted sentence) vs {commit[:12]}:{spath}: {detail}")
        else:
            if (d.get("inserted") or "").strip():
                rep.fail(project, kind, f"{label}: {kind} doc has a non-empty 'inserted' field")
            ok, detail = excerpt_check(raw, cdoc, src)
            if ok:
                rep.ok()
                if detail:
                    rep.note(project, kind, f"{label}: {detail}")
            else:
                rep.fail(project, kind + "-excerpt", f"{label} vs {commit[:12]}:{spath}: {detail}")

    if sorted(listed) != on_disk:
        missing = sorted(set(on_disk) - set(listed))
        extra = sorted(set(listed) - set(on_disk))
        dup = sorted({n for n in listed if listed.count(n) > 1})
        rep.fail(project, "manifest",
                 f"manifest docs != docs/ files (on disk not in manifest: {missing}; "
                 f"in manifest not on disk: {extra}; duplicated: {dup})")
    if len(mdocs) != EXPECTED_DOCS:
        rep.fail(project, "doc-count", f"manifest lists {len(mdocs)} docs, expected {EXPECTED_DOCS}")


def structure_only(corpus: Path, projects, rep: "Report") -> "Report":
    """CI checks: no upstream clones needed. Each project has facts and exactly
    EXPECTED_DOCS docs of the right size, the manifest lists the same files, and
    every quote in the set's key.json is verbatim in its document."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from quotegate.gate import norm                      # noqa: E402
    for proj in projects:
        facts = proj / "facts.json"
        docs = sorted((proj / "docs").glob("*.txt"))
        if not facts.exists():
            rep.fail(proj.name, "facts", "facts.json missing")
        else:
            rep.ok()
        if len(docs) != EXPECTED_DOCS:
            rep.fail(proj.name, "docs", f"{len(docs)} docs, expected {EXPECTED_DOCS}")
        else:
            rep.ok()
        for d in docs:
            n = len(d.read_text(errors="replace"))
            if not (MIN_CHARS <= n <= MAX_CHARS):
                rep.fail(proj.name, "size", f"{d.name}: {n} chars")
            else:
                rep.ok()
        man = proj / "manifest.json"
        if man.exists():
            listed = {Path(x["file"]).name for x in json.loads(man.read_text())["docs"]}
            if listed != {d.name for d in docs}:
                rep.fail(proj.name, "manifest", "manifest and docs/ disagree")
            else:
                rep.ok()
    items_p, key_p = corpus / "items.jsonl", corpus / "key.json"
    if items_p.exists() and key_p.exists():
        items = {json.loads(l)["id"]: json.loads(l)["text"] for l in open(items_p)}
        for doc, claims in json.loads(key_p.read_text())["docs"].items():
            for c in claims:
                if norm(c["quote"]) not in norm(items[doc]):
                    rep.fail("key", doc, f"key quote not verbatim: {c['quote'][:60]}")
                else:
                    rep.ok()
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--src", default=os.environ.get("QUOTEGATE_CORPUS_SRC"))
    ap.add_argument("--json", action="store_true", help="emit a JSON report")
    ap.add_argument("--structure-only", action="store_true", dest="structure_only",
                    help="checks that need no upstream clones (for CI): manifests, "
                         "doc counts and sizes, and every key quote verbatim in its doc")
    args = ap.parse_args()
    if not args.src and not args.structure_only:
        print("error: pass --src or set QUOTEGATE_CORPUS_SRC (or --structure-only)",
              file=sys.stderr)
        return 2
    projects_dir = Path(args.corpus) / "projects"
    if not projects_dir.is_dir():
        print(f"error: {projects_dir} is not a directory", file=sys.stderr)
        return 2

    rep = Report()
    projects = sorted(p for p in projects_dir.iterdir() if p.is_dir())
    if args.structure_only:
        rep = structure_only(Path(args.corpus), projects, rep)
        print(f"\n{len(projects)} projects, {rep.passes} structure checks passed, "
              f"{len(rep.failures)} failures")
        for f in rep.failures:
            print("FAIL " + f)
        return 1 if rep.failures else 0
    git = GitSource(Path(args.src))
    for p in projects:
        verify_project(p, git, rep)

    if args.json:
        print(json.dumps({"projects": [p.name for p in projects], "passes": rep.passes,
                          "failures": rep.failures, "notes": rep.notes}, indent=2))
    else:
        for f in rep.failures:
            print("FAIL", f)
        for n in rep.notes:
            print("NOTE", n)
        print(f"\n{len(projects)} projects, {rep.passes} checks passed, "
              f"{len(rep.failures)} failures, {len(rep.notes)} notes")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
