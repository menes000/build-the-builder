"""The builder's own fix loop: failed practice customers -> a revised CallSpec (Claude), recompile, retest.

Everything here is done by the builder at run time from the brief and the test results; no human edits.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from ..extract.callspec import CallSpec
from ..extract.extractor import _ask_claude, PROMPT_DIR

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "kit"))


def _transcript(call: dict, limit: int = 40) -> str:
    lines = []
    for m in call.get("messages") or []:
        role = m.get("role")
        txt = m.get("message") or ""
        if role in ("assistant", "user"):
            lines.append(f"{'AGENT' if role == 'assistant' else 'CUSTOMER'}: {txt[:300]}")
        elif role == "system":
            try:
                ev = json.loads(txt)
            except Exception:
                continue
            if ev.get("event") == "function_call_start" and ev.get("function") not in ("code_exec",):
                body = (ev.get("args") or {}).get("body")
                lines.append(f"TOOL CALL {ev.get('function')}: {json.dumps(body)[:200]}")
            elif ev.get("event") == "function_call_complete" and ev.get("function") not in ("code_exec",):
                d = (ev.get("result") or {}).get("data") if isinstance(ev.get("result"), dict) else None
                if isinstance(d, dict):
                    lines.append(f"TOOL RESULT {ev.get('function')}: " + json.dumps({k: v for k, v in d.items() if k != 'what_to_do_next'})[:200])
            elif ev.get("event") == "error":
                lines.append(f"ENGINE ERROR: {str(ev.get('message'))[:120]}")
    return "\n".join(lines[-limit:])


def collect_failures(result: dict, cases_by_id: dict) -> list[dict]:
    import freya
    out = []
    for row in result.get("rows", []):
        if row.get("pass"):
            continue
        c = cases_by_id.get(row["id"], {})
        tx = ""
        if row.get("call_id"):
            try:
                tx = _transcript(freya.get_call(row["call_id"]))
            except Exception as e:
                tx = f"(transcript unavailable: {e})"
        out.append({
            "id": row["id"], "title": c.get("title", ""), "family": row.get("family", ""),
            "script": c.get("script", ""), "checks": c.get("checks", []), "expected": c.get("expected", {}),
            "failed": row.get("failed", []), "transcript": tx,
        })
    return out


def platform_noise(failure: dict) -> bool:
    blob = " ".join(failure.get("failed", [])) + " " + failure.get("transcript", "")
    return "snekbox" in blob or "technical error" in blob.lower() or "service unavailable" in blob.lower() and "create_promise" not in blob


def propose_fix(spec: CallSpec, failures: list[dict], brief_paths: list[str], out_path: str, trace, model: str) -> CallSpec | None:
    """Ask Claude for a revised CallSpec. Returns None when nothing should change or the result is invalid."""
    real = [f for f in failures if not platform_noise(f)]
    if not real:
        trace.note("fix loop: all failures look like platform noise; no change")
        return None
    out = Path(out_path).resolve()
    if out.exists():
        out.unlink()
    instructions = (PROMPT_DIR / "fix_callspec.md").read_text()
    briefs = "".join(f"\n\n===== BRIEF FILE: {p} =====\n{Path(p).read_text()}" for p in brief_paths)
    spec_json = spec.model_dump_json(indent=1, exclude={"tools", "field_map"})
    fails = "\n\n".join(
        f"===== FAILURE {f['id']}: {f['title']} ({f['family']}) =====\nCustomer script: {f['script']}\nJudge checks: {json.dumps(f['checks'])}\n"
        f"Expected ledger: {json.dumps(f['expected'])}\nWhat failed: {json.dumps(f['failed'])}\nTranscript:\n{f['transcript']}"
        for f in real)
    prompt = (f"{instructions}\n\n## Output path\n{out}\n\n## Current CallSpec\n```json\n{spec_json}\n```\n\n"
              f"## Failures\n{fails}\n\n## The brief{briefs}\n")
    asyncio.run(_ask_claude(prompt, out, Path.cwd(), model, trace, purpose=f"revise CallSpec after {len(real)} failed practice customers"))
    if not out.exists():
        trace.note("fix loop: no revised CallSpec written")
        return None
    try:
        new = CallSpec.model_validate_json(out.read_text())
    except (ValidationError, ValueError) as e:
        trace.note(f"fix loop: revised CallSpec invalid: {str(e)[:300]}")
        return None
    # guard: structural fields must not move
    for a, b, name in (
        (spec.dates.holidays, new.dates.holidays, "holidays"),
        ([(x.days_late_min, x.days_late_max, x.persuasion_attempts) for x in spec.dates.bands], [(x.days_late_min, x.days_late_max, x.persuasion_attempts) for x in new.dates.bands], "bands"),
        ([(o.outcome, sorted(o.reasons)) for o in spec.closing.outcomes], [(o.outcome, sorted(o.reasons)) for o in new.closing.outcomes], "outcomes"),
        (spec.multi_product.enabled, new.multi_product.enabled, "multi_product"),
        ([q.field for q in spec.identity.questions], [q.field for q in new.identity.questions], "identity questions"),
    ):
        if a != b:
            trace.note(f"fix loop: revision changed {name}; rejected")
            return None
    new.tools = spec.tools
    new.field_map = spec.field_map
    trace.note("fix loop: revised CallSpec accepted (" + "; ".join(n[:120] for n in new.source_notes[-len(real):]) + ")")
    return new
