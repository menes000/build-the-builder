"""A local stand-in for the organisers' bank mock, so the local tester works for any brief and any customer.

Why: the real mock (freya-bank-mock.freyavoice.workers.dev) knows only the 13 practice accounts and two identity fields
(date_of_birth, phone_last4). A brief with a postcode question, or Sunday's hidden briefs with their own customers, cannot be
scored against it. This server takes the accounts from a case file (identity fields and products as written there) and keeps
the same ledger shape, so kit/tools/score.py scores it unchanged.

Behaviour copied from probes of the real mock (10 Oct):
  verify_identity  unknown field -> ok:false; unparseable date -> ok:false "answer is not a date. Send it as YYYY-MM-DD.";
                   day/month swapped -> verified:false + hint day_month_swapped, not counted; wrong -> wrong_answers_left - 1;
                   an already verified field answers verified:true again; all_verified when every field passed; 0 left -> ok:false
  get_account, create_promise, add_note before verification -> ok:false "identity not verified" (status 200)
  create_promise   case "faults": [{"tool": "create_promise", "fail_first_n": 1}] -> first n calls status 500 "service unavailable,
                   nothing was recorded"; a second promise on a product -> "this product already has a promise"; unknown product_id
  schedule_callback, transfer_to_agent  allowed before verification (third party / human request)
  close_call       second call -> "the call is already closed"; outcome/reason of the first call stay
The mock does not enforce the brief (weekend dates, amounts below the floor are accepted); neither does this one.

    from fakebank import start; host = start(cases)        # in-process, returns "http://127.0.0.1:<port>"
    python3 tester/fakebank.py tester/coverage-cases.json   # standalone on :8765
"""
import datetime, json, re, sys, threading, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"cases": {}, "sessions": {}}
LOCK = threading.Lock()
DATE_FIELDS = ("date_of_birth", "dob", "birth_date")


def load_cases(cases):
    STATE["cases"] = {c["id"]: c for c in cases}


def _parse_date(text):
    """ISO or numeric day-month-year. Returns (iso, swapped_iso_or_None) or raises ValueError."""
    t = str(text).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m: y, a, b = int(m[1]), int(m[2]), int(m[3]); month, day = a, b
    else:
        m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", t)
        if not m: raise ValueError
        day, month, y = int(m[1]), int(m[2]), int(m[3])
    try: iso = datetime.date(y, month, day).isoformat()
    except ValueError: iso = None
    try: swapped = datetime.date(y, day, month).isoformat() if day <= 12 else None
    except ValueError: swapped = None
    if iso is None and swapped is None: raise ValueError
    return iso, swapped


def _norm(field, v):
    s = str(v).strip()
    if field in DATE_FIELDS:
        try: return _parse_date(s)[0]
        except ValueError: return s
    return re.sub(r"\s+", "", s).upper() if not s.isdigit() else s


def new_session(case_id):
    c = STATE["cases"].get(case_id)
    if not c: return None
    cid = "c_" + uuid.uuid4().hex[:8] + "-" + uuid.uuid4().hex[:3]
    products = [{"product_id": f"p{i+1}", **p} for i, p in enumerate(c.get("products") or [])]
    faults = {f["tool"]: dict(f) for f in c.get("faults") or []}
    s = {"case": case_id, "identity": dict(c.get("identity") or {}), "products": products, "faults": faults,
         "now": (c.get("variables") or {}).get("now"), "verified": {}, "wrong": 0, "hinted": False, "left": 3,
         "promises": [], "notes": [], "callbacks": [], "transfers": [], "outcome": None, "reason": None, "closed": False,
         "failures": {}, "calls": []}
    with LOCK: STATE["sessions"][cid] = s
    return cid, {"customer_id": cid, **{k: v for k, v in (c.get("variables") or {}).items() if k != "customer_id"}}


def handle(path, body):
    """Returns (status, result). Records the call in the ledger like the real mock."""
    tool = path.rsplit("/", 1)[-1]
    if tool == "sessions":
        r = new_session((body or {}).get("case"))
        return (200, {"ok": True, "variables": r[1]}) if r else (404, {"ok": False, "error": "unknown practice case"})
    cid = (body or {}).get("customer_id")
    s = STATE["sessions"].get(cid)
    if not s: return 404, {"ok": False, "error": "unknown customer_id"}
    args = {k: v for k, v in body.items() if k != "customer_id"}
    status, res = 200, {"ok": True}
    with LOCK:
        all_ok = lambda: all(s["verified"].get(f) for f in s["identity"])
        if tool == "verify_identity":
            field, answer = args.get("field"), args.get("answer")
            if field not in s["identity"]:
                res = {"ok": False, "error": "field must be " + " or ".join(s["identity"])}
            elif s["left"] <= 0:
                res = {"ok": False, "error": "too many wrong answers, the identity check is closed"}
            elif s["verified"].get(field):
                res = {"ok": True, "verified": True, "wrong_answers_left": s["left"], "all_verified": all_ok()}
            else:
                truth = _norm(field, s["identity"][field])
                if field in DATE_FIELDS:
                    try: iso, swapped = _parse_date(answer)
                    except ValueError: iso = swapped = None; res = {"ok": False, "error": "answer is not a date. Send it as YYYY-MM-DD."}
                    if res.get("ok"):
                        if iso == truth: s["verified"][field] = True; res = {"ok": True, "verified": True, "wrong_answers_left": s["left"], "all_verified": all_ok()}
                        elif swapped == truth: s["hinted"] = True; res = {"ok": True, "verified": False, "wrong_answers_left": s["left"], "hint": "day_month_swapped"}
                        else: s["wrong"] += 1; s["left"] -= 1; res = {"ok": True, "verified": False, "wrong_answers_left": s["left"], "all_verified": False}
                else:
                    if _norm(field, answer) == truth: s["verified"][field] = True; res = {"ok": True, "verified": True, "wrong_answers_left": s["left"], "all_verified": all_ok()}
                    else: s["wrong"] += 1; s["left"] -= 1; res = {"ok": True, "verified": False, "wrong_answers_left": s["left"], "all_verified": False}
        elif tool in ("get_account", "create_promise", "add_note") and not all_ok():
            res = {"ok": False, "error": "identity not verified"}
        elif tool == "get_account":
            res = {"ok": True, "products": [dict(p) for p in s["products"]]}
        elif tool == "create_promise":
            f = s["faults"].get("create_promise")
            if f and f.get("fail_first_n", 0) > 0:
                f["fail_first_n"] -= 1; status, res = 500, {"ok": False, "error": "service unavailable, nothing was recorded"}
            else:
                pid = args.get("product_id"); prod = next((p for p in s["products"] if p["product_id"] == pid), None)
                if not prod: res = {"ok": False, "error": "unknown product_id"}
                elif any(p["product_id"] == pid for p in s["promises"]): res = {"ok": False, "error": "this product already has a promise"}
                else:
                    try: amount = float(args.get("amount")); datetime.date.fromisoformat(str(args.get("date")))
                    except (TypeError, ValueError): amount = None
                    if amount is None: res = {"ok": False, "error": "amount must be a number and date YYYY-MM-DD"}
                    else:
                        s["promises"].append({"promise_id": f"pr{len(s['promises'])+1}", "product_id": pid, "type": prod.get("type"), "amount": amount, "date": args["date"]})
                        res = {"ok": True, "promise_id": s["promises"][-1]["promise_id"]}
        elif tool == "add_note":
            s["notes"].append({"product_id": args.get("product_id"), "reason": args.get("reason"), "text": args.get("text", "")})
        elif tool == "schedule_callback":
            s["callbacks"].append({"date": args.get("date"), "time": args.get("time")})
        elif tool == "transfer_to_agent":
            s["transfers"].append({"queue": args.get("queue")})
        elif tool == "close_call":
            if s["closed"]: res = {"ok": False, "error": "the call is already closed"}
            else: s["closed"] = True; s["outcome"] = args.get("outcome"); s["reason"] = args.get("reason") or None
        else:
            status, res = 404, {"ok": False, "error": f"unknown tool {tool}"}
        s["failures"][tool] = s["failures"].get(tool, 0) + (1 if status >= 500 else 0)      # the real mock counts service faults only
        s["calls"].append({"n": len(s["calls"]) + 1, "tool": tool, "args": args, "status": status, "result": res})
    return status, res


def ledger(cid):
    s = STATE["sessions"].get(cid)
    if not s: return 404, {"ok": False, "error": "unknown customer_id"}
    return 200, {"ok": True, "case": s["case"], "team": "local", "now": s["now"], "verified": dict(s["verified"]), "wrong": s["wrong"], "hinted": s["hinted"],
                 "promises": list(s["promises"]), "notes": list(s["notes"]), "callbacks": list(s["callbacks"]), "transfers": list(s["transfers"]),
                 "outcome": s["outcome"], "reason": s["reason"], "failures": dict(s["failures"]), "calls": list(s["calls"])}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if "/practice/ledger/" in self.path: return self._send(*ledger(self.path.rsplit("/", 1)[-1]))
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._send(400, {"ok": False, "error": "bad json"})
        self._send(*handle(self.path.split("?")[0], body if isinstance(body, dict) else {}))


def start(cases, port=0):
    """Start the server on a thread; returns the base URL (no /v1)."""
    load_cases(cases)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


if __name__ == "__main__":
    cases = json.load(open(sys.argv[1]))
    print("fake bank for", len(cases), "cases on", start(cases, int(sys.argv[2]) if len(sys.argv) > 2 else 8765))
    threading.Event().wait()
