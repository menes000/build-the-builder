"""Check a deployed mock of the bank's services against the case's test customers, request by request.

    python3 tester/mock_check.py https://freya-mock.freya-hecaton.workers.dev [--cases final/case/test-environment/test-customers.json]
                                 [--prefix /voice/v1/] [--parallel 10] [--only cards.list,cards.balance]

For every customer, card and week in test-customers.json it sends the request the agent would send and compares the HTTP status
and the JSON body with the file, exactly. Then the contract's error rules: unknown customer / card, empty required fields, the
delayed answer (delaySeconds). Prints one line per mismatch and a summary; exit 0 when everything matches.
Reads only the case's own data files; makes no model call.
"""
import argparse, concurrent.futures, json, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CALL = {"ani": "5000000000", "lang": "tr"}


def post(url, data, timeout=40):
    body = json.dumps({"data": data, "call": CALL}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer test",
        "User-Agent": "Mozilla/5.0 (Macintosh) freya-mock-check"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except Exception as e:                                   # connection error, timeout
        return None, f"{type(e).__name__}: {e}", time.time() - t0
    try:
        return status, json.loads(raw or b"null"), time.time() - t0
    except ValueError:
        return status, f"(not JSON) {raw[:200]!r}", time.time() - t0


def diff(a, b, path=""):
    """First difference between expected a and got b, as a short string (None if equal)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b: return f"{path}.{k} missing"
            d = diff(a[k], b[k], f"{path}.{k}")
            if d: return d
        extra = set(b) - set(a)
        return f"{path}: unexpected field(s) {sorted(extra)}" if extra else None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): return f"{path}: {len(b)} items, expected {len(a)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, f"{path}[{i}]")
            if d: return d
        return None
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool)):
        return f"{path}: type {type(b).__name__} {json.dumps(b, ensure_ascii=False)[:60]}, expected {type(a).__name__} {json.dumps(a, ensure_ascii=False)[:60]}"
    return None if a == b else f"{path}: {json.dumps(b, ensure_ascii=False)[:80]}, expected {json.dumps(a, ensure_ascii=False)[:80]}"


def checks(cases):
    """(name, service, request data, expected entry) for every answer in the file."""
    out = []
    for c in cases["customers"]:
        no, s = c["customerNo"], c["services"]
        if "cards.list" in s: out.append((f"{no} cards.list", "cards.list", {"customerNo": no, "aiFlow": "CardOps"}, s["cards.list"]))
        if "contact.email.get" in s: out.append((f"{no} contact.email.get", "contact.email.get", {"customerNo": no, "intAddressInfoType": "E"}, s["contact.email.get"]))
        cards = list((s.get("cards.balance") or {}).keys())
        if "statement.pdf.send" in s:
            stmt = next((v["response"]["data"]["statementDate"] for v in (s.get("cards.balance") or {}).values() if v.get("http") == 200), "05.10.2026")
            out.append((f"{no} statement.pdf.send", "statement.pdf.send",
                        {"customerNo": no, "cardNumber": cards[0] if cards else "540000******0000", "currencyType": "TL", "statementDate": stmt, "emailAddress": "test@freyabank.example"},
                        s["statement.pdf.send"]))
        for card, e in (s.get("cards.balance") or {}).items():
            out.append((f"{no} cards.balance {card}", "cards.balance", {"cardNumber": card}, e))
        for card, e in (s.get("statement.week.get") or {}).items():
            out.append((f"{no} statement.week.get {card}", "statement.week.get", {"cardNumber": card}, e))
        for svc in ("statement.week.decide", "statement.week.change"):
            for card, weeks in (s.get(svc) or {}).items():
                wg = (s.get("statement.week.get") or {}).get(card, {})
                day = ((wg.get("response") or {}).get("data") or {}).get("statementDay", 1)
                for wk, e in weeks.items():
                    out.append((f"{no} {svc} {card} week {wk}", svc, {"cardNumber": card, "newStatementWeek": int(wk), "statementDay": day}, e))
    return out


ERRORS = [   # (name, service, data, expected status, expected code): the contract's rules for unknown and empty input
    ("unknown customer cards.list", "cards.list", {"customerNo": "99999999", "aiFlow": "CardOps"}, 404, "FB_IVR_CHANNEL_102"),
    ("unknown card cards.balance", "cards.balance", {"cardNumber": "540000******0000"}, 404, "FB_IVR_CHANNEL_120"),
    ("unknown card statement.week.get", "statement.week.get", {"cardNumber": "540000******0000"}, 404, "FB_IVR_CHANNEL_121"),
    ("unknown card statement.week.decide", "statement.week.decide", {"cardNumber": "540000******0000", "newStatementWeek": 2, "statementDay": 5}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("unknown card statement.week.change", "statement.week.change", {"cardNumber": "540000******0000", "newStatementWeek": 2, "statementDay": 5}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("unknown customer contact.email.get", "contact.email.get", {"customerNo": "99999999", "intAddressInfoType": "E"}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("empty card number cards.balance", "cards.balance", {"cardNumber": ""}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("empty intAddressInfoType", "contact.email.get", {"customerNo": "90000001", "intAddressInfoType": ""}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("customer number as a JSON number", "cards.list", {"customerNo": 90000001, "aiFlow": "CardOps"}, 200, "1"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mock_url"); ap.add_argument("--cases", default=str(ROOT / "final/case/test-environment/test-customers.json"))
    ap.add_argument("--prefix", default="/voice/v1/"); ap.add_argument("--parallel", type=int, default=10); ap.add_argument("--only")
    a = ap.parse_args()
    base = a.mock_url.rstrip("/") + "/" + a.prefix.strip("/") + "/"
    cases = json.load(open(a.cases))
    todo = checks(cases)
    if a.only: todo = [t for t in todo if t[1] in a.only.split(",")]
    print(f"{len(todo)} answers from {a.cases} against {base}  (+ {len(ERRORS)} contract error rules)")

    def run(t):
        name, svc, data, exp = t
        status, body, secs = post(base + svc, data)
        if status is None: return name, f"no answer: {body}"
        if status != exp["http"]: return name, f"HTTP {status}, expected {exp['http']} ({json.dumps(body, ensure_ascii=False)[:120]})"
        d = diff(exp["response"], body, "body")
        if d: return name, d
        if exp.get("delaySeconds") and secs < float(exp["delaySeconds"]) * 0.9: return name, f"answered in {secs:.1f} s, expected a {exp['delaySeconds']} s delay"
        return name, None

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.parallel) as pool:
        results = list(pool.map(run, todo))
    bad = [(n, m) for n, m in results if m]
    for n, m in bad[:80]: print(f"MISMATCH {n}: {m}")
    if len(bad) > 80: print(f"... and {len(bad) - 80} more")
    print(f"\nanswers: {len(todo) - len(bad)}/{len(todo)} match ({time.time() - t0:.0f} s)")

    err_bad = 0
    for name, svc, data, st, code in ERRORS:
        status, body, _ = post(base + svc, data)
        got = ((body or {}).get("result") or {}).get("code") if isinstance(body, dict) else None
        ok = status == st and got == code
        if st != 200 and isinstance(body, dict) and "data" in body: ok = False      # error answers carry no data object
        err_bad += not ok
        print(("ok      " if ok else "MISMATCH") + f" rule: {name}: HTTP {status} code {got}" + ("" if ok else f" (expected HTTP {st} code {code})"))
    print(f"contract rules: {len(ERRORS) - err_bad}/{len(ERRORS)} ok")
    sys.exit(0 if not bad and not err_bad else 1)


if __name__ == "__main__":
    main()
