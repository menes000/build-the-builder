"""Parse the bank's tool API (OpenAPI JSON) into CallSpec Tool objects. No LLM involved."""
from __future__ import annotations

import json
from pathlib import Path

from .callspec import Tool, ToolField


def parse_openapi(path: str | Path) -> list[Tool]:
    d = json.loads(Path(path).read_text())
    base = (d.get("servers") or [{}])[0].get("url", "").rstrip("/")
    tools: list[Tool] = []
    for p, ops in d.get("paths", {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        schema = (op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}))
        req = set(schema.get("required", []))
        fields = []
        for name, prop in (schema.get("properties") or {}).items():
            fields.append(ToolField(
                name=name,
                type=prop.get("type", "string"),
                enum=list(prop.get("enum") or []),
                description=prop.get("description", "") or "",
                required=name in req,
            ))
        tools.append(Tool(name=p.strip("/"), url=f"{base}{p}", summary=op.get("summary", "") or "", fields=fields))
    return tools


def response_fields(path: str | Path) -> dict[str, set[str]]:
    """Tool name -> set of top-level response property names (for lint)."""
    d = json.loads(Path(path).read_text())
    out: dict[str, set[str]] = {}
    for p, ops in d.get("paths", {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        ok = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
        props = ok.get("properties") or {}
        names = set(props.keys())
        prods = props.get("products", {}).get("items", {}).get("properties") or {}
        names |= {f"products.{k}" for k in prods}
        out[p.strip("/")] = names
    return out


# ----------------------------------------------------------------------------- field mapping
# The seven tool names stay the same in the final, but "the fields and the allowed values can change".
# We map our canonical field names to whatever the tool API actually calls them, by exact name, then synonyms,
# then a loose token match. Unresolved names fall back to the canonical one and are reported as warnings.

_SYN_REQ = {
    "customer_id": ["customer_id", "customerid", "customer", "cust_id", "account_holder_id"],
    "field": ["field", "question", "key", "check", "item"],
    "answer": ["answer", "value", "response"],
    "product_id": ["product_id", "productid", "product", "account_id", "loan_id"],
    "amount": ["amount", "sum", "value", "promise_amount", "payment_amount"],
    "date": ["date", "promise_date", "pay_date", "payment_date", "callback_date", "day"],
    "time": ["time", "callback_time", "hour", "slot"],
    "reason": ["reason", "code", "note_reason", "sub_outcome", "subreason", "detail"],
    "text": ["text", "note", "comment"],
    "queue": ["queue", "team", "department", "destination"],
    "outcome": ["outcome", "result", "status", "disposition"],
}
_SYN_RESP = {
    "ok": ["ok", "success", "succeeded"],
    "error": ["error", "message", "reason", "detail"],
    "verified": ["verified", "correct", "match", "passed"],
    "all_verified": ["all_verified", "fully_verified", "identity_verified", "complete", "all_passed", "done"],
    "wrong_answers_left": ["wrong_answers_left", "attempts_left", "remaining_attempts", "tries_left", "attempts_remaining", "wrong_left"],
    "hint": ["hint", "note", "advice"],
    "products": ["products", "accounts", "items", "loans", "debts"],
    "promise_id": ["promise_id", "id", "reference"],
}
_SYN_PRODUCT = {
    "product_id": ["product_id", "id", "productid", "account_id"],
    "type": ["type", "product_type", "kind", "category"],
    "card_last4": ["card_last4", "last4", "card_last_4", "last_four", "card_ending"],
    "past_due": ["past_due", "overdue", "amount_due", "past_due_amount", "arrears", "overdue_amount", "balance_due"],
    "days_late": ["days_late", "days_overdue", "late_days", "dpd", "days_past_due", "delinquency_days"],
    "minimum_payment": ["minimum_payment", "min_payment", "minimum", "min_due", "minimum_due"],
    "instalment_amount": ["instalment_amount", "installment_amount", "instalment", "installment", "monthly_amount", "monthly_payment"],
}


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _resolve(canon: str, synonyms: list[str], available: list[str], warnings: list[str], where: str) -> str:
    if not available:
        return canon
    if canon in available:
        return canon
    avail_norm = {_norm(a): a for a in available}
    for syn in synonyms:
        if _norm(syn) in avail_norm:
            return avail_norm[_norm(syn)]
    tokens = [t for t in canon.split("_") if len(t) > 2]
    for a in available:
        if any(t in a.lower() for t in tokens):
            warnings.append(f"{where}: '{canon}' loosely matched to '{a}'")
            return a
    warnings.append(f"{where}: '{canon}' not found (available: {', '.join(available)}); using '{canon}'")
    return canon


_TOOL_REQ = {
    "verify_identity": ["customer_id", "field", "answer"],
    "get_account": ["customer_id"],
    "create_promise": ["customer_id", "product_id", "amount", "date"],
    "add_note": ["customer_id", "product_id", "reason", "text"],
    "schedule_callback": ["customer_id", "date", "time"],
    "transfer_to_agent": ["customer_id", "queue"],
    "close_call": ["customer_id", "outcome", "reason"],
}
_TOOL_RESP = {
    "verify_identity": ["ok", "error", "verified", "all_verified", "wrong_answers_left", "hint"],
    "get_account": ["ok", "error", "products"],
    "create_promise": ["ok", "error", "promise_id"],
    "add_note": ["ok", "error"],
    "schedule_callback": ["ok", "error"],
    "transfer_to_agent": ["ok", "error"],
    "close_call": ["ok", "error"],
}


def field_map(path: str | Path) -> dict:
    """{'req': {tool: {canon: actual}}, 'resp': {tool: {canon: actual}}, 'product': {canon: actual}, 'warnings': [...]}"""
    d = json.loads(Path(path).read_text())
    warnings: list[str] = []
    req: dict[str, dict[str, str]] = {}
    resp: dict[str, dict[str, str]] = {}
    product: dict[str, str] = {}
    for p, ops in d.get("paths", {}).items():
        tool = p.strip("/")
        op = ops.get("post") or next(iter(ops.values()))
        rq = (op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("properties") or {})
        rs = (op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("properties") or {})
        req[tool] = {c: _resolve(c, _SYN_REQ[c], list(rq.keys()), warnings, f"{tool}.request") for c in _TOOL_REQ.get(tool, []) if rq}
        resp[tool] = {c: _resolve(c, _SYN_RESP[c], list(rs.keys()), warnings, f"{tool}.response") for c in _TOOL_RESP.get(tool, []) if rs}
        # the product list (get_account): find the array property and its item schema
        if tool == "get_account" and rs:
            arr = resp[tool].get("products", "products")
            items = (rs.get(arr) or {}).get("items") or {}
            pp = items.get("properties") or {}
            product = {c: _resolve(c, syn, list(pp.keys()), warnings, "product") for c, syn in _SYN_PRODUCT.items()}
    if not product:
        product = {c: c for c in _SYN_PRODUCT}
    return {"req": req, "resp": resp, "product": product, "warnings": warnings}


def req_name(fm: dict, tool: str, canon: str) -> str:
    return (fm.get("req", {}).get(tool) or {}).get(canon, canon)


def resp_name(fm: dict, tool: str, canon: str) -> str:
    return (fm.get("resp", {}).get(tool) or {}).get(canon, canon)
