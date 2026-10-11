"""Claude through the logged-in `claude` CLI (the user's Claude subscription, no API key), with the same two functions as
tester/gemini.py, so the local test can run without Gemini credit:

    export LLM_BACKEND=claude                 # gemini.call / gemini.generate are routed here (see gemini.py)
    export CLAUDE_TEST_MODEL=claude-haiku-5-5 # optional, the default
    export CLAUDE_TEST_EFFORT=low             # optional: low | medium | high

The CLI answers one prompt at a time, so a multi-turn history is written out as a transcript, and function calling
is asked for as JSON ({"say": ..., "tool_calls": [...]}) and turned back into Gemini-shaped parts for the emulator.
Each call is a separate `claude -p` process (~1-3 s). No tools, no settings, no session files.
"""
import json, os, re, subprocess, tempfile, threading, time

MODEL = os.environ.get("CLAUDE_TEST_MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("CLAUDE_TEST_EFFORT", "low")
USAGE = {"calls": 0, "prompt": 0, "output": 0, "cache_read": 0, "seconds": 0.0}
_lock = threading.Lock()
_CWD = tempfile.mkdtemp(prefix="claude-test-")          # an empty folder: no CLAUDE.md or project settings to pick up


def usage_line():
    u = USAGE
    return (f"Claude ({MODEL}, subscription) usage: {u['calls']} calls, {u['prompt']/1e3:.1f}k prompt tokens "
            f"({u['cache_read']/1e3:.1f}k from cache), {u['output']/1e3:.1f}k output, {u['seconds']:.0f} s in calls")


def _ask(system, prompt, tries=4, model=None, effort=None):
    cmd = ["claude", "-p", "--model", model or MODEL, "--system-prompt", system, "--tools", "", "--no-session-persistence",
           "--output-format", "json", "--effort", effort or EFFORT, "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands"]
    last = None
    for attempt in range(tries):
        t0 = time.time()
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180, cwd=_CWD)
            out = json.loads(p.stdout or "{}")
        except (subprocess.TimeoutExpired, ValueError) as e:
            last = RuntimeError(f"claude CLI: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(3 * (attempt + 1))
            continue
        u = out.get("usage") or {}
        with _lock:
            USAGE["calls"] += 1
            USAGE["prompt"] += int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0)
            USAGE["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
            USAGE["output"] += int(u.get("output_tokens") or 0)
            USAGE["seconds"] += time.time() - t0
        text = (out.get("result") or "").strip()
        if p.returncode == 0 and not out.get("is_error") and text:
            return text
        last = RuntimeError(f"claude CLI exit {p.returncode}: {(text or p.stderr or p.stdout)[:300]}")
        time.sleep(3 * (attempt + 1))                   # rate limit or a busy model: back off and retry
    raise last


def ask_json(system, prompt, model, effort="medium"):
    """One JSON answer from a chosen model (used by main.py's cross-check, independent of the test model)."""
    return _json(_ask(system, prompt + "\n\nAnswer with JSON only, no code fence, no text around it.", model=model, effort=effort))


def _json(text):
    """The reply as JSON, tolerating a code fence or a sentence around it."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            return json.loads(m.group(0))
        raise


def generate(system, history, json_mode=False, model=None, temperature=None, thinking=None):
    """Same contract as gemini.generate: `history` is [(role, text)] with role "user" or "model"; returns the reply text."""
    if len(history) == 1 and history[0][0] == "user":
        prompt = history[0][1]
    else:
        lines = [("THEM: " if r == "user" else "YOU: ") + t for r, t in history]
        prompt = ("The conversation so far (YOU are the speaker described in your instructions):\n\n" + "\n".join(lines)
                  + "\n\nWrite only your next message, as you would say it. No label, no quotes, no notes.")
    if json_mode:
        prompt += "\n\nAnswer with JSON only, no code fence, no text around it."
        return json.dumps(_json(_ask(system, prompt)))
    return _ask(system, prompt)


def _schema(p):
    """A compact one-line view of a function's parameters for the prompt."""
    props = (p or {}).get("properties") or {}
    req = set((p or {}).get("required") or [])
    out = []
    for k, v in props.items():
        d = v.get("type", "any")
        if v.get("enum"): d += " one of " + json.dumps(v["enum"])
        if v.get("description"): d += f" ({v['description'][:160]})"
        out.append(f"{k}{'' if k in req else '?'}: {d}")
    return "{" + "; ".join(out) + "}"


def call(system, contents, tools=None, model=None, temperature=None, max_tokens=None, thinking=None):
    """Same contract as gemini.call: Gemini `contents` (text, functionCall, functionResponse parts) in, Gemini-shaped parts out."""
    lines = []
    for c in contents:
        for p in c.get("parts") or []:
            if "text" in p and p["text"]:
                lines.append(("CUSTOMER: " if c["role"] == "user" else "YOU (agent): ") + p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                lines.append(f"YOU called tool {fc.get('name')} with {json.dumps(fc.get('args') or {}, ensure_ascii=False)}")
            elif "functionResponse" in p:
                fr = p["functionResponse"]
                lines.append(f"TOOL RESULT {fr.get('name')}: {json.dumps(fr.get('response'), ensure_ascii=False)[:2000]}")
    tool_text = "\n".join(f"- {t['name']}: {t.get('description', '')[:400]}\n  parameters: {_schema(t.get('parameters'))}" for t in tools or [])
    prompt = ("The call so far:\n\n" + "\n".join(lines) + "\n\n"
              + (f"Tools you may call now:\n{tool_text}\n\n" if tools else "You have no tools in this step.\n\n")
              + "Decide your next move as the phone agent, following your instructions exactly. Answer with JSON only, no code fence:\n"
              '{"say": "what you say to the customer now, or an empty string", "tool_calls": [{"name": "tool name", "args": {...}}]}\n'
              "Use an empty tool_calls list when you call no tool. Call only the tools listed above, with their exact names.")
    try:
        d = _json(_ask(system, prompt))
    except ValueError:
        return [{"text": _ask(system, prompt)}]
    parts = []
    if (d.get("say") or "").strip():
        parts.append({"text": d["say"].strip()})
    names = {t["name"] for t in tools or []}
    for tc in d.get("tool_calls") or []:
        if isinstance(tc, dict) and tc.get("name") in names:
            parts.append({"functionCall": {"name": tc["name"], "args": tc.get("args") or {}}})
    return parts or [{"text": ""}]
