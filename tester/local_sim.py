"""Run practice cases against a phone agent without Freya's simulation queue.

The phone agent runs on Freya as usual (experimental-5), reached turn by turn through the chat API.
Gemini plays the customer with the same persona prompt as tools/run_cases.py, and Gemini judges the transcript
against the case's checks. The bank's records are scored with tools/score.py. A case passes when both pass.

    python3 tester/local_sim.py <workflow_id or agent_id> [--brief A|B] [--only PUB-01,PUB-04] [--cases file.json]
                                [--reps 3] [--style in_words] [--parallel 3] [--max-turns 40] [--out results/local.json]

Needs FREYA_API_KEY, FREYA_BANK_TEAM_KEY and GEMINI_API_KEY.
"""
import argparse, concurrent.futures, json, pathlib, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "docs" / "build-the-builder"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(ROOT / "tester"))
import freya, gemini
from run_cases import STYLES, persona_for
from score import http, score_ledger

FIRST_LINE = "Hello?"                        # the customer picks up the phone
BYE = ("goodbye", "good bye", "bye.")
JUDGE = """You read the transcript of a phone call between a bank's phone agent (AGENT) and a customer (CUSTOMER).
Lines marked TOOL are the calls the agent made to the bank's systems, with their arguments and results.

Decide whether ALL of these success criteria are true:
{criteria}

Judge only these criteria, strictly, from the transcript. Answer with JSON only: {{"pass": true or false, "reason": "one or two sentences, naming the criterion that failed if any"}}"""

print_lock = threading.Lock()


def say(*a):
    with print_lock: print(*a, flush=True)


def chat(body):
    return freya.api("POST", "/api/v2/chat/message", body)


def workflow_for(given):
    """Accept a workflow id, an agent id or a slot name, and return the workflow id, through freya.save_workflow's state files."""
    for f in (KIT / ".freya-agents.json", ROOT / ".freya-agents.json", pathlib.Path(".freya-agents.json")):
        if not f.exists(): continue
        for name, slot in json.loads(f.read_text()).items():
            if given in (name, slot.get("agent_id"), slot.get("workflow_id")): return slot["workflow_id"]
    return given


def spoken(call_id):
    return [m for m in freya.get_call(call_id).get("messages", []) if m.get("role") in ("user", "assistant")]


def agent_turn(body, call_id, last_agent_text, tries=12, stats=None):
    """Send one customer message. The chat route sometimes answers 503 at once; that is retried with a pause.
    A message is never sent twice: mid-call, the call is read back first to see whether it arrived."""
    for attempt in range(tries):
        try:
            return chat(body)
        except RuntimeError as e:
            code = next((c for c in (" 503", " 504", " 502", " 500") if c in str(e)), None)
            if not code or attempt == tries - 1: raise
            if stats is not None: stats["freya_retries"] += 1
            time.sleep(min(2 + attempt, 8))
            if not call_id: continue                          # nothing started yet: safe to send again
            msgs = spoken(call_id)
            arrived = any(m["role"] == "user" and m.get("message") == body["message"] for m in msgs[-3:])
            if not arrived: continue                          # the message never reached the call: send it again
            for _ in range(5):                                # it arrived: wait for the agent's answer instead
                if msgs and msgs[-1]["role"] == "assistant" and msgs[-1].get("message") != last_agent_text:
                    return {"response": msgs[-1]["message"], "callId": call_id, "endedByAgent": False}
                time.sleep(4); msgs = spoken(call_id)
            return {"response": "", "callId": call_id, "endedByAgent": bool(freya.get_call(call_id).get("endedReason"))}   # arrived, agent stayed silent


def wait_for_close(customer_id, seconds=45):
    """End-of-call tools run some seconds after the call ends. Read the ledger until close_call is in it, or give up."""
    end = time.time() + seconds
    while True:
        ledger = http("/v1/practice/ledger/" + customer_id)
        calls = ledger.get("calls") or []
        if (calls and calls[-1].get("tool") == "close_call") or time.time() > end: return ledger
        time.sleep(3)


SANDBOX = ("snekbox", "Cannot connect to host")


def platform_errors(call):
    """Tool errors that come from Freya's infrastructure (its Python sandbox), not from the agent's workflow."""
    out = []
    for m in call.get("messages", []):
        if m.get("role") != "system": continue
        try: e = json.loads(m.get("message") or "")
        except ValueError: continue
        text = json.dumps(e)
        if e.get("event") in ("function_call_error", "error") and any(k in text for k in SANDBOX):
            out.append(f"{e.get('function') or e.get('event')}: {str(e.get('error') or e.get('message'))[:120]}")
    return out


def transcript_text(call):
    """User and agent lines plus the tool calls, as plain text for the judge."""
    out = []
    for m in call.get("messages", []):
        role, text = m.get("role"), m.get("message") or ""
        if role == "assistant": out.append("AGENT: " + text)
        elif role == "user": out.append("CUSTOMER: " + text)
        elif role == "system":
            try: ev = json.loads(text)
            except (ValueError, TypeError): continue
            if ev.get("event") == "function_call_start":
                args = ev.get("args") or {}
                args = args.get("body", args) if isinstance(args, dict) else args
                out.append(f"TOOL CALL {ev.get('function')}: {json.dumps(args)[:400]}")
            elif ev.get("event") == "function_call_complete":
                res = ev.get("result")
                res = res.get("data", res) if isinstance(res, dict) else res
                out.append(f"TOOL RESULT {ev.get('function')}: {json.dumps(res)[:400]}")
    return "\n".join(out)


def judge(criteria, call):
    raw = gemini.generate(JUDGE.format(criteria=criteria), [("user", transcript_text(call))], json_mode=True, temperature=0)
    try:
        v = json.loads(raw)
        return bool(v.get("pass")), str(v.get("reason", ""))
    except ValueError:
        return False, "judge returned no JSON: " + raw[:200]


def run_case(workflow_id, case, style, max_turns, out_dir, rep):
    """One customer, one call. Returns a row like run_cases.py, with status PASS, FAIL or ERROR."""
    persona = persona_for(case, {"identity": case["identity"]}, style)
    row = {"id": case["id"], "level": case["level"], "family": case["family"], "rep": rep, "failed": [], "turns": 0}
    conv, record, call_id = [], {"case": case["id"], "style": style, "persona": persona["prompt"]}, None
    stats = {"gemini_s": 0.0, "freya_s": 0.0, "freya_retries": 0, "turns": []}
    try:
        variables = http("/v1/practice/sessions", {"case": case["id"]})["variables"]
        record["variables"] = variables; row["customer_id"] = variables["customer_id"]
        t = time.time()
        r = agent_turn({"workflowId": workflow_id, "message": FIRST_LINE, "customerVariables": variables}, None, None, stats=stats)
        stats["freya_s"] += time.time() - t
        call_id = row["call_id"] = r["callId"]
        agent_text, ended, customer_said_bye = r.get("response") or "", bool(r.get("endedByAgent")), False
        conv.append(("AGENT", agent_text))
        history = []
        while not ended and row["turns"] < max_turns and not customer_said_bye:
            history.append(("user", agent_text or "(silence)"))
            t = time.time(); customer = gemini.generate(persona["prompt"], history, temperature=1.0); g = time.time() - t
            history.append(("model", customer)); conv.append(("CUSTOMER", customer)); row["turns"] += 1
            customer_said_bye = any(b in customer.lower() for b in BYE)
            t = time.time(); r = agent_turn({"callId": call_id, "message": customer}, call_id, agent_text, stats=stats); f = time.time() - t
            stats["gemini_s"] += g; stats["freya_s"] += f; stats["turns"].append({"gemini_s": round(g, 1), "freya_s": round(f, 1)})
            agent_text, ended = r.get("response") or "", bool(r.get("endedByAgent"))
            conv.append(("AGENT", agent_text))
        if not ended and row["turns"] >= max_turns: row["failed"].append(f"call not ended after {max_turns} customer turns")
        try: freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        except RuntimeError: pass
        ledger = wait_for_close(variables["customer_id"])
        scored = score_ledger(case, ledger)
        row["failed"] += scored["failed"]
        row["tools"] = [c["tool"] for c in ledger.get("calls", [])]
        call = freya.get_call(call_id)
        infra = platform_errors(call)
        if infra: row["infra"] = infra                        # Freya's own failures, kept apart from the agent's
        ok, reason = judge(persona["successCriteria"], call)
        if not ok: row["failed"].append("conversation: " + reason)
        row["status"] = "PASS" if not row["failed"] else ("ERROR" if row.get("infra") else "FAIL")
        if row["status"] == "ERROR": row["error"] = "Freya platform: " + "; ".join(row["infra"])[:300]
        record.update(ledger=ledger, judge={"pass": ok, "reason": reason}, transcript=transcript_text(call))
    except Exception as e:                                    # infrastructure, not the agent: counted apart
        row["status"], row["error"] = "ERROR", f"{type(e).__name__}: {e}"[:400]
    row["timing"] = {"gemini_s": round(stats["gemini_s"]), "freya_s": round(stats["freya_s"]), "freya_retries": stats["freya_retries"]}
    record.update(row=row, conversation=conv, timing=stats)
    (out_dir / f"{case['id']}-{rep}.json").write_text(json.dumps(record, indent=1, default=str))
    chain = " > ".join(t.replace("verify_identity", "verify").replace("create_promise", "promise") for t in row.get("tools", [])) or "(no tool calls)"
    lines = [f"{row['status']:<5} {case['id']} {case['level']:<6} {case['family']:<14} | {chain}"]
    tm = row["timing"]
    lines.append(f"       time: customer (Gemini) {tm['gemini_s']} s, agent (Freya) {tm['freya_s']} s, Freya retries {tm['freya_retries']}")
    lines += ["       - " + f[:260] for f in row["failed"]] + (["       - " + row["error"]] if "error" in row else [])
    say("\n".join(lines))
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow_id", help="workflow id, or the agent id from freya.save_workflow"); ap.add_argument("--brief"); ap.add_argument("--only"); ap.add_argument("--out")
    ap.add_argument("--cases", default=str(KIT / "public-test-set.json"))
    ap.add_argument("--reps", type=int, default=1); ap.add_argument("--style", choices=sorted(STYLES))
    ap.add_argument("--parallel", type=int, default=3); ap.add_argument("--max-turns", type=int, default=40)
    a = ap.parse_args()
    cases = [c for c in json.load(open(a.cases)) if (not a.brief or c["brief"] == a.brief) and (not a.only or c["id"] in a.only.split(","))]
    if not cases: sys.exit("no cases selected")
    wf = workflow_for(a.workflow_id)
    out_dir = ROOT / "results" / "local" / time.strftime("%Y%m%d-%H%M%S"); out_dir.mkdir(parents=True, exist_ok=True)
    say(f"{len(cases)} cases x {a.reps} reps, customer and judge {gemini.MODEL}, {a.parallel} at a time. Transcripts: {out_dir}\n")
    t0 = time.time()
    jobs = [(c, rep) for rep in range(1, a.reps + 1) for c in cases]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        rows = list(pool.map(lambda j: run_case(wf, j[0], a.style, a.max_turns, out_dir, j[1]), jobs))
    final = []
    for c in cases:
        mine = [r for r in rows if r["id"] == c["id"]]
        passes, errors = sum(r["status"] == "PASS" for r in mine), sum(r["status"] == "ERROR" for r in mine)
        final.append({"id": c["id"], "passes": passes, "errors": errors, "runs": a.reps, "pass": passes == a.reps})
    if a.reps > 1:
        say("")
        for f in final: say(("PASS" if f["pass"] else "FAIL"), f["id"], f"{f['passes']}/{f['runs']}" + (f" ({f['errors']} error)" if f["errors"] else ""))
    n, errs = sum(f["pass"] for f in final), sum(r["status"] == "ERROR" for r in rows)
    say(f"\n{n} / {len(final)} passed{'' if a.reps == 1 else f', a customer counts with {a.reps} of {a.reps} runs'}. "
        f"{errs} run(s) ended in an infrastructure error. {time.time() - t0:.0f} s.")
    with open(ROOT / "results" / "local-log.jsonl", "a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "workflow_id": wf, "brief": a.brief, "style": a.style, "runs": a.reps,
                            "passed": n, "total": len(final), "errors": errs, "failed": [x["id"] for x in final if not x["pass"]], "dir": str(out_dir)}) + "\n")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"workflow_id": wf, "passed": n, "total": len(final), "final": final, "rows": rows}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
