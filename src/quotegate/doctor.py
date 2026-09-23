"""`quotegate doctor`: measure, on YOUR Ollama, the silent traps this project
found - rather than assume they still exist (Ollama may fix them) or assume
they do not (they did not announce themselves here).

  1. Default-context truncation: a long prompt sent WITHOUT num_ctx - how many
     tokens were actually read? Measured 2026-09-21: 2,050 of 4,167.
  2. /api/generate + JSON schema vs /api/chat + JSON schema, with think=True:
     does the generate endpoint silently skip reasoning? Measured 2026-09-21
     on qwen3:8b: 0 chars of thinking on generate, 1,832 on chat.
"""
import json
import urllib.request

from .worker import DEFAULT_SCHEMA

# ~8,000 tokens: LONGER than any common default context (Ollama only cuts a
# prompt that exceeds num_ctx, and then keeps about half). A first version used
# ~2,700 tokens, fit inside the 4,096 default, and "proved" nothing.
FILLER = ("The configuration section describes each option in turn. "
          "Options are read at start-up and can be overridden per command. ") * 360


def _post(host, path, body, timeout=900):
    req = urllib.request.Request(host + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def check_truncation(host, model):
    """Read the same long prompt twice: at Ollama's DEFAULT context and at a
    large explicit one. Truncated if the default read noticeably fewer tokens.

    A fixed chars-per-token threshold is not enough here: the filler is
    repetitive and tokenizes unusually well (5.46 chars/token measured), so it
    can look "fine" by ratio while still being cut. Measure the reference."""
    prompt = "Summarise in one word.\n\n" + FILLER
    def read(opts):
        out = _post(host, "/api/generate", {"model": model, "prompt": prompt, "stream": False,
                                            "think": False, "options": {"num_predict": 1, **opts}})
        return out.get("prompt_eval_count") or 0
    default, full = read({}), read({"num_ctx": 32768})
    return {"prompt_chars": len(prompt), "tokens_default": default, "tokens_full": full,
            "truncated": full > 0 and default < 0.95 * full}


def check_reasoning(host, model):
    prompt = ("Is 3.9 at least 3.10? Think it through, then answer as JSON with "
              "found=true if it is, and quote the phrase 'at least 3.10'.")
    base = {"model": model, "stream": False, "think": True, "format": DEFAULT_SCHEMA,
            "options": {"temperature": 0, "num_predict": 2048, "num_ctx": 4096}}
    try:
        gen = _post(host, "/api/generate", {**base, "prompt": prompt})
        chat = _post(host, "/api/chat", {**base, "messages": [{"role": "user", "content": prompt}]})
    except Exception as e:                                    # noqa: BLE001
        return {"error": "%s: %s (model may not support thinking)" % (type(e).__name__, e)}
    g = len(gen.get("thinking") or "")
    c = len((chat.get("message") or {}).get("thinking") or "")
    return {"generate_thinking_chars": g, "chat_thinking_chars": c,
            "generate_drops_reasoning": c > 0 and g == 0}


def main(host, model):
    host = host if "://" in host else "http://" + host
    print("quotegate doctor  host=%s  model=%s\n" % (host, model))
    t = check_truncation(host, model)
    print("1. default-context truncation: the same %d-char prompt read as %d tokens at the "
          "default context, %d at num_ctx 32768" % (t["prompt_chars"], t["tokens_default"], t["tokens_full"]))
    print("   -> %s" % ("TRUNCATED at Ollama's default context: always send num_ctx (quotegate does)"
                        if t["truncated"] else "not truncated at the default context on this install"))
    r = check_reasoning(host, model)
    if "error" in r:
        print("2. reasoning under a schema: skipped - %s" % r["error"])
    else:
        print("2. reasoning under a schema: generate %d chars of thinking, chat %d"
              % (r["generate_thinking_chars"], r["chat_thinking_chars"]))
        print("   -> %s" % ("/api/generate DROPS reasoning under a schema: use /api/chat (quotegate does)"
                            if r["generate_drops_reasoning"] else
                            "no difference measured for this model"))
    return 0
