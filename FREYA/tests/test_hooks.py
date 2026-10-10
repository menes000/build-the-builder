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
