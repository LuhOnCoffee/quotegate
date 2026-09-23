"""The roster: which models exist, where they are served, how to call them, how
fast they are, and which role each plays in a sweep. Nothing about models is
hard-coded anywhere else.

    [[models]]
    name        = "gemma4:12b-it-qat"      # the backend's model tag
    family      = "gemma"                  # used to enforce a cross-family tie-break
    host        = "127.0.0.1:11434"
    hosts       = ["127.0.0.1:11434", "127.0.0.1:11435"]   # optional: the same model on
                                           # several GPUs; its stage is split across them
    backend     = "ollama"                 # or "openai" (llama.cpp / LM Studio / vLLM)
    think       = "off"                    # set it explicitly: defaults differ per model
    num_predict = 4096
    s_per_kchar = 0.83                     # seconds per 1,000 chars of item text (calibrate)
    load_s      = 60                       # seconds to load the model (calibrate)

    [roles]
    first    = "gemma4:12b-it-qat"         # required
    second   = "gemma4:26b-a4b-it-qat"     # optional: enables tier 2
    tiebreak = "gpt-oss:20b"               # optional; must be a DIFFERENT family
    tripwire = "qwen3.8:27b"               # optional: enables tier 3 (needs an eager prompt)

A tie-breaker from the same family as the model it breaks ties for made things
worse on the benchmark (gemma4:26b behind gemma4:12b: 12.5% wrong vs 8.2% with
gpt-oss), because related models make related mistakes. validate() refuses it.
"""
import tomllib
from dataclasses import dataclass, field

ROLES = ("first", "second", "tiebreak", "tripwire")


@dataclass
class Model:
    name: str
    family: str
    host: str = "127.0.0.1:11434"
    think: object = None
    backend: str = "ollama"            # or "openai" for /v1/chat/completions
    hosts: list = field(default_factory=list)   # several servers for one model: split its stage
    num_predict: int = 4096
    s_per_kchar: float = 1.0
    load_s: float = 60.0


@dataclass
class Roster:
    models: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)

    def role(self, r):
        n = self.roles.get(r)
        return self.models[n] if n else None


def _think(v):
    return {"on": True, "off": False, "auto": None}.get(v, v)


def parse(data):
    models = {}
    for m in data.get("models", []):
        if "name" not in m or "family" not in m:
            raise ValueError("every [[models]] entry needs name and family")
        mm = Model(**{k: v for k, v in m.items() if k in Model.__dataclass_fields__})
        mm.think = _think(m.get("think", "auto"))
        models[mm.name] = mm
    roster = Roster(models, dict(data.get("roles", {})))
    validate(roster)
    return roster


def load(path):
    with open(path, "rb") as fh:
        return parse(tomllib.load(fh))


def validate(roster):
    r = roster.roles
    unknown = set(r) - set(ROLES)
    if unknown:
        raise ValueError("unknown role(s): %s" % ", ".join(sorted(unknown)))
    if not r.get("first"):
        raise ValueError("roles.first is required")
    for role, name in r.items():
        if name not in roster.models:
            raise ValueError("roles.%s names %r, which is not in [[models]]" % (role, name))
    if r.get("tiebreak") and not r.get("second"):
        raise ValueError("a tiebreak needs a second opinion to break ties between")
    if r.get("tiebreak"):
        tb = roster.models[r["tiebreak"]].family
        for other in ("first", "second"):
            if roster.models[r[other]].family == tb:
                raise ValueError(
                    "tiebreak %r is the same family (%s) as %s %r: related models make "
                    "related mistakes - use a different family" % (r["tiebreak"], tb, other, r[other]))
    return roster
