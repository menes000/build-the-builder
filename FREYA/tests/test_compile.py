"""Compiled workflow structure, date facts, field mapping."""
import json
import sys
from pathlib import Path

from conftest import ROOT, tool

sys.path.insert(0, str(ROOT))
from builder.build_from_spec import build  # noqa: E402
from builder.compile.selfcheck import facts_preview  # noqa: E402


def test_single_product_shape(wf_a):
    n = wf_a["nodes"]
    assert "security_explain" in n and "after_promise" in n and "close_on_goodbye" in n and "close_on_transfer" in n
    assert [t["function"]["name"] for t in n["negotiate"]["tools"]] == ["create_promise", "note_refusal", "transfer_to_agent"]
    assert [t["function"]["name"] for t in n["after_promise"]["tools"]] == ["transfer_to_agent"]
    assert n["negotiate"]["transitions"][0]["target_node"] == "after_promise"
    assert "customer_id" not in wf_a["test_variables"]
    sec = tool(wf_a, "security", "transfer_to_agent")
    assert sec["function"]["parameters"]["properties"]["body"]["properties"]["queue"]["default"] == "general"


def test_multi_product_shape(wf_ab):
    n = wf_ab["nodes"]
    assert "after_promise" not in n
    assert "add_note" in [t["function"]["name"] for t in n["negotiate"]["tools"]]
    first = n["negotiate"]["transitions"][0]
    assert first["target_node"] == "close_promise" and len(first["condition"]["conditions"]) > 10  # counter combos


def test_dates_brief_a(wf_a):
    v = facts_preview(wf_a, "2026-10-14T11:00", [{"product_id": "p1", "type": "car_loan", "past_due": 1250.0, "days_late": 14, "instalment_amount": 400.0}])
    f = json.loads(v["facts_json"])[0]
    assert f["band"] == "late" and f["deadline"] == "2026-10-23" and f["att1"] == "2026-10-16" and f["floor"] == 400.0
    v = facts_preview(wf_a, "2026-10-14T11:00", [{"product_id": "p1", "type": "personal_loan", "past_due": 540.0, "days_late": 5, "instalment_amount": 180.0}])
    f = json.loads(v["facts_json"])[0]
    assert f["band"] == "early" and f["deadline"] == "2026-11-02"  # 12 business days, 26 Oct holiday skipped
    assert "2026-10-26" not in f["valid"] and "2026-10-27" in f["valid"]
    assert v["debt_statement"].startswith("Thank you, the security check is complete. I am calling from the collections team about a late payment.")
    assert "collections team" in v["debt_statement"] and v["next_question"] == "What is your date of birth?"
    assert v["outcome"] == "no_promise" and v["reason"] == "refused"


def test_renamed_api_is_mapped(wf_c_renamed):
    sec = tool(wf_c_renamed, "security", "verify_identity")
    assert sec["response_mapping"][0]["path"] == "data.id_state"
    assert any(c.get("variable") == "verify_identity_response.data.fully_verified"
               for c in wf_c_renamed["nodes"]["security"]["transitions"][0]["condition"]["conditions"])
    cp = tool(wf_c_renamed, "negotiate", "create_promise")
    keys = cp["function"]["parameters"]["properties"]["body"]["properties"].keys()
    assert "promise_date" in keys and "payment_amount" in keys
    assert wf_c_renamed["nodes"]["load_account"]["response_mapping"][0]["path"] == "data.accounts"
    v = facts_preview(wf_c_renamed, "2026-10-14T11:00", [{"product_id": "p1", "type": "credit_card", "last4": "9015", "overdue_amount": 510, "days_overdue": 16, "min_payment": 153}])
    assert v["account_state"] == "ok" and json.loads(v["facts_json"])[0]["floor"] == 153


def test_no_brief_values_in_compiler_code():
    """Brief A constants must not live in the compiler; they come from the CallSpec."""
    src = "".join(Path(p).read_text() for p in (ROOT / "builder/compile").glob("*.py") if p.name != "selfcheck.py")  # selfcheck holds sample data only
    for leak in ("2026-10-26", "4821", "collections team", "12th business", "Freya Bank"):
        assert leak not in src, leak


def test_human_request_is_not_a_refusal(wf_a):
    """Mehmet's OUR-09/26: 'I want a real person' during identity must not count as a refusal (v14 regression)."""
    sec = wf_a["nodes"]["security"]
    desc = next(e for e in sec["extraction_schema"] if e["name"] == "declined_1")["description"]
    assert "real person" in desc and "not a refusal" in desc
    assert "transfer_to_agent" in [t["function"]["name"] for t in sec["tools"]]
    assert "NOT a refusal" in sec["task_message"] if "task_message" in sec else True


def _variant(tmp_path, **changes):
    """Brief A's CallSpec with a few structured fields changed; returns the compiled workflow."""
    import copy
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    for path, value in changes.items():
        d = spec
        keys = path.split(".")
        for k in keys[:-1]:
            d = d[int(k)] if k.isdigit() else d[k]
        d[keys[-1]] = value
    f = tmp_path / "spec.json"
    f.write_text(json.dumps(spec))
    wf, problems = build(str(f), str(ROOT / "kit/tools/openapi.json"))
    assert not problems, problems
    return wf


def test_variants_from_brief_d(tmp_path):
    """The eight rule variants brief D exposed: each has a structured field and the compiler uses it."""
    wf = _variant(tmp_path, **{"products.0.floor_percent": 50, "products.0.floor_round_up_to_whole": True,
                               "third_party.callback.max_business_days_ahead": 2, "amounts.today_question": "Are you able to clear this today?",
                               "dates.weekend_named_offer": "previous_business_day", "dates.vague_period_fallback": "attempt1",
                               "confirm.max_tries_on_failure": 3, "identity.decline.explain_first": False,
                               "multi_product.no_promise_reason_priority": ["dispute", "hardship", "service_error", "refused"]})
    v = facts_preview(wf, "2026-10-14T11:00", [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.5, "days_late": 16, "minimum_payment": 153.0}])
    f = json.loads(v["facts_json"])[0]
    assert f["floor"] == 256.0                                             # ceil(0.5 * 510.5), whole pound, not minimum_payment
    assert "15 October" in v["callback_text"] and "16 October" in v["callback_text"]   # next business day or the one after
    assert v["debt_statement"].endswith("Are you able to clear this today?")
    assert "last business day before it" in v["calendar_text"]
    neg = wf["nodes"]["negotiate"]["task_message"]
    assert "attempt-1 date from ACCOUNT (the full amount" in neg and "up to 3 tries" in neg
    sec = wf["nodes"]["security"]["transitions"]
    assert any(t["target_node"] == "close_declined" and "declined_1" in json.dumps(t) for t in sec)   # no explanation step
    svc = next(t for t in wf["nodes"]["negotiate"]["transitions"] if t["target_node"] == "close_service_error")
    assert '"operand": 2' in json.dumps(svc)                               # failure count > 2 = three tries
    assert "'dispute', 'hardship'" in json.dumps(wf["nodes"]["decide_outcome"])


def test_band_needs_exactly_one_deadline_number(tmp_path):
    import pytest
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    spec["dates"]["bands"][0]["deadline_business_days_after_today"] = None
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(spec))
    with pytest.raises(Exception) as e:
        build(str(f), str(ROOT / "kit/tools/openapi.json"))
    assert "exactly one of" in str(e.value)


def test_consistency_checks_flag_text_without_field():
    """Layer 2: a text rule that names a variant without its structured field is reported to the extractor."""
    from builder.extract.callspec import CallSpec
    from builder.extract.tools import consistency_checks
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    assert consistency_checks(CallSpec.model_validate(spec)) == []
    spec["amounts"]["floor_rule"] = "50 percent of the overdue amount, rounded up"
    spec["dates"]["weekend_or_holiday_rule"] = "offer the last business day before it"
    spec["dates"]["vague_period_rule"] = "ask once for the exact day; if none, propose the attempt-1 date, not the latest date"
    spec["third_party"]["callback"]["day_rule"] = "never today; the next business day or the one after that"
    spec["confirm"]["extra_rules"] = ["If create_promise fails, retry twice before giving up."]
    errs = consistency_checks(CallSpec.model_validate(spec))
    assert len(errs) == 5, errs
    for key in ("floor_percent", "weekend_named_offer", "vague_period_fallback", "max_business_days_ahead", "max_tries_on_failure"):
        assert any(key in e for e in errs), key
