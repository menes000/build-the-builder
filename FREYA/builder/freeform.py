"""Free-form build: for a call the builder's CallSpec template does not model (the template is an outbound collections call:
identity questions, promises, notes), Claude designs the whole Freya workflow from the case documents and the tool API.

Nothing here is specific to a case. Claude gets: the case files, the tool API (every URL already points at the team's mock),
Freya's workflow and tool documentation from the kit, and the kit's example agent. It writes the workflow JSON; the builder
checks it (JSON, lint, code syntax, every API tool URL inside the tool API, Freya dryRun) and sends every problem back,
a few rounds at most. Every model call is in the trace.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from .compile.lint import lint
from .extract.extractor import _brief_text

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"

# the CallSpec template compiles an outbound collections call; it needs these tools
TEMPLATE_TOOLS = {"verify_identity", "get_account", "create_promise", "close_call"}

BIG_FILE = 60_000      # characters: a larger case file is shown in part; Claude reads the rest with the Read tool
DATA_FILE = 6_000      # a JSON/CSV data file larger than this is shown in part (its shape), not in full


def template_fits(tool_names: set[str]) -> bool:
    return TEMPLATE_TOOLS <= set(tool_names)


INSTRUCTIONS = """You are the builder of a phone agent on the Freya platform. A bank handed over the documents below. Design the
complete Freya workflow (JSON) for the phone agent they describe, so that it handles every caller the documents describe,
the way the documents say.

How to work:
1. Read every case document. They were written at different times and do not always agree: the most recent decision
   wins (decision recaps, later mails and meeting notes over older analysis versions; a document's own "superseded" notes
   count). Example conversations show the expected order and wording. Test-environment files show the data the tools return.
2. Find the call variables the platform passes into each call (the documents name them). Use exactly those names. Put
   them, with realistic values taken from the test data, in `test_variables`.
3. Find the agent's flow: every branch, every question, what to say for each kind of tool answer (success, each error
   code, empty data, slow answers), when to hand over or end, and what the agent must never do or say.
4. Design the workflow with Freya's documentation below (node types, prompts, transitions, extraction, tools, hooks,
   code nodes, end_call nodes, limits, design rules). Prefer a clear graph of small nodes for the main steps over one big
   prompt; route on extracted variables and tool results; use code nodes or hooks for anything that must be exact
   (reading amounts and dates from tool results, choosing between cases by a field value).
5. Tools: only `api_call` tools for the endpoints of the tool API below, with the exact URL given there (it is the
   team's mock of the bank), method, request body shape and field names the documents give. Bake call variables into
   bodies with `{{variable}}`; let the model fill only what the caller decides. Map the response fields you route on.
   The agent may call no other service.
6. Language: the agent speaks the language the documents say the calls are in, in every prompt and every fixed
   sentence. Keep JSON keys, variable names, field names and enum values exactly as they are.
7. Speech: amounts and dates come from the tools as raw values; the prompts tell the agent how to say them in the
   call's language, as the documents ask. Never read error texts meant for logs to the caller.

Output: write the workflow JSON object (top-level keys `nodes`, `tools`, `global_nodes`, `initial_node`, `system_prompt`,
`test_variables`; no `agent_config`) with the Write tool to exactly this path: {out}
Then write a short design note (the flow as a list of nodes and why, the conflicts you resolved and how) to: {notes}
"""


PLAN_INSTRUCTIONS = """You are the first half of a phone-agent builder. Read every case document below and write the DESIGN of the
phone agent they describe, as a Markdown file, so that a second step can turn it into a Freya workflow without the documents.
The documents were written at different times and do not always agree: the most recent decision wins (decision recaps, later
mails and meeting notes over older analysis versions). Example conversations show the expected order and wording.

Write, compactly but completely (aim for 2,000-4,000 words):
1. Call variables the platform passes in (exact names) and realistic test values from the test data.
2. Language and speaking rules (how amounts, dates, card numbers are said; what is never said or done).
3. The tools: for each endpoint of the tool API, when it is called, the exact request body (field names, which values come from
   variables, which from earlier tool results, which from the caller), and which response fields matter.
4. The flow as numbered steps (each will become a node): what the agent says (in the call language, exact sentences where the
   documents fix them), what it asks, and every branch: per tool result (success, each error code, empty or missing data, slow
   answer), per caller answer (including refusals, vague answers, off-topic or adversarial requests), and where each step goes next.
5. Every way the call ends (hand back to the menu, transfer to a person, ...) and what is said before it.
6. The conflicts between documents you found and which version you followed.
Write the file with the Write tool to exactly this path: {plan}
"""

COMPACT_HEAD = """COMPACT BUILD: build only the core of the design: the main path and its essential branches (each tool's success
and failure, the caller's main choices, every way the call ends). At most 10 nodes. Put the remaining rules of the design as
short lines in `system_prompt` instead of extra nodes. Write the workflow first; keep thinking short.
"""

JSON_INSTRUCTIONS_HEAD = """The design below was written from the bank's case documents by the first step of this builder; it is
authoritative. Turn it into the Freya workflow, following it exactly.
Keep the workflow compact: one node per step of the design (merge trivial steps), shared rules once in `system_prompt`,
no repeated text across nodes.
"""


def _case_text(paths: list[str]) -> str:
    """The case files as text; a very large file (e.g. a big data dump) is cut, with its path for the Read tool."""
    parts = []
    for p in paths:
        t = _brief_text([p])
        if Path(p).suffix.lower() in (".json", ".csv") and len(t) > DATA_FILE:   # a data dump: its start shows the shape
            t = t[:DATA_FILE] + f"\n\n[... data file cut at {DATA_FILE} characters; the full data is at {Path(p).resolve()} ...]\n"
        elif len(t) > BIG_FILE:
            t = t[:BIG_FILE] + f"\n\n[... file cut at {BIG_FILE} characters; read the rest with the Read tool at {Path(p).resolve()} ...]\n"
        parts.append(t)
    return "".join(parts)


def _kit_docs() -> str:
    out = []
    for name in ("docs/workflow-format.md", "docs/tools-and-code.md"):
        p = KIT / name
        if p.exists():
            out.append(f"\n\n===== FREYA DOC: {name} =====\n{p.read_text()}")
    ex = KIT / "examples" / "base-agent.json"
    if ex.exists():
        out.append(f"\n\n===== FREYA EXAMPLE AGENT (a different, simpler call; shows the JSON shape only) =====\n{ex.read_text()}")
    return "".join(out)


def check_workflow(wf: dict, api_urls: set[str]) -> list[str]:
    """Problems Freya would reject or that break the call: lint, code syntax, API tools outside the tool API."""
    problems = list(lint(wf))

    def tools_of(container) -> list[dict]:
        return [t for t in (container or []) if isinstance(t, dict)]

    all_tools = tools_of(wf.get("tools"))
    for name, n in (wf.get("nodes") or {}).items():
        if not isinstance(n, dict):
            problems.append(f"{name}: node is not an object")
            continue
        all_tools += tools_of(n.get("tools")) + tools_of(n.get("pre_actions"))
    for t in all_tools:
        fn = t.get("function") or {}
        code = ((fn.get("parameters") or {}).get("properties") or {}).get("code", {})
        code = code.get("default") if isinstance(code, dict) else None
        if isinstance(code, str) and code.strip():           # a code_exec step: its code must run
            try:
                compile(code, f"<{fn.get('name', '?')}>", "exec")
            except SyntaxError as e:
                problems.append(f"code step {fn.get('name', '?')} does not compile: {e}")
        for key in ("pre_process_code", "post_process_code"):
            src = t.get(key) or fn.get(key)
            if isinstance(src, str) and src.strip():
                try:
                    compile(src, f"<{fn.get('name', '?')}.{key}>", "exec")
                except SyntaxError as e:
                    problems.append(f"tool {fn.get('name', '?')}: {key} does not compile: {e}")
        url = (((fn.get("parameters") or {}).get("properties") or {}).get("url") or {}).get("default")
        if t.get("type") == "api_call" or url:
            if url and url not in api_urls:
                problems.append(f"tool {fn.get('name', '?')}: url {url} is not an endpoint of the tool API (allowed: {sorted(api_urls)})")
    return problems


def build_freeform(brief_paths: list[str], openapi_path: str, tools, out_dir: Path, slot: str, trace, model: str | None,
                   validate, rounds: int = 3, compact: bool = False) -> dict:
    """Returns the workflow dict. `validate(wf)` is Freya's dryRun (raises on rejection)."""
    from .extract.extractor import _ask_claude
    model = model or os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
    out = (out_dir / f"{slot}.freeform.workflow.json").resolve()
    notes = (out_dir / f"{slot}.freeform.notes.md").resolve()
    api_urls = {t.url for t in tools}
    api_text = Path(openapi_path).read_text()
    api_block = ("\n\n## Tool API (OpenAPI; every server URL is the team's mock, use these URLs exactly)\n```json\n" + api_text + "\n```\n"
                 + "\n## Endpoint URLs\n" + "\n".join(f"- {t.name}: POST {t.url}" for t in tools) + "\n")
    # step 1: the design, read from the documents (text, short); step 2: the workflow JSON from the design (no raw documents)
    plan = (out_dir / f"{slot}.freeform.plan.md").resolve()
    if plan.exists():
        plan.unlink()
    for attempt in (1, 2):
        asyncio.run(_ask_claude(PLAN_INSTRUCTIONS.replace("{plan}", str(plan)) + api_block + "\n\n## The case files" + _case_text(brief_paths) + "\n",
                                plan, out_dir.resolve(), model, trace, purpose=f"free-form: write the agent's design from the case documents (attempt {attempt})",
                                max_turns=20))
        if plan.exists() and len(plan.read_text().strip()) >= 500:
            break
    if not plan.exists() or len(plan.read_text().strip()) < 500:
        raise RuntimeError("free-form build: no design written from the case documents")
    trace.note(f"free-form design written: {plan} ({len(plan.read_text())} chars)")
    base = ((COMPACT_HEAD if compact else "") + JSON_INSTRUCTIONS_HEAD + "\n" + INSTRUCTIONS.replace("{out}", str(out)).replace("{notes}", str(notes))
            + "\n\n## The design (authoritative)\n" + plan.read_text() + "\n"
            + api_block + _kit_docs() + "\n")
    feedback = ""
    best = None
    for rnd in range(1, rounds + 1):
        if out.exists():
            prev = out.read_text()
            out.unlink()
        else:
            prev = ""
        prompt = base if not feedback else (
            base + "\n\n## Your previous workflow (rejected)\n```json\n" + prev[:120_000] + "\n```\n"
            + "\n## Problems to fix\n- " + "\n- ".join(feedback) + f"\n\nFix every problem and write the complete corrected workflow again to {out}.")
        t0 = time.time()
        asyncio.run(_ask_claude(prompt, out, out_dir.resolve(), model, trace,
                                purpose=f"free-form: write the workflow JSON from the design (round {rnd})", max_turns=40,
                                effort="low" if compact else "medium", max_thinking_tokens=8_000 if compact else 16_000))
        if not out.exists():
            feedback = ["No workflow file was written to the output path."]
            trace.note(f"free-form round {rnd}: no file written ({time.time() - t0:.0f} s)")
            continue
        try:
            wf = json.loads(out.read_text())
        except ValueError as e:
            feedback = [f"The file is not valid JSON: {e}"]
            trace.note(f"free-form round {rnd}: invalid JSON")
            continue
        if isinstance(wf, dict) and "workflow" in wf and "nodes" not in wf:
            wf = wf["workflow"]
        wf.pop("agent_config", None)
        problems = check_workflow(wf, api_urls)
        if not problems:
            try:
                validate(wf)
            except Exception as e:
                problems = [f"Freya dryRun rejected the workflow: {str(e)[:3000]}"]
        if not problems:
            trace.note(f"free-form round {rnd}: workflow valid, {len(wf.get('nodes', {}))} nodes, "
                       f"{sum(len(n.get('tools') or []) for n in wf['nodes'].values()) + len(wf.get('tools') or [])} tools")
            return wf
        best = wf
        feedback = problems[:40]
        trace.note(f"free-form round {rnd}: {len(problems)} problem(s): {problems[0][:200]}")
    raise RuntimeError(f"free-form build: no valid workflow after {rounds} rounds; last problems: {feedback[:5]}") if best is None else \
        RuntimeError(f"free-form build: workflow still rejected after {rounds} rounds: {feedback[:5]}")
