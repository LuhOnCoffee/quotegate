#!/usr/bin/env python3
"""PreToolUse hook on Read: an OPT-IN nudge when Claude is about to read a large
file in full. It never blocks a read and it never fails a read.

Off unless QUOTEGATE_NUDGE=1 is set in the environment Claude Code runs in.
Threshold: QUOTEGATE_NUDGE_LINES (default 400). A read with an explicit
offset/limit is already targeted and is left alone.

Why a hook at all: an offload tool the model has to REMEMBER to use tends not
to be used (token_save_mcp's README: "the agent forgets to use it"; a
controlled A/B on another offload plugin found no reliable savings
unattended). A nudge at the moment of a large read is where the decision is
actually made. It stays a suggestion: the right call for one file you need to
understand is to read it.
"""
import json
import os
import sys


def decide(event, env):
    """Returns the hook's stdout payload (dict) or None for 'say nothing'."""
    if env.get("QUOTEGATE_NUDGE") != "1":
        return None
    if event.get("tool_name") != "Read":
        return None
    ti = event.get("tool_input") or {}
    if ti.get("offset") or ti.get("limit"):
        return None
    path = ti.get("file_path") or ""
    try:
        limit = int(env.get("QUOTEGATE_NUDGE_LINES", "400"))
        with open(path, "rb") as fh:
            lines = sum(1 for _ in fh)
    except (OSError, ValueError):
        return None
    if lines < limit:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            "quotegate: %s is %d lines. If you are asking the same narrow, quotable "
            "question of many files like this one (does it state X? which mention Y? "
            "classify with evidence), the quotegate skill can have local models answer "
            "with quote-checked evidence and return only what they cannot settle. "
            "If you need to understand this file itself, read it." % (os.path.basename(path), lines))}}


def main():
    try:
        event = json.load(sys.stdin)
        out = decide(event, os.environ)
    except Exception:                                  # noqa: BLE001 - never break a read
        out = None
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
