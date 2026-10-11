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
def consistency_checks(spec) -> list[str]:
    """A rule written in a text field must also be in its structured field, or the code computes one thing while the
    prompt says another. Cheap word checks on the text fields; each hit is an error the extractor must resolve."""
    import re
    errs = []
    low = lambda t: (t or "").lower()
    fl = low(spec.amounts.floor_rule) + " " + " ".join(low(x) for x in spec.amounts.extra_rules)
    if re.search(r"\b\d+(\.\d+)?\s*(%|percent|per cent)|\bhalf\b|\bquarter\b|\bthird\b", fl) and not any(p.floor_percent for p in spec.products):
        errs.append("amounts.floor_rule speaks of a percentage or a fraction but no product has floor_percent: set products[].floor_percent (applied to floor_field)")
    cbt = low(spec.third_party.callback.day_rule) + " " + " ".join(low(x) for x in spec.third_party.extra_rules)
    if ("calendar day" in cbt or "saturday is allowed" in cbt or "saturday allowed" in cbt) and not (spec.third_party.callback.calendar_days or spec.third_party.callback.saturday_allowed):
        errs.append("the callback window text counts calendar days or allows Saturday but callback.calendar_days / saturday_allowed are false")
    it = " ".join(low(x) for x in spec.identity.extra_rules) + " " + " ".join(low(x) for x in spec.opening.extra_rules)
    if re.search(r"(immediately|right) after the name is confirmed.*say", it) and not spec.identity.intro_text:
        errs.append("a text rule dictates a sentence right after the name is confirmed but identity.intro_text is empty")
    ot = low(spec.opening.first_sentence) + " " + " ".join(low(x) for x in spec.opening.extra_rules)
    if "good afternoon" in ot and "good morning" in ot and "{greeting}" not in spec.opening.first_sentence:
        errs.append("the greeting depends on the time of day but opening.first_sentence has no {greeting} placeholder (fill opening.greetings)")
    idt = " ".join(low(x) for x in spec.identity.extra_rules)
    if re.search(r"per question|same question", idt) and not spec.identity.max_wrong_per_question:
        errs.append("identity text counts wrong answers per question but identity.max_wrong_per_question is empty")
    mc = low(spec.multi_product.closing_rule)
    if "first product" in mc and not re.search(r"not paid|non-paid|other than paid|isn't paid|is not noted paid", mc) and not spec.multi_product.closing_by_first_product:
        errs.append("multi_product.closing_rule follows the first product but closing_by_first_product is false")
    w2 = low(spec.dates.weekend_or_holiday_rule)
    if re.search(r"(both|before and after|before it and|choose)", w2) and spec.dates.weekend_named_offer != "both" and re.search(r"(after|next)", w2) and re.search(r"(before|previous)", w2):
        errs.append("dates.weekend_or_holiday_rule offers both the day before and after but weekend_named_offer is not 'both'")
    for b in spec.dates.bands:
        r = low(b.deadline_rule)
        if "calendar" in r and b.deadline_calendar_days_after_today is None:
            errs.append(f"dates.bands[{b.name}].deadline_rule says calendar days but deadline_calendar_days_after_today is empty")
        if "business" in r and "calendar" not in r and b.deadline_business_days_after_today is None:
            errs.append(f"dates.bands[{b.name}].deadline_rule says business days but deadline_business_days_after_today is empty")
    w = low(spec.dates.weekend_or_holiday_rule)
    if re.search(r"\b(before|previous|preceding|prior|earlier|back)\b", w) and "next" not in w.split("before")[0] and spec.dates.weekend_named_offer == "next_business_day":
        errs.append("dates.weekend_or_holiday_rule moves the date backwards but weekend_named_offer is next_business_day")
    v = low(spec.dates.vague_period_rule)
    if re.search(r"attempt|first proposal|first offer|third business|next business day", v) and "deadline" not in v.replace("not the latest", "").replace("not the deadline", "") and spec.dates.vague_period_fallback != "attempt1":
        errs.append("dates.vague_period_rule falls back to the attempt-1 date but vague_period_fallback is deadline")
    c = " ".join(low(x) for x in spec.confirm.extra_rules) + " " + " ".join(low(x) for x in spec.global_extra_rules)
    if re.search(r"\b(twice|two more|three (tries|times|attempts)|3 (tries|times|attempts)|retry twice|up to 3)\b", c) and spec.confirm.max_tries_on_failure <= 2:
        errs.append("a text rule allows more than one retry of create_promise but confirm.max_tries_on_failure is 2")
    cb = low(spec.third_party.callback.day_rule)
    if re.search(r"after that|the one after|following business day|two business days|day after next", cb) and spec.third_party.callback.max_business_days_ahead < 2:
        errs.append("third_party.callback.day_rule allows the business day after the next one but max_business_days_ahead is 1")
    d = " ".join(low(x) for x in spec.identity.extra_rules) + " " + low(spec.identity.decline.explain_once_text)
    if re.search(r"(first time|at once|immediately|straight away|without (an )?explanation|no explanation)", d) and re.search(r"(close|end the call|hang up)", d) and spec.identity.decline.explain_first:
        errs.append("identity text says the first refusal closes the call but decline.explain_first is true")
    q = low(spec.amounts.today_question) + " ".join(low(x) for x in spec.amounts.extra_rules + spec.persuasion.extra_rules)
    if re.search(r"(asked|say|ask) (exactly|verbatim|once for all products.*:)", q) and not spec.amounts.today_question and not spec.multi_product.today_question_all:
        errs.append("a text rule quotes the exact 'pay today' question but amounts.today_question / multi_product.today_question_all are empty")
    m = low(spec.multi_product.closing_rule) + " ".join(low(x) for x in spec.multi_product.extra_rules)
    if re.search(r"priorit|takes precedence|over (hardship|refused|service)|>", m) and not spec.multi_product.no_promise_reason_priority:
        errs.append("multi_product text ranks the note reasons but no_promise_reason_priority is empty")
    return errs


def apply_text_modes(spec, problems: list[str]) -> list[str]:
    """Last resort when a consistency problem survives every extraction attempt: the matching quantity is left to the
    model (its *_mode becomes 'text'), so the code stops computing and enforcing a number the text contradicts.
    Returns the fields switched."""
    switched = []
    blob = " ".join(problems).lower()
    if ("floor_percent" in blob or "floor_rule" in blob) and spec.amounts.floor_mode != "text":
        spec.amounts.floor_mode = "text"; switched.append("amounts.floor_mode")
    if "callback" in blob and spec.third_party.callback.day_mode != "text":
        spec.third_party.callback.day_mode = "text"; switched.append("third_party.callback.day_mode")
    if ("attempt-1" in blob or "attempt1" in blob or "vague_period" in blob) and spec.persuasion.attempt1_mode != "text":
        spec.persuasion.attempt1_mode = "text"; switched.append("persuasion.attempt1_mode")
    return switched


def lint_spec(spec, tools: list[Tool], fm: dict) -> list[str]:
    """Values the CallSpec sends to the bank must exist in the tool API's enums, and text rules must agree with the
    structured fields. Returns problems (empty = fine)."""
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
    errs += consistency_checks(spec)
    return errs
