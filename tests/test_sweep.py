"""Roster rules, decision policy and budgeted sweeps - scripted fake models and
a fake clock, no GPU."""
import json

import pytest

from quotegate import config, policy
from quotegate.backends import Reply
from quotegate.sweep import choose_tier, plan, sweep

STALE = "Requests officially supports Python 2.7 and 3.4+."
DOC_A = STALE + " It runs great on PyPy. " + "Filler sentence here. " * 40
DOC_B = "Requests supports Python 3.10 and newer. It runs great on PyPy. " + "Filler sentence here. " * 40
ITEMS = [{"id": "a", "text": DOC_A}, {"id": "b", "text": DOC_B}]


def roster_toml(**roles):
    models = {
        "g12": ("gemma", 1.0), "g26": ("gemma", 1.0), "oss": ("gpt-oss", 1.0), "q38": ("qwen", 1.0)}
    return config.parse({
        "models": [{"name": n, "family": f, "s_per_kchar": s, "load_s": 1} for n, (f, s) in models.items()],
        "roles": roles})


# --- roster rules ------------------------------------------------------------------

def test_same_family_tiebreak_is_refused():
    with pytest.raises(ValueError, match="same family"):
        roster_toml(first="g12", second="q38", tiebreak="g26")


def test_cross_family_tiebreak_is_accepted():
    r = roster_toml(first="g12", second="g26", tiebreak="oss", tripwire="q38")
    assert r.role("tiebreak").family == "gpt-oss"


def test_first_is_required_and_roles_must_exist():
    with pytest.raises(ValueError, match="first"):
        roster_toml(second="g26")
    with pytest.raises(ValueError, match="not in"):
        roster_toml(first="nope")


def test_tiebreak_without_second_is_refused():
    with pytest.raises(ValueError, match="second"):
        roster_toml(first="g12", tiebreak="oss")


def test_example_rosters_load():
    for f in ("examples/roster-single-gpu.toml", "examples/roster-two-gpu.toml"):
        config.load(f)


# --- policy ------------------------------------------------------------------------

def test_agreement_is_by_place_in_the_document():
    a = (policy.FIND, "officially supports Python 2.7")
    b = (policy.FIND, "Requests officially supports Python 2.7 and 3.4+.")
    c = (policy.FIND, "It runs great on PyPy.")
    assert policy.agree(a, b, DOC_A)
    assert not policy.agree(a, c, DOC_A)
    assert policy.agree((policy.NONE, None), (policy.NONE, None), DOC_A)


def test_drop_never_agrees_and_never_decides():
    d = (policy.DROP, None)
    assert policy.after_first(d) is None
    assert policy.after_second(d, d, DOC_A) == (None, True)
    assert policy.after_tiebreak(d, d, (policy.NONE, None), DOC_A) is None


def test_tripwire_turns_a_none_into_undecided_only_when_it_fires():
    none = (policy.NONE, None)
    assert policy.after_tripwire(none, (policy.FIND, "x" * 20)) is None
    assert policy.after_tripwire(none, none) == none


# --- planning ----------------------------------------------------------------------

def test_plan_offers_only_the_tiers_the_roster_supports():
    assert set(plan(roster_toml(first="g12"), 10, 5.0)) == {1}
    assert set(plan(roster_toml(first="g12", second="g26", tiebreak="oss", tripwire="q38"), 10, 5.0)) == {1, 2, 3}


def test_choose_tier_picks_the_best_that_fits_with_a_margin():
    # Plans with PLAN_MARGIN (1.3): a 300 s tier needs 390 s of budget, because
    # estimates ran ~30% low under sustained load (19 min predicted, 25.1 real).
    tiers = {1: 100, 2: 300, 3: 500}
    assert choose_tier(tiers, 390) == 2
    assert choose_tier(tiers, 350) == 1
    assert choose_tier(tiers, 50) == 1          # nothing fits: tier 1, items may stay undecided
    with pytest.raises(ValueError):
        choose_tier({1: 100}, 1e9, forced=3)


# --- sweeps with scripted models ---------------------------------------------------

class Scripted:
    """A fake backend answering per item from a script: 'stale' | 'none' | 'fab' | 'down'."""
    def __init__(self, script, clock=None, cost=0.0):
        self.script, self.clock, self.cost, self.calls = script, clock, cost, 0

    def ask(self, model, prompt, **kw):
        self.calls += 1
        if self.clock:
            self.clock.t += self.cost
        doc = "a" if STALE in prompt else "b"
        act = self.script[doc]
        if act == "down":
            from quotegate.backends import BackendError
            raise BackendError("down")
        if act == "stale":
            return Reply(json.dumps({"found": True, "quote": STALE, "why": ""}))
        if act == "fab":
            return Reply(json.dumps({"found": True, "quote": "Requests supports Python 3.6 only", "why": ""}))
        return Reply(json.dumps({"found": False, "quote": "It runs great on PyPy.", "why": ""}))


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def run(scripts, roles, **kw):
    r = roster_toml(**roles)
    fakes = {name: Scripted(s) for name, s in scripts.items()}
    return sweep(r, ITEMS, "{{TEXT}}", backend_for=lambda m: fakes[m.name], clock=Clock(), **kw), fakes


def test_tier1_takes_the_first_model():
    res, _ = run({"g12": {"a": "stale", "b": "none"}}, dict(first="g12"))
    assert res.decisions["a"][0] == policy.FIND and res.decisions["b"][0] == policy.NONE


def test_tier2_agreement_decides_and_disagreement_goes_to_the_tiebreak():
    res, fakes = run({"g12": {"a": "stale", "b": "stale"}, "g26": {"a": "stale", "b": "none"},
                      "oss": {"a": "none", "b": "none"}},
                     dict(first="g12", second="g26", tiebreak="oss"), tier=2)
    assert res.decisions["a"][0] == policy.FIND        # both found it: decided without the tie-break
    assert res.decisions["b"][0] == policy.NONE        # split; tie-break sided with "none"
    assert fakes["oss"].calls == 1                     # tie-break ran ONLY on the split item


def test_a_fabricated_quote_is_a_drop_and_cannot_win_a_vote():
    res, _ = run({"g12": {"a": "fab", "b": "none"}, "g26": {"a": "stale", "b": "none"},
                  "oss": {"a": "fab", "b": "none"}},
                 dict(first="g12", second="g26", tiebreak="oss"), tier=2)
    assert res.decisions["a"] is None                  # one real finding, no agreement: Claude


def test_tier3_tripwire_sends_a_shared_miss_to_claude():
    # Both voters miss the stale claim in "a" (the shared-miss pattern); the
    # eager-prompt tripwire finds it, so "a" is NOT decided "none".
    res, fakes = run({"g12": {"a": "none", "b": "none"}, "g26": {"a": "none", "b": "none"},
                      "oss": {"a": "none", "b": "none"}, "q38": {"a": "stale", "b": "none"}},
                     dict(first="g12", second="g26", tiebreak="oss", tripwire="q38"),
                     tier=3, eager_prompt="{{TEXT}}")
    assert res.decisions["a"] is None
    assert res.decisions["b"][0] == policy.NONE
    assert fakes["q38"].calls == 2


def test_tier3_is_unavailable_without_an_eager_prompt():
    r = roster_toml(first="g12", second="g26", tiebreak="oss", tripwire="q38")
    with pytest.raises(ValueError):
        sweep(r, ITEMS, "{{TEXT}}", tier=3, backend_for=lambda m: None)


def test_a_stage_that_does_not_fit_is_skipped_and_reported():
    # The roster estimates the second stage at ~3 s (load 1 s + 1 s/kchar over
    # two ~1k-char items). The first stage really takes 60 s (30 s per item),
    # so a 61 s budget leaves 1 s: the second stage must be skipped, loudly.
    clock = Clock()
    r = roster_toml(first="g12", second="g26", tiebreak="oss")
    fakes = {n: Scripted({"a": "stale", "b": "none"}, clock, cost=30.0) for n in ("g12", "g26", "oss")}
    res = sweep(r, ITEMS, "{{TEXT}}", budget_s=61, tier=2,
                backend_for=lambda m: fakes[m.name], clock=clock)
    assert any("SKIPPED second" in line for line in res.log)
    assert fakes["g26"].calls == 0
    assert res.decisions["a"][0] == policy.FIND        # tier-1 answers stand


def test_items_past_the_deadline_stay_undecided():
    clock = Clock()
    r = roster_toml(first="g12")
    fake = Scripted({"a": "stale", "b": "none"}, clock, cost=100.0)
    res = sweep(r, ITEMS, "{{TEXT}}", budget_s=50, tier=1, backend_for=lambda m: fake, clock=clock)
    assert fake.calls == 1
    assert res.decisions["b"] is None
    assert any("budget reached" in line for line in res.log)


# --- calibration ------------------------------------------------------------------

def test_calibrated_roster_round_trips_through_toml(tmp_path):
    import tomllib
    from quotegate.calibrate import to_toml
    r = config.load("examples/roster-two-gpu.toml")
    r.models["gpt-oss:20b"].s_per_kchar = 3.33
    again = config.parse(tomllib.loads(to_toml(r)))
    assert again.roles == r.roles
    for name, m in r.models.items():
        n = again.models[name]
        assert (n.family, n.host, n.think, n.num_predict, n.s_per_kchar, n.load_s) == \
               (m.family, m.host, m.think, m.num_predict, m.s_per_kchar, m.load_s)


def test_time_model_uses_load_from_the_first_call_and_median_speed():
    from quotegate.calibrate import time_model

    class Timed:
        def __init__(self):
            self.i = 0

        def ask(self, model, prompt, **kw):
            self.i += 1
            load = 5e9 if self.i == 1 else 0            # 5 s load on the first call only
            return Reply('{"found": false, "quote": "x"}',
                         meta={"total_duration": load + 2e9, "load_duration": load})
    m = config.Model(name="m", family="f")
    items = [{"id": str(k), "text": "x" * 2000} for k in range(3)]   # 2k chars each
    r = time_model(m, items, "{{TEXT}}", backend=Timed())
    assert r["load_s"] == 5.0
    assert r["s_per_kchar"] == 1.0                     # 2 s / 2k chars
    assert r["timed_items"] == 3


def test_savings_footer_is_labelled_an_estimate_and_counts_undecided_in_full():
    from quotegate.sweep import Result, savings_footer
    items = [{"id": "a", "text": "x" * 4000}, {"id": "b", "text": "y" * 4000}, {"id": "c", "text": "z" * 4000}]
    res = Result(1, {"a": None, "b": (policy.NONE, None), "c": (policy.FIND, "zzzz")}, {})
    line = savings_footer(res, items)
    assert "estimate" in line and "not a measurement" in line
    assert "reads ~5k of 12k" in line          # a in full (4k) + c around its quote (1.5k)


# --- one model on several GPUs --------------------------------------------------

def two_host_roster(**roles):
    r = roster_toml(**roles)
    r.models["g12"].hosts = ["h1:1", "h2:2"]
    return r


class HostFake(Scripted):
    def __init__(self, host, *a, **k):
        super().__init__(*a, **k)
        self.host, self.unloaded = host, []

    def unload(self, model):
        self.unloaded.append(model)


def test_a_stage_with_two_hosts_uses_both_and_answers_every_item():
    items = [{"id": "a%d" % i, "text": DOC_A} for i in range(10)]
    fakes = {}

    def backend_for(m):
        fakes[m.host] = HostFake(m.host, {"a": "stale", "b": "none"})
        return fakes[m.host]
    res = sweep(two_host_roster(first="g12"), items, "{{TEXT}}", tier=1,
                backend_for=backend_for, clock=Clock())
    assert set(fakes) == {"h1:1", "h2:2"}
    assert sum(f.calls for f in fakes.values()) == 10          # each item asked once
    assert all(res.decisions[i["id"]][0] == policy.FIND for i in items)
    assert all(f.unloaded == ["g12"] for f in fakes.values())  # every server unloaded
    assert any("across 2 hosts" in line for line in res.log)


def test_estimate_is_shared_across_hosts():
    one = plan(roster_toml(first="g12"), 100, 1.0)[1]
    two = plan(two_host_roster(first="g12"), 100, 1.0)[1]
    assert two == pytest.approx(1 + (one - 1) / 2)             # load time is not shared


def test_two_hosts_still_stop_at_the_deadline():
    clock = Clock()
    items = [{"id": "a%d" % i, "text": DOC_A} for i in range(10)]
    res = sweep(two_host_roster(first="g12"), items, "{{TEXT}}", budget_s=250, tier=1,
                backend_for=lambda m: HostFake(m.host, {"a": "stale", "b": "none"}, clock, cost=100.0),
                clock=clock)
    undecided = sum(1 for d in res.decisions.values() if d is None)
    assert 0 < undecided < 10
    assert any("budget reached" in line for line in res.log)


def test_hosts_parse_from_the_roster():
    r = config.parse({"models": [{"name": "g12", "family": "gemma", "hosts": ["a:1", "b:2"]}],
                      "roles": {"first": "g12"}})
    assert r.role("first").hosts == ["a:1", "b:2"]


def test_calibrate_keeps_backend_and_hosts(tmp_path):
    import tomllib
    from quotegate.calibrate import to_toml
    r = config.parse({"models": [{"name": "g12", "family": "gemma", "backend": "openai",
                                  "hosts": ["a:1", "b:2"]}], "roles": {"first": "g12"}})
    back = config.parse(tomllib.loads(to_toml(r)))
    assert back.role("first").backend == "openai" and back.role("first").hosts == ["a:1", "b:2"]


# --- the plan follows the measured pace ------------------------------------------

def test_a_slow_first_stage_rescales_the_later_stages():
    # Items are ~1k chars and the roster says 1 s/kchar, so each item "should"
    # take ~1 s. They take 2 s. Unscaled, the second stage (10 items, ~10 s +
    # 1 s load) fits in the 12 s left after stage one; at the measured 2x it
    # needs ~21 s and must be skipped, loudly.
    clock = Clock()
    items = [{"id": "a%d" % i, "text": DOC_A} for i in range(10)]
    kc = len(DOC_A) / 1000
    r = roster_toml(first="g12", second="g26")
    fakes = {n: Scripted({"a": "stale", "b": "none"}, clock, cost=2.0 * kc) for n in ("g12", "g26")}
    budget = 1 + 2.0 * kc * 10 + 12          # stage one (load + 2x) plus 12 s
    res = sweep(r, items, "{{TEXT}}", budget_s=budget, tier=2,
                backend_for=lambda m: fakes[m.name], clock=clock)
    import re
    drift = [float(m.group(1)) for line in res.log
             for m in [re.search(r"ran at ([0-9.]+)x the roster's speed", line)] if m]
    assert drift and 1.8 <= drift[0] <= 2.1          # 2x the pace, less the roster's load allowance
    assert any("SKIPPED second" in line for line in res.log)
    assert fakes["g26"].calls == 0


def test_on_log_sees_every_line_as_it_is_written():
    seen = []
    res, _ = run({"g12": {"a": "stale", "b": "none"}}, dict(first="g12"), on_log=seen.append)
    assert seen == res.log and len(seen) >= 3


# --- finishing a stopped sweep ---------------------------------------------------

def test_resume_asks_only_what_is_missing_and_decides_the_same():
    roles = dict(first="g12", second="g26", tiebreak="oss")
    script = {"g12": {"a": "stale", "b": "none"}, "g26": {"a": "stale", "b": "stale"},
              "oss": {"a": "stale", "b": "none"}}
    whole, _ = run(script, roles, tier=2)
    prior = {"a": {"first": {"status": "kept", "answer": {"found": True, "quote": STALE}}},
             "b": {"first": {"status": "kept", "answer": {"found": False, "quote": "It runs great on PyPy."}}}}
    resumed, fakes = run(script, roles, tier=2, prior=prior)
    assert fakes["g12"].calls == 0                      # the first stage is not asked again
    assert fakes["g26"].calls == 2
    assert resumed.decisions == whole.decisions
    assert any("resumed: 2 answers" in line for line in resumed.log)


def test_cli_resume_appends_to_the_votes(tmp_path, monkeypatch):
    from quotegate import cli, sweep as sweep_mod
    items = tmp_path / "items.jsonl"
    items.write_text("\n".join(json.dumps(i) for i in ITEMS) + "\n")
    prompt = tmp_path / "p.txt"; prompt.write_text("{{TEXT}}")
    roster = tmp_path / "r.toml"
    roster.write_text('[[models]]\nname = "g12"\nfamily = "gemma"\n[roles]\nfirst = "g12"\n')
    out = tmp_path / "d.jsonl"
    votes = tmp_path / "d.jsonl.votes.jsonl"
    votes.write_text(json.dumps({"role": "first", "id": "a", "status": "kept",
                                 "answer": {"found": True, "quote": STALE}}) + "\n")
    fake = Scripted({"a": "stale", "b": "none"})
    real = sweep_mod.sweep
    monkeypatch.setattr(sweep_mod, "sweep", lambda *a, **k: real(*a, backend_for=lambda m: fake, **k))
    assert cli.main(["sweep", "--roster", str(roster), "--items", str(items), "--prompt", str(prompt),
                     "--tier", "1", "--out", str(out), "--resume"]) == 0
    assert fake.calls == 1                                # only "b" was asked
    lines = votes.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["id"] == "a"
