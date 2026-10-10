"""Parse the bank's tool API (OpenAPI JSON) into CallSpec Tool objects. No LLM involved."""
from __future__ import annotations

import json
from pathlib import Path

from .callspec import Tool, ToolField


def load_openapi(path: str | Path) -> dict:
    """JSON or YAML OpenAPI file."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(text)
    except ValueError:
        import yaml  # type: ignore
        return yaml.safe_load(text)


def tool_name(path: str) -> str:
    """'/v1/verify_identity' -> 'verify_identity' (the seven tool names stay the same; prefixes may not)."""
    return path.strip("/").split("/")[-1]


def parse_openapi(path: str | Path) -> list[Tool]:
    d = load_openapi(path)
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
        tools.append(Tool(name=tool_name(p), url=f"{base}{p}", summary=op.get("summary", "") or "", fields=fields))
    return tools


def response_fields(path: str | Path) -> dict[str, set[str]]:
    """Tool name -> set of top-level response property names (for lint)."""
    d = load_openapi(path)
    out: dict[str, set[str]] = {}
    for p, ops in d.get("paths", {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        ok = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
        props = ok.get("properties") or {}
        names = set(props.keys())
        prods = props.get("products", {}).get("items", {}).get("properties") or {}
        names |= {f"products.{k}" for k in prods}
        out[tool_name(p)] = names
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
    loose = [a for a in available if any(t in a.lower() for t in tokens)]
    if len(loose) > 1:
        raise ValueError(f"{where}: '{canon}' is ambiguous in the tool API (candidates: {', '.join(loose)}); add the right name to the synonym list in builder/extract/tools.py")
    if loose:
        warnings.append(f"{where}: '{canon}' loosely matched to '{loose[0]}'")
        return loose[0]
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
    d = load_openapi(path)
    warnings: list[str] = []
    req: dict[str, dict[str, str]] = {}
    resp: dict[str, dict[str, str]] = {}
    product: dict[str, str] = {}
    for p, ops in d.get("paths", {}).items():
        tool = tool_name(p)
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



# ----------------------------------------------------------------------------- CallSpec vs tool API
def lint_spec(spec, tools: list[Tool], fm: dict) -> list[str]:
    """Values the CallSpec sends to the bank must exist in the tool API's enums. Returns problems (empty = fine)."""
    by = {t.name: t for t in tools}

    def enum_of(tool: str, canon: str) -> list[str]:
        t = by.get(tool)
        if not t:
            return []
        actual = req_name(fm, tool, canon)
        for f in t.fields:
            if f.name == actual:
                return list(f.enum)
        return []

    errs = []
    outcomes = enum_of("close_call", "outcome")
    queues = enum_of("transfer_to_agent", "queue")
    fields = enum_of("verify_identity", "field")
    reasons = enum_of("add_note", "reason")
    closes = []
    for row in spec.closing.outcomes:
        closes.append(("closing.outcomes", row.outcome))
    sp = spec.special
    for name, oc in (("opening.unclear_close", spec.opening.unclear_close), ("identity.failed_close", spec.identity.failed_close),
                     ("identity.decline.close", spec.identity.decline.close), ("third_party.callback_close", spec.third_party.callback_close),
                     ("third_party.no_callback_close", spec.third_party.no_callback_close), ("third_party.wrong_number_close", spec.third_party.wrong_number_close),
                     ("third_party.deceased_close", spec.third_party.deceased_close), ("persuasion.refused_close", spec.persuasion.refused_close),
                     ("special.hardship.accept_close", sp.hardship.accept_close), ("special.hardship.decline_close", sp.hardship.decline_close),
                     ("special.paid.close", sp.paid.close), ("special.dispute.close", sp.dispute.close), ("special.restructuring.close", sp.restructuring.close),
                     ("special.human.close", sp.human.close), ("confirm.failed_twice_close", spec.confirm.failed_twice_close),
                     ("special.refuses_twice_verified_close", sp.refuses_twice_verified_close), ("special.refuses_twice_unverified_close", sp.refuses_twice_unverified_close)):
        closes.append((name, oc.outcome))
    if outcomes:
        for where, val in closes:
            if val not in outcomes:
                errs.append(f"{where}: outcome '{val}' is not in close_call.outcome enum {outcomes}")
        if spec.closing.promise_outcome not in outcomes:
            errs.append(f"closing.promise_outcome '{spec.closing.promise_outcome}' not in {outcomes}")
    if queues:
        for where, q in (("special.hardship.offer_queue", sp.hardship.offer_queue), ("special.restructuring.queue", sp.restructuring.queue), ("special.human.queue", sp.human.queue)):
            if q not in queues:
                errs.append(f"{where}: queue '{q}' is not in transfer_to_agent.queue enum {queues}")
        if spec.identity.human_request and spec.identity.human_request.queue not in queues:
            errs.append(f"identity.human_request.queue '{spec.identity.human_request.queue}' not in {queues}")
    if fields:
        for q in spec.identity.questions:
            if q.field not in fields:
                errs.append(f"identity.questions: field '{q.field}' is not in verify_identity.field enum {fields}")
    if reasons and spec.multi_product.enabled:
        for r in spec.multi_product.note_reasons:
            if r not in reasons:
                errs.append(f"multi_product.note_reasons: '{r}' is not in add_note.reason enum {reasons}")
    return errs
