"""Compare a fresh extraction against a reference: structured fields and the numbers the compiled agent computes.

    python3 builder/test/regression_compare.py

For A, A+B and C the reference is a hand-checked CallSpec (fixtures/). For D and E the reference is the answer key's
computed values (test-briefs/keys/), written here as expectations for the practical "now" 2026-10-14T11:00.
Prints one line per check: OK / DIFF.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from builder.build_from_spec import build  # noqa: E402
from builder.compile.selfcheck import facts_preview  # noqa: E402

NOW = "2026-10-14T11:00"
OUT = ROOT / "out"


def fields(s: dict) -> dict:
    d, i, cb = s["dates"], s["identity"], s["third_party"]["callback"]
    return {
        "holidays": sorted(d["holidays"]),
        "bands": [(b["days_late_min"], b["days_late_max"], b.get("deadline_business_days_after_today"), b.get("deadline_calendar_days_after_today"), b["persuasion_attempts"]) for b in d["bands"]],
        "identity": [q["field"] for q in i["questions"]],
        "max_wrong": i["max_wrong_total"],
        "queues": [s["special"]["hardship"]["offer_queue"], s["special"]["restructuring"]["queue"], s["special"]["human"]["queue"]],
        "promise_outcome": s["closing"]["promise_outcome"],
        "callback": (cb["time_from"], cb["time_to"], cb.get("allow_today"), cb.get("max_business_days_ahead", 1)),
        "multi": s["multi_product"]["enabled"],
        "att1": (s["persuasion"]["attempt1_date_kind"], s["persuasion"].get("attempt1_business_days", 0)),
    }


def facts(wf, accounts):
    v = facts_preview(wf, NOW, accounts)
    fs = json.loads(v.get("facts_json") or "[]")
    return {"facts": [(f["pid"], f["band"], f["deadline"], f["att1"], f["floor"], f["attempts"]) for f in fs],
            "callback_days": [x.split(" (")[1][:10] for x in (v.get("callback_text") or "").split(" or ") if " (" in x],
            "question": (v.get("debt_statement") or "").split(". ")[-1]}


ACC = {
    "A": [[{"product_id": "p1", "type": "car_loan", "past_due": 1250.0, "days_late": 14, "instalment_amount": 400.0}],
          [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.0, "days_late": 5, "minimum_payment": 153.0}]],
    "AB": [[{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.0, "days_late": 16, "minimum_payment": 153.0},
            {"product_id": "p2", "type": "personal_loan", "past_due": 1320.0, "days_late": 16, "instalment_amount": 440.0},
            {"product_id": "p3", "type": "car_loan", "past_due": 140.0, "days_late": 3, "instalment_amount": 46.0}]],
}


def compare(name, new_spec, ref_spec, openapi, accounts):
    from builder.extract.callspec import CallSpec
    n = CallSpec.model_validate_json(Path(new_spec).read_text()).model_dump()
    r = CallSpec.model_validate_json(Path(ref_spec).read_text()).model_dump()   # older references get today's defaults
    fn, fr = fields(n), fields(r)
    bad = [k for k in fr if fn[k] != fr[k]]
    for k in fr:
        print(f"  {'OK  ' if k not in bad else 'DIFF'} {name} {k}: {fn[k]}" + ("" if k not in bad else f"   reference: {fr[k]}"))
    wn, _ = build(new_spec, openapi)
    wr, _ = build(ref_spec, openapi)
    for acc in accounts:
        a, b = facts(wn, acc), facts(wr, acc)
        for k in a:
            ok = a[k] == b[k]
            print(f"  {'OK  ' if ok else 'DIFF'} {name} computed {k}: {a[k]}" + ("" if ok else f"   reference: {b[k]}"))


def expect(name, new_spec, openapi, acc, want):
    wf, problems = build(new_spec, openapi)
    if problems:
        print(f"  DIFF {name} compile problems: {problems[:3]}")
    got = facts(wf, acc)
    for k, v in want.items():
        g = got["facts"] if k == "facts" else got[k]
        if k == "question":
            ok = all(w in g for w in v)
        else:
            ok = g == v
        print(f"  {'OK  ' if ok else 'DIFF'} {name} {k}: {g}" + ("" if ok else f"   expected: {v}"))


if __name__ == "__main__":
    kit_api = str(ROOT / "kit/tools/openapi.json")
    tb = ROOT.parent / "test-briefs"
    print("== A"); compare("A", str(OUT / "brief-a.callspec.json"), str(ROOT / "fixtures/callspec_brief_a.json"), kit_api, ACC["A"])
    print("== A+B"); compare("AB", str(OUT / "brief-ab.callspec.json"), str(ROOT / "fixtures/callspec_brief_ab.json"), kit_api, ACC["AB"])
    print("== C (postcode question dropped in this copy)")
    c_ref = json.loads((ROOT / "fixtures/callspec_brief_c.claude.json").read_text())
    c_ref["identity"]["questions"] = [q for q in c_ref["identity"]["questions"] if q["field"] != "postcode"]
    (ROOT / "scripts_tmp").mkdir(exist_ok=True)
    (ROOT / "scripts_tmp/c_ref.json").write_text(json.dumps(c_ref))
    compare("C", str(OUT / "brief-c.callspec.json"), str(ROOT / "scripts_tmp/c_ref.json"), str(tb / "brief-c/openapi.json"),
            [[{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.0, "days_late": 16, "minimum_payment": 153.0}]])
    print("== D (answer key values)")
    expect("D", str(OUT / "brief-d.callspec.json"), str(tb / "brief-d/openapi.json"),
           [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.5, "days_late": 16, "minimum_payment": 153.0},
            {"product_id": "p2", "type": "personal_loan", "past_due": 540.0, "days_late": 3, "instalment_amount": 180.0},
            {"product_id": "p3", "type": "car_loan", "past_due": 1250.0, "days_late": 30, "instalment_amount": 400.0}],
           {"facts": [("p1", "second", "2026-10-27", "2026-10-20", 256.0, 2), ("p2", "first", "2026-11-06", "2026-10-20", 270.0, 2),
                      ("p3", "final", "2026-10-19", "2026-10-19", 625.0, 1)],
            "callback_days": ["2026-10-15", "2026-10-19"],
            "question": ["clear this today"]})
    print("== E (answer key values)")
    expect("E", str(OUT / "brief-e.callspec.json"), str(tb / "brief-e/openapi.json"),
           [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 300.0, "days_late": 12, "minimum_payment": 45.0},
            {"product_id": "p2", "type": "personal_loan", "past_due": 999.0, "days_late": 40, "instalment_amount": 333.0}],
           {"facts": [("p1", "standard", "2026-10-28", "2026-10-28", 45.0, 1), ("p2", "priority", "2026-10-23", "2026-10-23", 167.0, 1)],
            "callback_days": ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17"],
            "question": ["by tomorrow", "15 October"]})
