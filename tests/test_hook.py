"""The large-read nudge: opt-in, never blocks, never breaks a read."""
import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).resolve().parents[1] / "hooks" / "large_read_nudge.py"


def call(event, env):
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event) if isinstance(event, dict) else event,
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", **env}, timeout=20)
    return r


def big(tmp_path, n=500):
    p = tmp_path / "big.md"
    p.write_text("line\n" * n)
    return str(p)


def ev(path, **extra):
    return {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path, **extra}}


def test_off_by_default(tmp_path):
    r = call(ev(big(tmp_path)), {})
    assert r.returncode == 0 and r.stdout == ""


def test_nudges_a_large_whole_file_read_when_enabled(tmp_path):
    r = call(ev(big(tmp_path)), {"QUOTEGATE_NUDGE": "1"})
    assert r.returncode == 0
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert "500 lines" in out["additionalContext"]
    assert "permissionDecision" not in out                 # a nudge, never a block


def test_small_files_and_targeted_reads_are_left_alone(tmp_path):
    assert call(ev(big(tmp_path, 50)), {"QUOTEGATE_NUDGE": "1"}).stdout == ""
    assert call(ev(big(tmp_path), offset=100, limit=50), {"QUOTEGATE_NUDGE": "1"}).stdout == ""


def test_threshold_is_configurable(tmp_path):
    assert call(ev(big(tmp_path, 50)), {"QUOTEGATE_NUDGE": "1", "QUOTEGATE_NUDGE_LINES": "40"}).stdout != ""


def test_garbage_input_or_missing_file_never_breaks_the_read(tmp_path):
    for bad in ("not json", json.dumps({"tool_name": "Read"})):
        r = call(bad, {"QUOTEGATE_NUDGE": "1"})
        assert r.returncode == 0 and r.stdout == ""
    r = call(ev(str(tmp_path / "nope.md")), {"QUOTEGATE_NUDGE": "1"})
    assert r.returncode == 0 and r.stdout == ""
