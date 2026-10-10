"""Tiny Gemini client. Standard library only.

    export GEMINI_API_KEY=...                    # Google AI Studio key
    export CUSTOMER_MODEL=gemini-3-flash-preview # optional, the model Freya's simulator uses
"""
import json, os, threading, time, urllib.error, urllib.request

MODEL = os.environ.get("CUSTOMER_MODEL", "gemini-3-flash-preview")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Token usage of this process, summed from usageMetadata, for the budget line at the end of a run. Thought tokens are billed as output.
USAGE = {"calls": 0, "prompt": 0, "output": 0, "thoughts": 0}
_lock = threading.Lock()


def _count(out):
    u = out.get("usageMetadata") or {}
    with _lock:
        USAGE["calls"] += 1
        USAGE["prompt"] += int(u.get("promptTokenCount") or 0)
        USAGE["output"] += int(u.get("candidatesTokenCount") or 0)
        USAGE["thoughts"] += int(u.get("thoughtsTokenCount") or 0)


def usage_line():
    u = USAGE
    return f"Gemini usage: {u['calls']} calls, {u['prompt']/1e6:.2f}M prompt tokens, {u['output']/1e3:.0f}k output, {u['thoughts']/1e3:.0f}k thinking"


def call(system, contents, tools=None, model=MODEL, temperature=None, max_tokens=None, thinking=None):
    """One model call with raw Gemini `contents` and optional function declarations. Returns the reply's parts
    (text parts and functionCall parts, thought signatures kept so they can be sent back unchanged)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key: raise RuntimeError("GEMINI_API_KEY is not set")
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents}
    if tools: body["tools"] = [{"functionDeclarations": tools}]
    cfg = {}
    if temperature is not None: cfg["temperature"] = temperature
    if max_tokens: cfg["maxOutputTokens"] = int(max_tokens)
    if thinking: cfg["thinkingConfig"] = {"thinkingLevel": thinking}
    if cfg: body["generationConfig"] = cfg
    req = urllib.request.Request(URL.format(model=model), data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r: out = json.load(r)
            _count(out)
            parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            parts = [p for p in parts if not p.get("thought")]
            if parts: return parts
            last = RuntimeError(f"empty Gemini reply: {json.dumps(out)[:300]}")
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"Gemini {e.code}: {e.read().decode()[:500]}")
            if e.code not in (429, 500, 502, 503, 504): raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = RuntimeError(f"Gemini connection: {e}")
        time.sleep(2 * (attempt + 1))
    raise last


def generate(system, history, json_mode=False, model=MODEL, temperature=None, thinking=None):
    """One model call. `history` is a list of (role, text) with role "user" or "model". Returns the reply text.
    `thinking`: "minimal" | "low" | "high" caps the model's reasoning (Gemini 3 thinkingLevel); None leaves the default."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key: raise RuntimeError("GEMINI_API_KEY is not set")
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": r, "parts": [{"text": t}]} for r, t in history]}
    cfg = {}
    if json_mode: cfg["responseMimeType"] = "application/json"
    if temperature is not None: cfg["temperature"] = temperature
    if thinking: cfg["thinkingConfig"] = {"thinkingLevel": thinking}
    if cfg: body["generationConfig"] = cfg
    req = urllib.request.Request(URL.format(model=model), data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r: out = json.load(r)
            _count(out)
            parts = ((out.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if text: return text
            last = RuntimeError(f"empty Gemini reply: {json.dumps(out)[:300]}")
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"Gemini {e.code}: {e.read().decode()[:300]}")
            if e.code not in (429, 500, 502, 503, 504): raise last
        except (urllib.error.URLError, TimeoutError) as e:
            last = RuntimeError(f"Gemini connection: {e}")
        time.sleep(2 * (attempt + 1))
    raise last
