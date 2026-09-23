"""`quotegate calibrate`: time each roster model on a few of YOUR items, so a
sweep's budget estimates come from your hardware and documents, not the
benchmark rig's. Writes a calibrated copy of the roster.

Load time is Ollama's own load_duration on the first request after an unload;
speed is (total - load) seconds per 1,000 chars of item text over the rest.
"""
import statistics

from .backends import BackendError, Ollama
from .worker import DEFAULT_SCHEMA, fill


def time_model(model, items, prompt, backend=None):
    b = backend or Ollama(model.host)
    if hasattr(b, "unload"):
        b.unload(model.name)
    load_s, per_kchar = None, []
    for i, it in enumerate(items):
        try:
            r = b.ask(model.name, fill(prompt, it), schema=DEFAULT_SCHEMA,
                      think=model.think, num_predict=model.num_predict)
        except BackendError:
            continue                         # a runaway still counts as time, not as speed
        m = r.meta
        total = (m.get("total_duration") or 0) / 1e9
        load = (m.get("load_duration") or 0) / 1e9
        if i == 0:
            load_s = load
        kchars = len(it["text"]) / 1000.0
        if kchars:
            per_kchar.append((total - load) / kchars)
    if hasattr(b, "unload"):
        b.unload(model.name)
    return {"load_s": round(load_s or model.load_s, 1),
            "s_per_kchar": round(statistics.median(per_kchar), 2) if per_kchar else None,
            "timed_items": len(per_kchar)}


def to_toml(roster):
    """Serialise a roster back to TOML (flat, as config.py reads it)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return '"%s"' % v
        return repr(v)
    lines = []
    for m in roster.models.values():
        think = {True: "on", False: "off", None: "auto"}.get(m.think, m.think)
        lines += ["[[models]]", 'name = "%s"' % m.name, 'family = "%s"' % m.family,
                  'host = "%s"' % m.host, 'think = "%s"' % think,
                  "num_predict = %d" % m.num_predict, "s_per_kchar = %s" % val(m.s_per_kchar),
                  "load_s = %s" % val(m.load_s)]
        if m.backend != "ollama":
            lines.append('backend = "%s"' % m.backend)
        if m.hosts:
            lines.append("hosts = [%s]" % ", ".join('"%s"' % h for h in m.hosts))
        lines.append("")
    lines.append("[roles]")
    lines += ['%s = "%s"' % (k, v) for k, v in roster.roles.items()]
    return "\n".join(lines) + "\n"
