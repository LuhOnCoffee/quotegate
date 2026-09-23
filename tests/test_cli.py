"""The CLI must at least parse and answer --help for every command.

Added after a syntax error in cli.py was committed with 53 passing tests: no
test imported the CLI, so nothing noticed (2026-09-22). These run the module
the same way the Claude Code plugin does - `python3 -m quotegate` from src/,
with nothing installed.
"""
import pathlib
import subprocess
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


def qg(*args):
    return subprocess.run([sys.executable, "-m", "quotegate", *args], cwd="/",
                          env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
                          capture_output=True, text=True, timeout=60)


def test_version_runs_without_install():
    r = qg("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("quotegate ")


@pytest.mark.parametrize("cmd", ["run", "sweep", "calibrate", "doctor"])
def test_every_command_answers_help(cmd):
    r = qg(cmd, "--help")
    assert r.returncode == 0, r.stderr
    assert "usage: quotegate " + cmd in r.stdout


def test_sweep_requires_a_budget_or_a_tier():
    r = qg("sweep", "--roster", "x", "--items", "x", "--prompt", "x", "--out", "x")
    assert r.returncode != 0 and "--budget-min" in r.stderr
