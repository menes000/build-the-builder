"""The Python that runs inside Freya: refusal counter, promise checks, identity question tracking."""
import json

from conftest import FACTS_1, FACTS_2, run_hook, tool


def _refusal(wf, node, facts, pid, times, too_much="false"):
    t = tool(wf, node, "note_refusal")
    v = {"facts_json": json.dumps(facts)}
    out = []
    for _ in range(times):
        run_hook(t["pre_process_code"], v, body={"product_id": pid, "amount_too_much": too_much, "customer_id": "c"})
        res = {"data": {"ok": True, "products": []}, "header": {}}
        run_hook(t["post_process_code"], v, result=res)
        out.append((res["data"]["refusal_state"], res["data"]["what_to_do_next"]))
    return out


def test_counter_single_product_two_attempts_then_stop(wf_a):
    r = _refusal(wf_a, "negotiate", FACTS_1, "p1", 3)
    assert r[0][0] == "continue" and "Attempt 1 of 2" in r[0][1] and "510" in r[0][1] and "16 October" in r[0][1]
    assert r[1][0] == "continue" and "Attempt 2 of 2" in r[1][1] and "153" in r[1][1] and "23 October" in r[1][1]
    assert r[2][0] == "exhausted" and "transition_to_close_refused" in r[2][1]


def test_counter_single_product_too_much_uses_floor(wf_a):
    r = _refusal(wf_a, "negotiate", FACTS_1, "p1", 1, too_much="true")
    assert "propose 153" in r[0][1] and "rest stays overdue" in r[0][1]


def test_counter_multi_product_opening_counts_as_attempt_one(wf_ab):
    r = _refusal(wf_ab, "negotiate", FACTS_2, "p1", 2)
    assert "Attempt 2 of 2" in r[0][1]
    assert r[1][0] == "exhausted" and "add_note" in r[1][1] and "p1" in r[1][1]
    r = _refusal(wf_ab, "negotiate", FACTS_2, "p3", 1)
    assert r[0][0] == "exhausted" and "car loan" in r[0][1]


def test_promise_precheck_rejects_bad_date_and_amount(wf_a):
    t = tool(wf_a, "negotiate", "create_promise")
    v = {"facts_json": json.dumps(FACTS_1), "promises_json": "[]"}
    e = run_hook(t["pre_process_code"], v, body={"product_id": "p1", "amount_kind": "custom", "amount": "100", "date": "2026-10-20"})
    assert e["config"]["body"]["date"] == "REJECTED" and v["promise_precheck"] == "rejected"  # below floor
    e = run_hook(t["pre_process_code"], v, body={"product_id": "p1", "amount_kind": "full", "date": "2026-10-26"})
    assert e["config"]["body"]["date"] == "REJECTED"  # not an allowed date
    e = run_hook(t["pre_process_code"], v, body={"product_id": "p1", "amount_kind": "full", "date": "2026-10-16"})
    assert e["config"]["body"]["date"] == "2026-10-16" and e["config"]["body"]["amount"] == 510.0 and v["promise_precheck"] == "ok"


def test_promise_duplicate_gives_immutable_sentence(wf_a):
    t = tool(wf_a, "negotiate", "create_promise")
    v = {"facts_json": json.dumps(FACTS_1), "promises_json": json.dumps([{"pid": "p1"}])}
    run_hook(t["pre_process_code"], v, body={"product_id": "p1", "amount_kind": "full", "date": "2026-10-16"})
    res = {"data": {"ok": False, "error": "x"}, "header": {}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["promise_state"] == "duplicate"
    assert "mobile app" in res["data"]["what_to_do_next"]


def test_promise_success_sets_outcome_immediately(wf_a):
    t = tool(wf_a, "negotiate", "create_promise")
    v = {"facts_json": json.dumps(FACTS_1), "promises_json": "[]", "outcome": "no_promise", "reason": "refused"}
    run_hook(t["pre_process_code"], v, body={"product_id": "p1", "amount_kind": "full", "date": "2026-10-16"})
    res = {"data": {"ok": True, "promise_id": "pr1"}, "header": {}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["promise_state"] == "recorded"
    assert v["outcome"] == "promise" and v["reason"] == ""
    assert json.loads(v["promises_json"]) == [{"pid": "p1"}]


def test_identity_next_question_tracking(wf_a):
    t = tool(wf_a, "security", "verify_identity")
    v = {"next_question": "What is your date of birth?"}
    run_hook(t["pre_process_code"], v, body={"field": "date_of_birth", "answer": "1988-03-14"})
    res = {"data": {"ok": True, "verified": True, "all_verified": False, "wrong_answers_left": 3}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["id_state"] == "next"
    assert "phone" in v["next_question"]
    run_hook(t["pre_process_code"], v, body={"field": "phone_last4", "answer": "4471"})
    res = {"data": {"ok": True, "verified": True, "all_verified": True, "wrong_answers_left": 3}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["id_state"] == "verified"


def test_identity_hint_and_failure(wf_a):
    t = tool(wf_a, "security", "verify_identity")
    v = {}
    res = {"data": {"ok": True, "verified": False, "hint": "day_month_swapped", "wrong_answers_left": 3}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["id_state"] == "retry" and "NOT count" in res["data"]["what_to_do_next"]
    res = {"data": {"ok": True, "verified": False, "wrong_answers_left": 0}}
    run_hook(t["post_process_code"], v, result=res)
    assert res["data"]["id_state"] == "failed"


def _close_call(wf):
    return next(t for t in wf["tools"] if t["function"]["name"] == "close_call")


def test_hangup_after_hardship_closes_as_hardship(wf_a):
    """Customer hangs up before any closing node ran: the last known situation decides, not the baked default."""
    t = _close_call(wf_a)
    v = {"outcome": "no_promise", "reason": "refused", "situation": "hardship", "promises_json": "[]"}
    e = run_hook(t["pre_process_code"], v, body={"outcome": "no_promise", "reason": "refused"})
    assert e["config"]["body"] == {"outcome": "no_promise", "reason": "hardship"} and v["reason"] == "hardship"
    v = {"outcome": "no_promise", "reason": "refused", "situation": "paid", "promises_json": "[]"}
    e = run_hook(t["pre_process_code"], v, body={"outcome": "no_promise", "reason": "refused"})
    assert e["config"]["body"] == {"outcome": "paid"}                      # Brief A: paid has no reason


def test_hangup_keeps_decided_or_promised_outcome(wf_a):
    t = _close_call(wf_a)
    v = {"outcome": "no_promise", "reason": "refused", "situation": "hardship", "outcome_decided": "true"}
    e = run_hook(t["pre_process_code"], v, body={"outcome": "no_promise", "reason": "refused"})
    assert e["config"]["body"]["reason"] == "refused"                     # a closing node already decided
    v = {"outcome": "promise", "reason": "", "situation": "hardship", "promises_json": '[{"pid": "p1"}]'}
    e = run_hook(t["pre_process_code"], v, body={"outcome": "promise", "reason": ""})
    assert e["config"]["body"] == {"outcome": "promise"}                   # promise wins; empty reason dropped
    assert "outcome_decided" in json.dumps(wf_a["nodes"]["decide_outcome"])


def _variant_wf(tmp_path, **changes):
    import pathlib
    from conftest import ROOT
    from builder.build_from_spec import build
    spec = json.loads((ROOT / "fixtures/callspec_brief_a.json").read_text())
    for path, value in changes.items():
        d = spec
        keys = path.split(".")
        for k in keys[:-1]:
            d = d[int(k)] if k.isdigit() else d[k]
        d[keys[-1]] = value
    f = pathlib.Path(tmp_path) / "spec.json"
    f.write_text(json.dumps(spec))
    wf, problems = build(str(f), str(ROOT / "kit/tools/openapi.json"))
    assert not problems, problems
    return wf


def test_layer3_floor_left_to_the_model(tmp_path):
    """Floor rule fits no field: no computed floor in the prompt, no 'floor' amount kind, the check keeps only 0 < amount <= full."""
    from builder.compile.selfcheck import facts_preview
    wf = _variant_wf(tmp_path, **{"amounts.floor_mode": "text", "amounts.floor_rule": "The average of the last three instalments."})
    v = facts_preview(wf, "2026-10-14T11:00", [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.0, "days_late": 16, "minimum_payment": 153.0}])
    assert "153" not in v["offers_text"] and "average of the last three instalments" in v["offers_text"]
    t = tool(wf, "negotiate", "create_promise")
    assert t["function"]["parameters"]["properties"]["body"]["properties"]["amount_kind"]["enum"] == ["full", "custom"]
    facts = json.loads(v["facts_json"])
    vv = {"facts_json": json.dumps(facts), "promises_json": "[]"}
    e = run_hook(t["pre_process_code"], vv, body={"product_id": "p1", "amount_kind": "custom", "amount": "100", "date": facts[0]["valid"][0]})
    assert e["config"]["body"]["date"] != "REJECTED"                         # 100 is below the old floor 153: now accepted
    e = run_hook(t["pre_process_code"], vv, body={"product_id": "p1", "amount_kind": "custom", "amount": "600", "date": facts[0]["valid"][0]})
    assert e["config"]["body"]["date"] == "REJECTED"                         # still never above the full amount
    neg = wf["nodes"]["negotiate"]["task_message"]
    assert "FLOOR RULE (work the floor out yourself" in neg


def test_layer3_attempt1_other_and_callback_text(tmp_path):
    from builder.compile.selfcheck import facts_preview
    wf = _variant_wf(tmp_path, **{"persuasion.attempt1_date_kind": "other", "persuasion.attempt1_date_rule": "The customer's next payday.",
                                  "third_party.callback.day_mode": "text", "third_party.callback.day_rule": "Any weekday of the next fortnight."})
    v = facts_preview(wf, "2026-10-14T11:00", [{"product_id": "p1", "type": "credit_card", "card_last4": "9015", "past_due": 510.0, "days_late": 16, "minimum_payment": 153.0}])
    assert "next payday" in v["offers_text"] and "16 October" not in v["offers_text"].split("Refusal plan")[1].split("attempt 2")[0]
    assert "Any weekday of the next fortnight" in v["callback_text"] and v["cb_dates"] == ""
    t = tool(wf, "third_party", "schedule_callback")
    vv = dict(v)
    e = run_hook(t["pre_process_code"], vv, body={"date": "2026-10-22", "time": "11:00"})
    assert e["config"]["body"]["date"] == "2026-10-22"                      # a day the code no longer judges
    e = run_hook(t["pre_process_code"], vv, body={"date": "2026-10-22", "time": "23:00"})
    assert e["config"]["body"]["date"] == "REJECTED"                         # the time window is still enforced


def test_layer3_automatic_switch():
    from conftest import ROOT
    from builder.extract.callspec import CallSpec
    from builder.extract.tools import apply_text_modes
    spec = CallSpec.model_validate_json((ROOT / "fixtures/callspec_brief_a.json").read_text())
    got = apply_text_modes(spec, ["amounts.floor_rule speaks of a percentage but no product has floor_percent",
                                  "third_party.callback.day_rule allows the business day after the next one but max_business_days_ahead is 1"])
    assert got == ["amounts.floor_mode", "third_party.callback.day_mode"]
    assert spec.amounts.floor_mode == "text" and spec.third_party.callback.day_mode == "text"
