"""Run the generated Python snippets locally (syntax + a smoke execution) before sending the workflow to Freya."""
from __future__ import annotations

import json


def _run(code: str, env: dict) -> dict:
    g = {"__builtins__": __builtins__}
    g.update(env)
    exec(compile(code, "<snippet>", "exec"), g)
    return g


def check_snippets(workflow: dict, sample_now: str = "2026-10-14T11:00", sample_products=None) -> list[str]:
    errs: list[str] = []
    sample_products = sample_products or [
        {"product_id": "p1", "type": "credit_card", "card_last4": "4821", "past_due": 420.0, "days_late": 6, "minimum_payment": 126.0},
        {"product_id": "p2", "type": "personal_loan", "past_due": 310.5, "days_late": 11, "instalment_amount": 103.5},
    ]
    # 1. every code node compiles and runs on a sample variable table
    for k, n in workflow["nodes"].items():
        for a in n.get("pre_actions") or []:
            code = a.get("function", {}).get("parameters", {}).get("properties", {}).get("code", {}).get("default")
            if not code:
                continue
            try:
                compile(code, k, "exec")
            except SyntaxError as e:
                errs.append(f"{k}: syntax error {e}")
                continue
            v = {"now": sample_now, "customer_id": "c_test", "title": "Mr", "last_name": "Reyes",
                 "products": json.dumps(sample_products), "facts_json": "[]", "promises_json": "[]", "notes_json": "[]"}
            try:
                _run(code, {"vars": v})
            except Exception as e:
                errs.append(f"{k}: runtime error {e}")
            if k == "account_facts":
                if v.get("account_state") != "ok":
                    errs.append(f"account_facts: account_state={v.get('account_state')} err={v.get('facts_error')}")
                for key in ("facts_json", "calendar_text", "offers_text", "debt_statement", "deadline_text"):
                    if not v.get(key):
                        errs.append(f"account_facts: {key} empty")
    # 2. hooks compile and survive odd inputs
    tools = list(workflow.get("tools") or [])
    for n in workflow["nodes"].values():
        tools += n.get("tools") or []
    for t in tools:
        name = t.get("function", {}).get("name")
        for hk in ("pre_process_code", "post_process_code"):
            code = t.get(hk)
            if not code:
                continue
            try:
                compile(code, f"{name}.{hk}", "exec")
            except SyntaxError as e:
                errs.append(f"{name}.{hk}: syntax error {e}")
                continue
            for env in (
                {"vars": {}, "config": {"body": {}}, "result": {}},
                {"vars": {"facts_json": "bad", "promises_json": None}, "config": {"body": {"date": "x", "amount": "abc"}}, "result": {"data": {"ok": "false", "error": "boom"}}},
                {"vars": {}, "config": {}, "result": None},
            ):
                try:
                    _run(code, env)
                except Exception as e:
                    errs.append(f"{name}.{hk}: raised on odd input: {e}")
    return errs


def facts_preview(workflow: dict, now: str, products: list) -> dict:
    """What the account_facts code computes for a given now/products. For tests and debugging."""
    code = workflow["nodes"]["account_facts"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
    v = {"now": now, "customer_id": "c", "title": "Ms", "last_name": "X", "products": json.dumps(products)}
    _run(code, {"vars": v})
    return v
