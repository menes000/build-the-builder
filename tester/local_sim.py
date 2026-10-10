"""Run practice cases against a phone agent without Freya's simulation queue.

Gemini plays the customer with the same persona prompt as tools/run_cases.py, and Gemini judges the transcript
against the case's checks. The bank's records are scored with tools/score.py. A case passes when both pass.

Two ways to run the phone agent (--agent):
  freya  (default) the agent runs on Freya (experimental-5), reached turn by turn through the chat API.
  local  the workflow JSON runs in tester/emulator.py with Gemini as the agent model, code and hooks in local Python.
         No Freya request during calls: give a workflow file, or an id (the workflow is downloaded once).
         An approximation of Freya's runtime; confirm a result on Freya before trusting it.

    python3 tester/local_sim.py <workflow_id | agent_id | slot | workflow.json> [--agent freya|local] [--brief A|B]
                                [--only PUB-01,PUB-04] [--cases file.json] [--reps 3] [--style in_words] [--parallel 3]
                                [--max-turns 40] [--out results/local.json]

Needs FREYA_BANK_TEAM_KEY and GEMINI_API_KEY, and FREYA_API_KEY unless --agent local is given a file.
"""
import argparse, concurrent.futures, json, os, pathlib, re, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "docs" / "build-the-builder"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(ROOT / "tester"))
import emulator, freya, gemini
from run_cases import STYLES, persona_for
from score import http, score_ledger

FIRST_LINE = "Hello?"                        # the customer picks up the phone
BYE_RE = re.compile(r"\b(good-?\s?bye|bye)\b[\s!.]*$|\bbye\b", re.I)   # "Goodbye.", "Bye!", "bye bye"
BYE = ("goodbye", "good bye", "bye.")                                  # kept for FreyaAgent.hung_up
JUDGE_THINKING = os.environ.get("JUDGE_THINKING", "low")               # Gemini 3 thinkingLevel for the judge; the 215 s judge was a runaway
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
    if pathlib.Path(given).exists(): return given
    try:                                                      # a workflow made elsewhere, e.g. by a teammate's builder
        listed = freya.api("GET", "/api/v2/workflow", workspaceId=freya.workspace_id())
        for w in listed.get("workflows", []) if isinstance(listed, dict) else listed:
            if given in (w.get("id"), w.get("name"), w.get("agentId")): return w["id"]
    except RuntimeError: pass
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


def node_path(call):
    """The nodes the engine entered, from the call's node_enter events."""
    out = []
    for m in call.get("messages", []):
        if m.get("role") != "system": continue
        try: e = json.loads(m.get("message") or "")
        except ValueError: continue
        if e.get("event") == "node_enter": out.append(e.get("node"))
    return out


def behaviour_flags(call):
    """Engine events that point at agent behaviour (not infrastructure): silent turns, a resumed call after it ended, repeated rejections."""
    out, ended, rejected = [], False, {}
    for m in call.get("messages", []):
        if m.get("role") != "system": continue
        try: e = json.loads(m.get("message") or "")
        except ValueError: continue
        text = json.dumps(e)
        if "no speakable content" in text: out.append("the model returned no speakable content")
        if e.get("event") == "function_call_complete":
            res = e.get("result"); data = res.get("data") if isinstance(res, dict) else None
            if (isinstance(res, dict) and res.get("status") == "error") or (isinstance(data, dict) and data.get("ok") is False):
                f = e.get("function"); rejected[f] = rejected.get(f, 0) + 1
                if rejected[f] == 2: out.append(f"{f} rejected/failed {rejected[f]}x in one call: the model keeps retrying")
        if e.get("event") == "call_ended": ended = True
        elif ended and e.get("event") == "node_enter": out.append(f"engine entered {e.get('node')} after the call ended (runner sent a turn too many)"); ended = False
    return out


def transcript_text(call, endpoints=None):
    """User and agent lines plus the tool calls, as plain text for the judge. `endpoints` maps workflow tool names to bank API names."""
    out, ep = [], endpoints or {}
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
                out.append(f"TOOL CALL {ep.get(ev.get('function'), ev.get('function'))}: {json.dumps(args)[:400]}")
            elif ev.get("event") == "function_call_complete":
                res = ev.get("result")
                res = res.get("data", res) if isinstance(res, dict) else res
                out.append(f"TOOL RESULT {ep.get(ev.get('function'), ev.get('function'))}: {json.dumps(res)[:400]}")
    return "\n".join(out)


class FreyaAgent:
    """The phone agent on Freya, through the chat API."""
    endpoints = {}                                                 # set once per run from the workflow JSON (main)

    def __init__(self, workflow_id, variables, stats):
        self.wf, self.variables, self.stats, self.call_id, self.last = workflow_id, variables, stats, None, None
        self.call = None

    def start(self, first):
        r = agent_turn({"workflowId": self.wf, "message": first, "customerVariables": self.variables}, None, None, stats=self.stats)
        self.call_id, self.last = r["callId"], r.get("response") or ""
        return self.last, bool(r.get("endedByAgent"))

    def send(self, message):
        r = agent_turn({"callId": self.call_id, "message": message}, self.call_id, self.last, stats=self.stats)
        self.last = r.get("response") or ""
        self.stats.setdefault("chat_replies", []).append({k: v for k, v in r.items() if k != "response"})
        return self.last, bool(r.get("endedByAgent")) or self.hung_up()

    def hung_up(self):
        """The chat reply did not say the agent ended the call in the smoke test, although end_call had run. When the agent's
        line sounds like a farewell, read the call once: a set endedReason means the engine hung up (one GET, not per turn)."""
        if not self.last or not any(b in self.last.lower() for b in BYE): return False
        try: ended = bool(freya.get_call(self.call_id).get("endedReason"))
        except RuntimeError: return False
        if ended: self.stats["ended_detected_by"] = "endedReason after farewell"
        return ended

    def finish(self):
        try: freya.api("POST", "/api/v2/chat/end", {"callId": self.call_id})
        except RuntimeError: pass

    def result(self):
        """(transcript text for the judge, platform errors, behaviour flags, node path), read from Freya after the end-of-call tools ran."""
        self.call = freya.get_call(self.call_id)
        return transcript_text(self.call, self.endpoints), platform_errors(self.call), behaviour_flags(self.call), node_path(self.call)


class LocalAgent:
    """The phone agent's workflow run by tester/emulator.py, with Gemini as the agent model."""
    def __init__(self, workflow, variables, stats):
        self.agent, self.call_id = emulator.LocalAgent(workflow, variables), "local"

    def start(self, first):
        text = self.agent.start(first)
        return text, self.agent.ended

    def send(self, message): return self.agent.send(message)

    def finish(self): self.agent.finish()

    def result(self):
        flags = list(self.agent.warnings) + ["routed by intent: " + r for r in self.agent.routes]
        return self.agent.transcript_text(), ["emulator: " + x for x in self.agent.infra], flags, list(self.agent.path)


def for_judge(transcript, view):
    """What the judge reads. 'tools': spoken lines plus the bank tool calls (code_exec, end_call and engine lines dropped,
    they are noise the organisers' checks never mention). 'spoken': the conversation only, as a judge that sees no tool log."""
    out = []
    for line in transcript.splitlines():
        if line.startswith(("TOOL CALL code_exec", "TOOL RESULT code_exec", "TOOL CALL end_call", "TOOL RESULT end_call", "ENGINE:")): continue
        if view == "spoken" and line.startswith(("TOOL CALL", "TOOL RESULT")): continue
        out.append(line)
    return "\n".join(out)


def judge(criteria, transcript):
    raw = gemini.generate(JUDGE.format(criteria=criteria), [("user", transcript)], json_mode=True, temperature=0, thinking=JUDGE_THINKING or None)
    try:
        v = json.loads(raw)
        return bool(v.get("pass")), str(v.get("reason", ""))
    except ValueError:
        return False, "judge returned no JSON: " + raw[:200]


def run_case(target, case, style, max_turns, out_dir, rep, backend="freya", judge_view="tools"):
    """One customer, one call. Returns a row like run_cases.py, with status PASS, FAIL or ERROR."""
    persona = persona_for(case, {"identity": case["identity"]}, style)
    row = {"id": case["id"], "level": case["level"], "family": case["family"], "rep": rep, "failed": [], "turns": 0}
    conv, record = [], {"case": case["id"], "style": style, "persona": persona["prompt"], "agent": backend}
    stats = {"gemini_s": 0.0, "freya_s": 0.0, "freya_retries": 0, "turns": []}
    try:
        variables = http("/v1/practice/sessions", {"case": case.get("session_case", case["id"])})["variables"]   # our cases borrow a PUB account
        for k, v in (case.get("variables") or {}).items():                                                     # the case's own calendar day or time wins
            if k != "customer_id" and v not in (None, ""): variables[k] = v
        record["variables"] = variables; row["customer_id"] = variables["customer_id"]
        agent = (LocalAgent if backend == "local" else FreyaAgent)(target, variables, stats)
        t = time.time()
        agent_text, ended = agent.start(FIRST_LINE)
        stats["freya_s"] += time.time() - t
        row["call_id"], customer_said_bye = agent.call_id, False
        conv.append(("AGENT", agent_text))
        history = []
        while not ended and row["turns"] < max_turns and not customer_said_bye:
            history.append(("user", agent_text or "(silence)"))
            t = time.time(); customer = gemini.generate(persona["prompt"], history, temperature=1.0); g = time.time() - t
            history.append(("model", customer)); conv.append(("CUSTOMER", customer)); row["turns"] += 1
            customer_said_bye = bool(BYE_RE.search(customer))
            t = time.time(); agent_text, ended = agent.send(customer); f = time.time() - t
            stats["gemini_s"] += g; stats["freya_s"] += f; stats["turns"].append({"gemini_s": round(g, 1), "freya_s": round(f, 1)})
            conv.append(("AGENT", agent_text))
        if not ended and row["turns"] >= max_turns: row["failed"].append(f"call not ended after {max_turns} customer turns")
        agent.finish()
        ledger = wait_for_close(variables["customer_id"], seconds=45 if backend == "freya" else 5)
        scored = score_ledger(case, ledger)
        row["failed"] += scored["failed"]
        row["tools"] = [c["tool"] for c in ledger.get("calls", [])]
        transcript, infra, flags, path = agent.result()
        if infra: row["infra"] = infra                        # platform (or emulator) failures, kept apart from the agent's
        if flags: row["flags"] = flags                        # agent behaviour worth a look, pass or fail
        row["path"] = path
        record.update(ledger=ledger, transcript=transcript)  # kept even when the judge call fails
        t = time.time(); ok, reason = judge(persona["successCriteria"], for_judge(transcript, judge_view)); stats["judge_s"] = round(time.time() - t, 1)
        if not ok: row["failed"].append("conversation: " + reason)
        row["status"] = "PASS" if not row["failed"] else ("ERROR" if row.get("infra") else "FAIL")
        if row["status"] == "ERROR": row["error"] = "Freya platform: " + "; ".join(row["infra"])[:300]
        record.update(ledger=ledger, judge={"pass": ok, "reason": reason}, transcript=transcript)
    except Exception as e:                                    # infrastructure, not the agent: counted apart
        row["status"], row["error"] = "ERROR", f"{type(e).__name__}: {e}"[:400]
    row["timing"] = {"gemini_s": round(stats["gemini_s"]), "freya_s": round(stats["freya_s"]), "freya_retries": stats["freya_retries"]}
    record.update(row=row, conversation=conv, timing=stats)
    (out_dir / f"{case['id']}-{rep}.json").write_text(json.dumps(record, indent=1, default=str))
    chain = " > ".join(t.replace("verify_identity", "verify").replace("create_promise", "promise") for t in row.get("tools", [])) or "(no tool calls)"
    lines = [f"{row['status']:<5} {case['id']} {case['level']:<6} {case['family']:<14} | {chain}"]
    tm = row["timing"]
    lines.append(f"       time: customer (Gemini) {tm['gemini_s']} s, agent ({backend}) {tm['freya_s']} s" + (f", Freya retries {tm['freya_retries']}" if backend == "freya" else ""))
    if row.get("path"): lines.append("       path: " + " > ".join(row["path"]))
    lines += ["       - " + f[:260] for f in row["failed"]] + (["       - " + row["error"]] if "error" in row else [])
    lines += ["       ! " + f[:200] for f in row.get("flags", [])]
    say("\n".join(lines))
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow_id", help="workflow id, agent id, slot name, or (with --agent local) a workflow JSON file"); ap.add_argument("--brief"); ap.add_argument("--only"); ap.add_argument("--out")
    ap.add_argument("--agent", choices=["freya", "local"], default="freya", help="freya: agent on Freya via chat API. local: workflow emulated with Gemini")
    ap.add_argument("--cases", default=str(KIT / "public-test-set.json"))
    ap.add_argument("--reps", type=int, default=1); ap.add_argument("--style", choices=sorted(STYLES))
    ap.add_argument("--parallel", type=int, default=3); ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--judge-view", choices=["tools", "spoken"], default="tools", help="what the judge reads: conversation plus bank tool calls, or the conversation only")
    a = ap.parse_args()
    cases = [c for c in json.load(open(a.cases)) if (not a.brief or c["brief"] == a.brief) and (not a.only or c["id"] in a.only.split(","))]
    if not cases: sys.exit("no cases selected")
    wf = workflow_for(a.workflow_id)
    target = emulator.load_workflow(wf) if a.agent == "local" else wf
    if a.agent == "freya":
        try: FreyaAgent.endpoints = emulator.endpoints_of(emulator.load_workflow(wf))      # one GET, so the judge reads API names
        except Exception as e: say(f"(could not load the workflow for tool names: {e})")
    out_dir = ROOT / "results" / "local" / time.strftime("%Y%m%d-%H%M%S"); out_dir.mkdir(parents=True, exist_ok=True)
    agent_desc = f"agent emulated locally with {emulator.AGENT_MODEL}" if a.agent == "local" else "agent on Freya"
    say(f"{len(cases)} cases x {a.reps} reps, {agent_desc}, customer and judge {gemini.MODEL} (judge sees: {a.judge_view}), {a.parallel} at a time. Transcripts: {out_dir}\n")
    t0 = time.time()
    jobs = [(c, rep) for rep in range(1, a.reps + 1) for c in cases]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        rows = list(pool.map(lambda j: run_case(target, j[0], a.style, a.max_turns, out_dir, j[1], a.agent, a.judge_view), jobs))
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
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "workflow_id": wf, "agent": a.agent, "cases": a.cases, "brief": a.brief, "style": a.style, "runs": a.reps,
                            "passed": n, "total": len(final), "errors": errs, "failed": [x["id"] for x in final if not x["pass"]], "dir": str(out_dir)}) + "\n")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"workflow_id": wf, "passed": n, "total": len(final), "final": final, "rows": rows}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
