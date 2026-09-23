"""Budgeted, staged multi-model sweep: the most accurate result a time budget buys.

Tiers (roles from the roster; see config.py and policy.py):
  1 fast     first model on every item
  2 checked  + second opinion on every item, tie-break only on disagreement
  3 strict   + tripwire (an EAGER prompt) on every item decided "none"

Before each stage, the stage's estimate - roster speed (seconds per 1,000 chars)
times the actual items, plus the model's load time - is compared with the time
left. A stage that no longer fits is SKIPPED AND REPORTED, never silent; within
a stage, items past the deadline stay undecided. Undecided items are Claude's.

It attaches to Ollama instances that are already running and never starts or
kills a server. A model with several `hosts` (the same model served on two
GPUs) runs its stage on all of them at once: one worker per host, each taking
the next item from a shared queue, so a slower card simply does fewer items.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from . import policy
from .backends import Ollama, OpenAICompat
from .worker import DEFAULT_SCHEMA, ask_one

# Rates used to size the CONDITIONAL stages before they run, measured on the
# benchmark (tier 2 disagreement ~35%, "none" after tier 2 ~55%). Replace with
# your own once you have run a sweep on your data.
P_DISAGREE = 0.35
P_NONE = 0.55
# Estimates run LOW under sustained load: calibration on 3 items with cool
# cards predicted 19 min for a sweep that took 25.1 (2026-09-22) - the Quadro
# throttles when hot. Tier choice plans with this margin; the per-item deadline
# still guarantees the budget itself is never overrun.
PLAN_MARGIN = 1.3


def hosts_of(model):
    return list(getattr(model, "hosts", None) or [model.host])


def estimate(model, n_items, kchars_per_item):
    """Load time plus the items' reading time, shared across the model's hosts."""
    return model.load_s + model.s_per_kchar * kchars_per_item * n_items / len(hosts_of(model))


def plan(roster, n_items, kchars):
    """Estimated seconds for each available tier: {1: s, 2: s, 3: s}."""
    first, second = roster.role("first"), roster.role("second")
    tb, trip = roster.role("tiebreak"), roster.role("tripwire")
    out = {1: estimate(first, n_items, kchars)}
    if second:
        t2 = out[1] + estimate(second, n_items, kchars)
        if tb:
            t2 += estimate(tb, n_items * P_DISAGREE, kchars)
        out[2] = t2
        if trip:
            out[3] = t2 + estimate(trip, n_items * P_NONE, kchars)
    return out


def choose_tier(tiers, budget_s, forced=None):
    if forced:
        if forced not in tiers:
            raise ValueError("tier %d needs roles the roster does not define" % forced)
        return forced
    fitting = [t for t, s in tiers.items() if s * PLAN_MARGIN <= budget_s]
    return max(fitting) if fitting else 1


@dataclass
class Result:
    tier: int
    decisions: dict                      # id -> vote or None (undecided)
    votes: dict                          # id -> {role: vote}
    log: list = field(default_factory=list)

    def counts(self):
        c = {"finding": 0, "none": 0, "undecided": 0}
        for d in self.decisions.values():
            c["undecided" if d is None else ("finding" if d[0] == policy.FIND else "none")] += 1
        return c


def sweep(roster, items, careful_prompt, budget_s=float("inf"), tier=None,
          eager_prompt=None, schema=DEFAULT_SCHEMA, backend_for=None,
          clock=time.monotonic, raw_fh=None, on_log=None, prior=None):
    """Run the chosen tier. backend_for(model) -> backend; tests pass fakes.
    on_log(line) is called as each log line is written (the CLI prints them live).
    prior = {id: {role: worker record}} from an earlier run of the SAME sweep:
    those questions are not asked again, so a stopped or budget-capped sweep
    can be finished instead of restarted."""
    backend_for = backend_for or (lambda m: (OpenAICompat(m.host) if m.backend == "openai"
                                             else Ollama(m.host)))
    n = len(items)
    kc = sum(len(i["text"]) for i in items) / max(n, 1) / 1000.0
    tiers = plan(roster, n, kc)
    if 3 in tiers and not eager_prompt:
        del tiers[3]
    t = choose_tier(tiers, budget_s, tier)
    start = clock()
    deadline = start + budget_s
    res = Result(t, {}, {i["id"]: {} for i in items})
    byid = {i["id"]: i for i in items}
    reused = 0
    for iid, roles in (prior or {}).items():
        if iid in byid:
            for role, rec in roles.items():
                res.votes[iid][role] = policy.to_vote(rec, byid[iid]["text"])
                reused += 1

    def say(line):
        res.log.append(line)
        if on_log:
            on_log(line)

    # Measured speed / roster speed, from the stages run so far. The roster's
    # s_per_kchar was calibrated on SOME prompt and cards; a longer prompt
    # (facts + an expansion) or a hot card runs slower - 1.7x on a real job
    # (2026-09-22) - and later stages must be planned at the measured pace.
    drift = [1.0]
    say("%d items, %.1fk chars each; estimates: %s; tier %d"
        % (n, kc, ", ".join("tier %d %.0f min" % (k, v / 60) for k, v in sorted(tiers.items())), t))
    if reused:
        say("resumed: %d answers from the earlier run are reused, not asked again" % reused)

    def stage(role, subset, prompt, sch):
        model = roster.role(role)
        subset = [it for it in subset if role not in res.votes[it["id"]]]
        if not subset:
            return True
        left = deadline - clock()
        need = model.load_s + (estimate(model, len(subset), kc) - model.load_s) * drift[0]
        if subset and need > left:
            say("SKIPPED %s (%s) on %d items: needs ~%.0f min, %.0f left"
                % (role, model.name, len(subset), need / 60, left / 60))
            return False
        backends = [backend_for(replace(model, host=h)) for h in hosts_of(model)]
        queue, lock = list(subset), threading.Lock()
        stopped = []

        def work(backend):
            n = 0
            while True:
                with lock:
                    if not queue:
                        return n
                    if clock() > deadline:
                        if not stopped:
                            stopped.append(True)
                        return n
                    it = queue.pop(0)
                rec = ask_one(backend, model.name, prompt, it, schema=sch,
                              think=model.think, num_predict=model.num_predict)
                vote = policy.to_vote(rec, it["text"])
                with lock:
                    if raw_fh:
                        raw_fh.write(json.dumps({"role": role, **rec}) + "\n")
                    res.votes[it["id"]][role] = vote
                n += 1

        t0 = clock()
        if len(backends) == 1:
            per_host = [work(backends[0])]
        else:
            with ThreadPoolExecutor(max_workers=len(backends)) as pool:
                per_host = list(pool.map(work, backends))
        done = sum(per_host)
        planned = estimate(model, done, kc) - model.load_s
        if done >= 5 and planned > 0:
            ratio = max(0.0, clock() - t0 - model.load_s) / planned
            if abs(ratio - drift[0]) > 0.2 * drift[0]:
                say("%s ran at %.1fx the roster's speed estimate - later stages are planned at %.1fx"
                    % (role, ratio, ratio))
            drift[0] = ratio
        if stopped:
            say("%s: budget reached after %d of %d items - the rest stay undecided"
                % (role, done, len(subset)))
        split = "" if len(backends) == 1 else " across %d hosts (%s)" % (
            len(backends), ", ".join(str(k) for k in per_host))
        say("%s (%s): %d items%s" % (role, model.name, done, split))
        for backend in backends:
            if hasattr(backend, "unload"):
                backend.unload(model.name)
        return True

    stage("first", items, careful_prompt, schema)
    for i in items:
        v = res.votes[i["id"]].get("first")
        res.decisions[i["id"]] = policy.after_first(v) if v else None

    if t >= 2 and stage("second", items, careful_prompt, schema):
        split = []
        for i in items:
            vs = res.votes[i["id"]]
            if "first" in vs and "second" in vs:
                d, needs = policy.after_second(vs["first"], vs["second"], i["text"])
                res.decisions[i["id"]] = d
                if needs:
                    split.append(i)
            else:
                res.decisions[i["id"]] = None
        if split and roster.role("tiebreak"):
            stage("tiebreak", split, careful_prompt, schema)
            for i in split:
                vs = res.votes[i["id"]]
                if "tiebreak" in vs:
                    res.decisions[i["id"]] = policy.after_tiebreak(
                        vs["first"], vs["second"], vs["tiebreak"], i["text"])

    if t >= 3:
        nones = [byid[k] for k, d in res.decisions.items() if policy.needs_tripwire(d)]
        if nones and stage("tripwire", nones, eager_prompt, DEFAULT_SCHEMA):
            for i in nones:
                v = res.votes[i["id"]].get("tripwire")
                if v:
                    res.decisions[i["id"]] = policy.after_tripwire(res.decisions[i["id"]], v)

    c = res.counts()
    say("tier %d | %d items | finding %d | none %d | UNDECIDED %d (Claude reads these) | %.1f min"
        % (t, n, c["finding"], c["none"], c["undecided"], (clock() - start) / 60))
    say(savings_footer(res, items))
    return res


def savings_footer(res, items):
    """An ESTIMATE of document text kept out of Claude's context, labelled as such.

    Undecided items Claude reads in full; a finding costs a look around its
    quote (counted as 1,500 chars); a "none" costs nothing. At ~4 chars per
    token. This is not a measurement of Claude's tokens - that needs the same
    task run both ways (see docs/dev/PLAN.md, milestone 4)."""
    total = read = 0
    for it in items:
        n = len(it["text"])
        total += n
        d = res.decisions.get(it["id"])
        read += n if d is None else (min(n, 1500) if d[0] == policy.FIND else 0)
    kept_out = total - read
    return ("estimate: Claude reads ~%dk of %dk chars (~%dk tokens kept out of context, "
            "%.0f%%) - an estimate, not a measurement" % (read // 1000, total // 1000,
                                                            kept_out // 4000, 100 * kept_out / max(total, 1)))
