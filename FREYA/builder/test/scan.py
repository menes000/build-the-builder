"""Scan every call of one or more run_cases result files for known bad patterns, pass or fail alike.

    source env.sh; python3 -m builder.test.scan kit/results/final-*.json

Reports, per call: loops (repeated agent lines), silent turns (model returned nothing), platform errors (snekbox,
function_call_error), model-filled close_call, customer hang-ups after silence, 'recorded' before a successful
create_promise, very long calls. The point: a run that passed can still hide a behaviour that fails next time.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "kit"))


def scan_call(call: dict) -> list[str]:
    issues = []
    msgs = call.get("messages") or []
    agent_lines = [m.get("message") or "" for m in msgs if m.get("role") == "assistant"]
    user_lines = [m.get("message") or "" for m in msgs if m.get("role") == "user"]
    # 1. loops: the same agent line 3+ times
    for line, n in Counter(l.strip().lower() for l in agent_lines if l.strip()).items():
        if n >= 3:
            issues.append(f"LOOP: agent said {n}x: {line[:60]!r}")
    # 2. consecutive identical user lines (persona stuck) with agent not moving on
    for line, n in Counter(l.strip().lower() for l in user_lines if l.strip()).items():
        if n >= 4:
            issues.append(f"STUCK: customer said {n}x: {line[:60]!r}")
    # 3. system events
    promise_ok_seen = False
    model_filled_close = False
    for m in msgs:
        if m.get("role") != "system":
            continue
        try:
            ev = json.loads(m.get("message") or "")
        except Exception:
            continue
        e = ev.get("event")
        txt = json.dumps(ev)
        if "snekbox" in txt:
            issues.append("PLATFORM: snekbox unreachable (code/hooks failed)")
        if e == "function_call_error":
            issues.append(f"TOOL_ERROR: {ev.get('function')}: {str(ev.get('error') or ev.get('message') or '')[:80]}")
        if e == "error":
            issues.append(f"ENGINE_ERROR: {str(ev.get('message'))[:80]}")
        if e == "function_call_complete" and ev.get("function") == "create_promise":
            d = (ev.get("result") or {}).get("data") or {}
            if str(d.get("ok")).lower() == "true":
                promise_ok_seen = True
        if e == "function_call_start" and ev.get("function") == "close_call":
            body = (ev.get("args") or {}).get("body") or {}
            if body.get("outcome") not in ("promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"):
                model_filled_close = True
                issues.append(f"CLOSE_INVALID: outcome={body.get('outcome')!r} reason={str(body.get('reason'))[:40]!r}")
    # 4. 'recorded' spoken before a successful promise
    said_recorded_early = False
    seen_ok = False
    for m in msgs:
        if m.get("role") == "system":
            try:
                ev = json.loads(m.get("message") or "")
            except Exception:
                continue
            if ev.get("event") == "function_call_complete" and ev.get("function") == "create_promise":
                d = (ev.get("result") or {}).get("data") or {}
                if str(d.get("ok")).lower() == "true":
                    seen_ok = True
        elif m.get("role") == "assistant" and not seen_ok and re.search(r"\brecorded\b", m.get("message") or "", re.I):
            said_recorded_early = True
    if said_recorded_early:
        issues.append("WORD: agent said 'recorded' before a successful create_promise")
    # 5. ending
    if call.get("endedReason") == "customer-ended-call":
        issues.append("HANGUP: customer ended the call (silence or loop)")
    if len(user_lines) > 25:
        issues.append(f"LONG: {len(user_lines)} customer turns")
    return sorted(set(issues))


def main(paths: list[str]) -> int:
    import freya
    total = Counter()
    for p in paths:
        r = json.loads(Path(p).read_text())
        rows_sets = r.get("all_rows") or [r.get("rows", [])]
        print(f"=== {p}")
        for rep, rows in enumerate(rows_sets):
            for row in rows:
                cid = row.get("call_id")
                if not cid:
                    continue
                try:
                    call = freya.get_call(cid)
                except Exception as e:
                    print(f"  {row['id']} rep{rep + 1}: could not fetch call: {e}")
                    continue
                issues = scan_call(call)
                for i in issues:
                    total[i.split(":")[0]] += 1
                if issues:
                    print(f"  {row['id']} rep{rep + 1} {'PASS' if row.get('pass') else 'FAIL'}: " + " | ".join(issues))
    print("\nTOTAL by class:", dict(total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
