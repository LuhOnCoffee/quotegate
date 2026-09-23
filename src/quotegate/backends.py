"""Model backends. A backend turns one prompt into one reply; everything that
decides whether the reply is trusted lives in worker.py and gate.py.

Two backends: Ollama (native /api/chat) and any OpenAI-compatible
/v1/chat/completions server (llama.cpp, LM Studio, vLLM - or Ollama's own /v1).
Both carry the defences for the silent failures measured on 2026-09-21 - each
one produced output that looked like a model capability result and was a
harness defect:

  1. TRUNCATION. Ollama's default context cut a 4,167-token prompt to 2,050
     tokens without an error - it keeps about HALF of num_ctx - so a
     "prompt_eval_count near num_ctx" check never fires. num_ctx is sent
     explicitly and a reply is refused when the prompt read at more than
     MAX_CHARS_PER_TOKEN (markdown reads at 3.1-3.3; the cut read at 12.5).
  2. /api/generate + a JSON schema silently disables reasoning (qwen3: 0 chars
     of thinking; gpt-oss: an empty response). /api/chat does not, so chat is
     the only endpoint used.
  3. THE ANSWER IN THE WRONG CHANNEL. qwen3.5 with a schema and thinking on
     wrote the correct JSON into `thinking` and returned an empty `content`.
     Named as such instead of being reported as "raise num_predict".
"""
import json
import urllib.request
from dataclasses import dataclass, field

NUM_CTX = 16384
MAX_CHARS_PER_TOKEN = 6.0


class BackendError(Exception):
    """The request did not produce a usable reply (never a model 'answer')."""


class Truncated(BackendError):
    """The backend cut the prompt, so the model saw only part of it."""


class AnswerInThinking(BackendError):
    """The schema-shaped answer was written to the thinking channel."""


class Runaway(BackendError):
    """Generation hit the token cap before producing an answer."""


@dataclass
class Reply:
    content: str
    thinking: str = ""
    meta: dict = field(default_factory=dict)


def truncated(chars, prompt_tokens):
    """True when too few tokens were evaluated for the prompt's length."""
    return bool(prompt_tokens) and chars / prompt_tokens > MAX_CHARS_PER_TOKEN


def first_json_object(text):
    """The first balanced {...} in a free-text reply, parsed; or None."""
    s = text or ""
    start = s.find("{")
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except ValueError:
                        break
        start = s.find("{", start + 1)
    return None


class Ollama:
    """Ollama's /api/chat. `think` is True, False, "low"/"medium"/"high", or
    None to send nothing (the model's default - which two models measured here
    handle badly; set it explicitly)."""

    def __init__(self, host="http://127.0.0.1:11434", num_ctx=NUM_CTX, timeout=900):
        host = host.strip().rstrip("/")
        self.host = host if "://" in host else "http://" + host
        self.num_ctx = num_ctx
        self.timeout = timeout

    def _post(self, body):
        req = urllib.request.Request(self.host + "/api/chat", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())

    def unload(self, model):
        """Evict the model now (keep_alive 0), so the next stage has the VRAM.
        Best effort: a failure here must never fail a sweep."""
        try:
            req = urllib.request.Request(self.host + "/api/generate",
                                         json.dumps({"model": model, "keep_alive": 0}).encode(),
                                         {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=60).read()
        except Exception:                                     # noqa: BLE001
            pass

    def ask(self, model, prompt, schema=None, think=None, num_predict=4096):
        body = {"model": model, "stream": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0, "num_predict": num_predict,
                            "num_ctx": self.num_ctx}}
        if schema is not None:
            body["format"] = schema
        if think is not None:
            body["think"] = think
        try:
            out = self._post(body)
        except Exception as e:                                # noqa: BLE001
            raise BackendError("%s: %s" % (type(e).__name__, e)) from e
        msg = out.get("message") or {}
        meta = {k: out.get(k) for k in ("prompt_eval_count", "eval_count", "eval_duration",
                                         "prompt_eval_duration", "load_duration",
                                         "total_duration", "done_reason")}
        reply = Reply(msg.get("content") or "", msg.get("thinking") or "", meta)
        meta["thinking_chars"] = len(reply.thinking)
        return self.check(reply, prompt, schema is not None)

    @staticmethod
    def check(reply, prompt, used_schema):
        """Refuse replies that only look like answers. Static so it is testable
        without a server."""
        m = reply.meta
        if truncated(len(prompt), m.get("prompt_eval_count") or 0):
            raise Truncated("%d chars read as %s tokens - the prompt was cut; raise num_ctx "
                            "or chunk the input" % (len(prompt), m.get("prompt_eval_count")))
        if not reply.content.strip():
            if (used_schema and m.get("done_reason") == "stop"
                    and first_json_object(reply.thinking) is not None):
                raise AnswerInThinking("the schema answer landed in `thinking` - set think off")
            if m.get("done_reason") == "length":
                raise Runaway("hit num_predict (%s tokens) without an answer" % m.get("eval_count"))
            raise BackendError("empty reply (done_reason=%s)" % m.get("done_reason"))
        return reply


class OpenAICompat:
    """Any OpenAI-compatible /v1/chat/completions server: llama.cpp, LM Studio,
    vLLM, or Ollama's own /v1 endpoint.

    The same refusals as the Ollama backend, from the fields this API gives:
    `usage.prompt_tokens` for the truncation check, `finish_reason == "length"`
    for a runaway, and `message.reasoning` (Ollama's name for the thinking
    channel here) for an answer in the wrong channel.

    `think` maps to `reasoning_effort` for servers that support it ("low" /
    "medium" / "high"); True/False have no portable equivalent and are ignored
    - use the Ollama backend when a model's thinking must be switched off.
    """

    def __init__(self, host="http://127.0.0.1:11434", api_key=None, timeout=900,
                 max_chars_per_token=MAX_CHARS_PER_TOKEN):
        host = host.strip().rstrip("/")
        self.host = host if "://" in host else "http://" + host
        self.api_key = api_key
        self.timeout = timeout
        self.max_chars_per_token = max_chars_per_token

    def _post(self, body):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        req = urllib.request.Request(self.host + "/v1/chat/completions",
                                     json.dumps(body).encode(), headers)
        return json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())

    def ask(self, model, prompt, schema=None, think=None, num_predict=4096):
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": num_predict}
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "answer", "schema": schema}}
        if think in ("low", "medium", "high"):
            body["reasoning_effort"] = think
        try:
            out = self._post(body)
        except Exception as e:                                # noqa: BLE001
            raise BackendError("%s: %s" % (type(e).__name__, e)) from e
        choice = (out.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = out.get("usage") or {}
        reply = Reply(msg.get("content") or "", msg.get("reasoning") or "",
                      {"prompt_eval_count": usage.get("prompt_tokens"),
                       "eval_count": usage.get("completion_tokens"),
                       "done_reason": choice.get("finish_reason")})
        reply.meta["thinking_chars"] = len(reply.thinking)
        return self.check(reply, prompt, schema is not None)

    def check(self, reply, prompt, used_schema):
        m = reply.meta
        if truncated(len(prompt), m.get("prompt_eval_count") or 0):
            raise Truncated("%d chars read as %s tokens - the prompt was cut"
                            % (len(prompt), m.get("prompt_eval_count")))
        if not reply.content.strip():
            if used_schema and m.get("done_reason") == "stop" \
                    and first_json_object(reply.thinking) is not None:
                raise AnswerInThinking("the schema answer landed in the reasoning field")
            if m.get("done_reason") == "length":
                raise Runaway("hit max_tokens (%s) without an answer" % m.get("eval_count"))
            raise BackendError("empty reply (finish_reason=%s)" % m.get("done_reason"))
        return reply
