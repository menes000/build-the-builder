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

STATE = {"cases": {}, "sessions": {}, "map": None, "api": None}
CANON_RESP = {"verify_identity": ["ok", "error", "verified", "all_verified", "wrong_answers_left", "hint"], "get_account": ["ok", "error", "products"],
              "create_promise": ["ok", "error", "promise_id"], "add_note": ["ok", "error"], "schedule_callback": ["ok", "error"],
              "transfer_to_agent": ["ok", "error"], "close_call": ["ok", "error"]}


def load_openapi(path_or_obj):
    """Request rules per tool from the brief's openapi.json: required fields, enums, method. Unknown shapes are tolerated."""
    o = json.load(open(path_or_obj)) if isinstance(path_or_obj, str) else path_or_obj
    api = {}
    for path, methods in (o.get("paths") or {}).items():
        tool = path.rstrip("/").rsplit("/", 1)[-1]
        for method, op in methods.items():
            if method.lower() not in ("post", "get", "put"): continue
            schema = ((((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {})
            props = schema.get("properties") or {}
            if method.lower() == "get":
                props = {p["name"]: p.get("schema") or {} for p in op.get("parameters") or [] if p.get("in") == "query"}
                required = [p["name"] for p in op.get("parameters") or [] if p.get("in") == "query" and p.get("required")]
            else: required = list(schema.get("required") or [])
            enums = {k: v["enum"] for k, v in props.items() if isinstance(v, dict) and v.get("enum")}
            resp = ((((op.get("responses") or {}).get("200") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
            api[tool] = {"method": method.upper(), "required": required, "enums": enums, "fields": list(props), "resp_fields": list((resp.get("properties") or {}))}
    STATE["api"] = api
    return api


def audit():
    """Where the brief's API differs from what this bank can imitate: response fields it will not produce (the ledger path is then unreliable)."""
    out = []
    fm = STATE["map"] or {}
    for tool, spec in (STATE["api"] or {}).items():
        if tool not in CANON_RESP: out.append(f"{tool}: unknown tool, the fake bank answers 404"); continue
        known = {((fm.get("resp") or {}).get(tool) or {}).get(k, k) for k in CANON_RESP[tool]}
        missing = [f for f in spec["resp_fields"] if f not in known]
        if missing: out.append(f"{tool}: response fields the fake bank never sends: {missing} (hooks reading them get nothing locally)")
        if spec["method"] != "POST": out.append(f"{tool}: method {spec['method']} (supported)")
    return out


def validate(tool, body):
    """Required fields and enums from the openapi, before translation. Returns an error string or None."""
    spec = (STATE["api"] or {}).get(tool)
    if not spec: return None
    for f in spec["required"]:
        if body.get(f) in (None, ""): return f"missing required field {f}"
    for f, allowed in spec["enums"].items():
        if f in body and body[f] not in (None, "") and str(body[f]) not in map(str, allowed): return f"{f} must be one of {allowed}"
    return None

LOCK = threading.Lock()
DATE_FIELDS = ("date_of_birth", "dob", "birth_date")
CANON_REQ = {"verify_identity": ["customer_id", "field", "answer"], "get_account": ["customer_id"], "create_promise": ["customer_id", "product_id", "amount", "date"],
             "add_note": ["customer_id", "product_id", "reason", "text"], "schedule_callback": ["customer_id", "date", "time"],
             "transfer_to_agent": ["customer_id", "queue"], "close_call": ["customer_id", "outcome", "reason"]}


def is_date_field(f): return f in DATE_FIELDS or "birth" in str(f).lower() or str(f).lower() == "dob"


def load_cases(cases, field_map=None):
    """`field_map` = the builder's CallSpec field_map ({"req": {tool: {canonical: actual}}, "resp": {...}, "product": {canonical: actual}}).
    The hidden briefs may rename fields (the seven tool names stay); requests are translated actual -> canonical, responses canonical -> actual."""
    STATE["cases"] = {c["id"]: c for c in cases}
    fm = field_map or next((c.get("field_map") for c in cases if c.get("field_map")), None)
    STATE["map"] = fm if fm and (fm.get("req") or fm.get("resp") or fm.get("product")) else None


def to_canon(tool, body):
    m = ((STATE["map"] or {}).get("req") or {}).get(tool) or {}
    back = {actual: canon for canon, actual in m.items()}
    return {back.get(k, k): v for k, v in body.items()}


def to_actual(tool, res):
    fm = STATE["map"] or {}
    m = (fm.get("resp") or {}).get(tool) or {}
    out = {m.get(k, k): v for k, v in res.items()}
    pm = fm.get("product") or {}
    if tool == "get_account" and pm and isinstance(out.get(m.get("products", "products")), list):
        key = m.get("products", "products")
        out[key] = [{pm.get(k, k): v for k, v in p.items()} for p in out[key]]
    return out


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
    if is_date_field(field):
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
         "now": (c.get("variables") or {}).get("now"), "verified": {}, "wrong": 0, "hinted": False, "left": int(c.get("identity_max_wrong") or 3),
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
    bad = validate(tool, body or {})
    if bad: return 400, {"ok": False, "error": bad}
    body = to_canon(tool, body or {})
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
                if is_date_field(field):
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
    return status, to_actual(tool, res)


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
        path, _, query = self.path.partition("?")
        tool = path.rstrip("/").rsplit("/", 1)[-1]
        if tool in CANON_RESP:                                   # a GET tool with query parameters (allowed by some APIs)
            import urllib.parse
            body = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
            return self._send(*handle(path, body))
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._send(400, {"ok": False, "error": "bad json"})
        self._send(*handle(self.path.split("?")[0], body if isinstance(body, dict) else {}))


def start(cases, port=0, field_map=None, openapi=None):
    """Start the server on a thread; returns the base URL (no /v1). `openapi`: path to the brief's tool API for request validation."""
    load_cases(cases, field_map)
    if openapi: load_openapi(openapi)
    elif not STATE["api"]:
        oa = next((c.get("openapi") for c in cases if c.get("openapi")), None)
        if oa: load_openapi(oa)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


if __name__ == "__main__":
    cases = json.load(open(sys.argv[1]))
    print("fake bank for", len(cases), "cases on", start(cases, int(sys.argv[2]) if len(sys.argv) > 2 else 8765))
    threading.Event().wait()
