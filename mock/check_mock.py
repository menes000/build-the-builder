"""Check a deployed (or local) mock against test-customers.json: every stored answer must come back with the same
HTTP status and the same body; unknown customers / cards / weeks and empty fields must get the contract's errors.

    python3 mock/check_mock.py http://localhost:8787
    python3 mock/check_mock.py https://freya-mock.freya-hecaton.workers.dev
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1].rstrip("/") + "/voice/v1/"
DATA = json.loads((Path(__file__).parent / "src" / "test-customers.json").read_text())
SKIP_DELAY = "--skip-delay" in sys.argv


def post(svc, data):
    req = urllib.request.Request(BASE + svc, data=json.dumps({"data": data, "call": {"ani": "5000000000", "lang": "tr"}}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "freya-mock-check/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"_not_json": raw[:200].decode("utf-8", "replace")}


ok = bad = 0


def check(label, svc, data, stored):
    global ok, bad
    if SKIP_DELAY and stored.get("delaySeconds"):
        return
    t = time.time()
    status, body = post(svc, data)
    if status == stored["http"] and body == stored["response"]:
        ok += 1
    else:
        bad += 1
        print(f"FAIL {label}: got {status} {json.dumps(body, ensure_ascii=False)[:160]}  want {stored['http']}")
    if stored.get("delaySeconds"):
        print(f"delay {label}: {time.time() - t:.1f}s (stored {stored['delaySeconds']}s)")


for c in DATA["customers"]:
    no, s = c["customerNo"], c["services"]
    for svc in ("cards.list", "contact.email.get", "statement.pdf.send"):
        if svc in s:
            d = {"customerNo": no}
            if svc == "contact.email.get":
                d["intAddressInfoType"] = "E"
            if svc == "statement.pdf.send":
                d.update(cardNumber="540000******0000", currencyType="TL", statementDate="05.10.2026", emailAddress="x@y.example")
            check(f"{no} {svc}", svc, d, s[svc])
            if svc == "cards.list":
                check(f"{no} {svc} (number)", svc, {"customerNo": int(no)}, s[svc])
    for svc in ("cards.balance", "statement.week.get"):
        for card, st in (s.get(svc) or {}).items():
            check(f"{no} {svc} {card}", svc, {"cardNumber": card}, st)
    for svc in ("statement.week.decide", "statement.week.change"):
        for card, weeks in (s.get(svc) or {}).items():
            for wk, st in weeks.items():
                check(f"{no} {svc} {card} w{wk}", svc, {"cardNumber": card, "newStatementWeek": int(wk), "statementDay": 5}, st)

# contract errors
expect = [
    ("cards.list", {"customerNo": "11111111"}, 404, "FB_IVR_CHANNEL_102"),
    ("cards.balance", {"cardNumber": "999999******0000"}, 404, "FB_IVR_CHANNEL_120"),
    ("statement.week.get", {"cardNumber": "999999******0000"}, 404, "FB_IVR_CHANNEL_121"),
    ("statement.week.decide", {"cardNumber": "999999******0000", "newStatementWeek": 1, "statementDay": 5}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("contact.email.get", {"customerNo": "11111111", "intAddressInfoType": "E"}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("statement.pdf.send", {"customerNo": "11111111", "cardNumber": "x", "currencyType": "TL", "statementDate": "05.10.2026", "emailAddress": "a@b"}, 404, "FB_IVR_CHANNEL_107"),
    ("cards.balance", {"cardNumber": ""}, 400, "INVALID_ARGUMENTS_ERROR"),
    ("contact.email.get", {"customerNo": "90000001", "intAddressInfoType": ""}, 400, "INVALID_ARGUMENTS_ERROR"),
]
for svc, d, st, code in expect:
    status, body = post(svc, d)
    good = status == st and body.get("result", {}).get("code") == code and "data" not in body
    ok += good
    bad += not good
    if not good:
        print(f"FAIL error case {svc} {d}: got {status} {json.dumps(body)[:160]}")

print(f"{ok} OK, {bad} FAIL")
sys.exit(1 if bad else 0)
