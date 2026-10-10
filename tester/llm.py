"""Provider choice and a disk cache for the deterministic model calls of the tester (extraction, routing, judge).

Providers: "gemini" (tester/gemini.py) or "openai" (tester/openai_client.py).
    EXTRACT_PROVIDER, ROUTE_PROVIDER, JUDGE_PROVIDER   default: openai for extract and judge when OPENAI_API_KEY is set, else gemini;
                                                      routing stays on gemini (closest to Freya's own router)
    LLM_CACHE=0                                        switch the cache off
Cache: results/llm-cache.json, keyed by provider + model + prompt + input. Only extraction is cached (LLM_CACHE_KINDS=extract,route,judge widens it);
the customer and the agent are never cached (they must vary).
"""
import hashlib, json, os, pathlib, threading

import gemini, openai_client

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "results" / "llm-cache.json"
_lock = threading.Lock()
_cache = None
STATS = {"hits": 0, "misses": 0}
CACHED_KINDS = set(os.environ.get("LLM_CACHE_KINDS", "extract").split(","))   # only extraction by default; routing and judge always call the model


def provider(kind):
    env = os.environ.get(f"{kind.upper()}_PROVIDER")
    if env: return env
    if kind in ("extract", "judge") and os.environ.get("OPENAI_API_KEY"): return "openai"
    return "gemini"


def model_of(prov):
    return openai_client.MODEL if prov == "openai" else gemini.MODEL


def _load():
    global _cache
    if _cache is None:
        try: _cache = json.load(open(CACHE_FILE))
        except Exception: _cache = {}
    return _cache


def generate(kind, system, history, json_mode=False, thinking=None):
    """A deterministic call (temperature 0 / low reasoning) for `kind` in extract | route | judge, through the cache."""
    prov = provider(kind)
    key = hashlib.sha1(json.dumps([prov, model_of(prov), system, history, json_mode], sort_keys=True).encode()).hexdigest()
    use_cache = kind in CACHED_KINDS and os.environ.get("LLM_CACHE", "1") != "0"
    if use_cache:
        with _lock:
            hit = _load().get(key)
        if hit is not None:
            STATS["hits"] += 1; return hit
    if use_cache: STATS["misses"] += 1
    if prov == "openai":
        text = openai_client.generate(system, history, json_mode=json_mode)
    else:
        text = gemini.generate(system, history, json_mode=json_mode, temperature=0, thinking=thinking)
    if use_cache:
        with _lock:
            _load()[key] = text
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = CACHE_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps(_cache)); tmp.replace(CACHE_FILE)
    return text


def usage_lines():
    out = [gemini.usage_line()]
    if openai_client.USAGE["calls"]: out.append(openai_client.usage_line())
    out.append(f"LLM cache ({','.join(sorted(CACHED_KINDS))}): {STATS['hits']} hits, {STATS['misses']} misses (extract={provider('extract')}, route={provider('route')}, judge={provider('judge')})")
    return out
