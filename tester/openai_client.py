"""Tiny OpenAI client (Chat Completions). Standard library only. Used for the extraction and judge calls when OPENAI_API_KEY is set.

    export OPENAI_API_KEY=...
    export OPENAI_MODEL=gpt-5.4-mini        # optional (gpt-5-mini needs org verification)
    export OPENAI_REASONING=low             # optional: minimal | low | medium | high (reasoning models); unset = model default
"""
import json, os, threading, time, urllib.error, urllib.request

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
REASONING = os.environ.get("OPENAI_REASONING", "low")
URL = "https://api.openai.com/v1/chat/completions"
USAGE = {"calls": 0, "prompt": 0, "output": 0, "reasoning": 0}
_lock = threading.Lock()


def _count(out):
    u = out.get("usage") or {}
    with _lock:
        USAGE["calls"] += 1
        USAGE["prompt"] += int(u.get("prompt_tokens") or 0)
        USAGE["output"] += int(u.get("completion_tokens") or 0)
        USAGE["reasoning"] += int(((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0)


def usage_line():
    u = USAGE
    return f"OpenAI usage: {u['calls']} calls, {u['prompt']/1e3:.1f}k prompt tokens, {u['output']/1e3:.1f}k output ({u['reasoning']/1e3:.1f}k reasoning)"


def generate(system, history, json_mode=False, model=MODEL, reasoning=REASONING):
    """One model call. `history` is a list of (role, text) with role "user" or "model". Returns the reply text."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key: raise RuntimeError("OPENAI_API_KEY is not set")
    messages = [{"role": "system", "content": system}] + [{"role": "assistant" if r == "model" else "user", "content": t} for r, t in history]
    body = {"model": model, "messages": messages}
    if json_mode: body["response_format"] = {"type": "json_object"}
    if reasoning: body["reasoning_effort"] = reasoning
    last = None
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=120) as r: out = json.load(r)
            _count(out)
            text = ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            if text.strip(): return text.strip()
            last = RuntimeError(f"empty OpenAI reply: {json.dumps(out)[:300]}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:500]
            if e.code == 400 and "reasoning_effort" in msg and "reasoning_effort" in body:
                body.pop("reasoning_effort"); continue                      # the model has no reasoning switch
            last = RuntimeError(f"OpenAI {e.code}: {msg}")
            if e.code not in (429, 500, 502, 503, 504): raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = RuntimeError(f"OpenAI connection: {e}")
        time.sleep(2 * (attempt + 1))
    raise last
