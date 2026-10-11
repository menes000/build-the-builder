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
    wf = _variant(tmp_path, **{"products.0.floor_field": "past_due", "products.0.floor_percent": 50, "products.0.floor_round_up_to_whole": True,
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


def test_variants_from_brief_e(tmp_path):
    """Brief E: percentage of the floor field, placeholders in the first question, calendar-day callbacks with Saturday,
    no retry, closing by the first product, a dictated identity intro, both days offered for a weekend date."""
    wf = _variant(tmp_path, **{"products.1.floor_percent": 50, "products.1.floor_round_up_to_whole": True,
                               "amounts.today_question": "Can you pay {amount} by tomorrow, {tomorrow}?",
                               "third_party.callback.max_business_days_ahead": 3, "third_party.callback.calendar_days": True, "third_party.callback.saturday_allowed": True,
                               "confirm.max_tries_on_failure": 1, "multi_product.closing_by_first_product": True,
                               "identity.intro_text": "Before we go on, I must let you know that this call is recorded.",
                               "dates.weekend_named_offer": "both"})
    v = facts_preview(wf, "2026-10-14T11:00", [{"product_id": "p1", "type": "personal_loan", "past_due": 540.0, "days_late": 5, "instalment_amount": 333.0}])
    f = json.loads(v["facts_json"])[0]
    assert f["floor"] == 167.0                                              # ceil(333 / 2): percentage of the floor field, not of past_due
    assert v["debt_statement"].endswith("Can you pay 540 by tomorrow, Thursday 15 October 2026?")
    assert "17 October" in v["callback_text"] and "18 October" not in v["callback_text"]   # Saturday yes, Sunday no
    assert "let the customer choose" in v["calendar_text"]
    assert "must let you know that this call is recorded" in wf["nodes"]["security"]["on_enter"]["text"]
    svc = next(t for t in wf["nodes"]["negotiate"]["transitions"] if t["target_node"] == "close_service_error")
    assert '"operand": 0' in json.dumps(svc)                                # no retry: the first failure closes
    assert "do not call it again" in wf["nodes"]["negotiate"]["task_message"]
    assert "CLOSE_BY_FIRST = True" in json.dumps(wf["nodes"]["decide_outcome"])


def _decide(wf, notes, facts):
    from conftest import run_hook
    node = wf["nodes"]["decide_outcome"]
    code = node.get("code") or node["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
    v = {"notes_json": json.dumps(notes), "facts_json": json.dumps(facts), "promises_json": "[]"}
    run_hook(code, v)
    return v["outcome"], v["reason"]


def test_closing_by_first_product_behaviour(tmp_path):
    """Review finding: with closing_by_first_product, a paid first product must close as paid (it was overwritten)."""
    spec = json.loads((ROOT / "fixtures/callspec_brief_ab.json").read_text())
    spec["multi_product"]["closing_by_first_product"] = True
    f = tmp_path / "s.json"; f.write_text(json.dumps(spec))
    wf, _ = build(str(f), str(ROOT / "kit/tools/openapi.json"))
    facts = [{"pid": "p1"}, {"pid": "p2"}]
    assert _decide(wf, [{"pid": "p1", "reason": "paid"}, {"pid": "p2", "reason": "refused"}], facts)[0] == "paid"
    assert _decide(wf, [{"pid": "p2", "reason": "paid"}, {"pid": "p1", "reason": "dispute"}], facts) == ("no_promise", "dispute")


def test_brief_b_closing_unchanged(wf_ab):
    """Brief B: first non-paid product decides; all paid -> paid."""
    facts = [{"pid": "p1"}, {"pid": "p2"}]
    assert _decide(wf_ab, [{"pid": "p1", "reason": "paid"}, {"pid": "p2", "reason": "refused"}], facts) == ("no_promise", "refused")
    assert _decide(wf_ab, [{"pid": "p1", "reason": "paid"}, {"pid": "p2", "reason": "paid"}], facts)[0] == "paid"


def test_consistency_checks_do_not_lock():
    """Review finding: every weekend value was rejected by one check or another; the A+B rule was a false alarm."""
    from builder.extract.callspec import CallSpec
    from builder.extract.tools import consistency_checks
    ab = CallSpec.model_validate_json((ROOT / "fixtures/callspec_brief_ab.json").read_text())
    assert consistency_checks(ab) == []
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    spec["dates"]["weekend_or_holiday_rule"] = "Offer both the last business day before it and the next business day after it; the customer chooses."
    ok = []
    for v in ("next_business_day", "previous_business_day", "both"):
        spec["dates"]["weekend_named_offer"] = v
        if not [e for e in consistency_checks(CallSpec.model_validate(spec)) if "weekend" in e]:
            ok.append(v)
    assert ok == ["both"]


def test_extraction_never_crashes_on_lint(tmp_path, monkeypatch):
    """Review finding: a lint problem on the last attempt crashed the build. Now the spec is kept with a warning."""
    from builder.extract import extractor
    from builder.trace import Trace
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    spec["amounts"]["floor_rule"] = "50 percent of the overdue amount"          # a consistency problem on every attempt
    out = tmp_path / "cs.json"

    async def fake_ask(prompt, out_path, cwd, model, trace, purpose):
        out_path.write_text(json.dumps(spec))
        return ""
    monkeypatch.setattr(extractor, "_ask_claude", fake_ask)
    brief = tmp_path / "b.md"; brief.write_text("brief")
    tr = Trace(str(tmp_path), "t")
    got = extractor.extract_callspec([str(brief)], str(out), tr, openapi_path=str(ROOT / "kit/tools/openapi.json"))
    assert got.amounts.floor_rule.startswith("50 percent")
    assert "WARNING kept as is" in tr.txt.read_text()


def test_closing_lines_do_not_repeat_a_sentence(tmp_path):
    """Regression run 15:40: the extracted after-failed text already said 'I am sorry, I could not verify your identity'."""
    wf = _variant(tmp_path, **{"identity.after_failed_text": "I am sorry, I could not verify your identity, so please use the Freya Bank mobile app or visit a branch."})
    txt = json.dumps(wf["nodes"]["close_failed"])
    assert txt.count("could not verify your identity") == 1
    from builder.compile.compiler import _dedupe_sentences
    assert _dedupe_sentences("Thank you. Goodbye. Thank you. Goodbye.") == "Thank you. Goodbye."
