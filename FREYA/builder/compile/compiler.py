"""CallSpec -> Freya workflow JSON. Deterministic; no LLM. Patterns follow kit docs and the verified example builder."""
from __future__ import annotations

from ..extract.callspec import CallSpec, Outcome, Tool
from . import codegen, prompts


# ----------------------------------------------------------------------------- json helpers

def grp(*conds):
    return {"logic": "or", "conditions": list(conds)}


def eq(var, val):
    return {"variable": var, "operator": "equals", "operand": val}


def gt(var, val):
    return {"variable": var, "operator": "greater_than", "operand": val}


def go(target, desc, cond):
    return {"target_node": target, "description": desc, "condition": cond}


def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def bye_tr(target):
    return {"target_node": target, "description": "The customer says goodbye, hangs up, or clearly ends the conversation",
            "condition": {"operator": "matches_intent", "description": "The customer says goodbye, says they are hanging up, or clearly ends the conversation (not a refusal to pay, not a question)"}}


def tool_tr(target, desc):
    return {"target_node": target, "description": desc, "is_tool_call": True,
            "condition": {"operator": "matches_intent", "description": desc}}


def code_node(name, code, nxt, transitions=None):
    return {
        "name": name, "node_type": "code", "passthrough": True,
        "passthrough_default_transition": nxt, "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [{"type": "function", "function": {
            "name": "code_exec", "handler": "__function__:code_exec",
            "parameters": {"type": "object", "properties": {
                "code": {"type": "string", "default": code},
                "timeout_ms": {"type": "number", "default": 10000}}}}}],
        "transitions": (transitions or []) + [always(nxt)],
    }


def conv(name, task, tools=(), transitions=(), on_enter=None, extraction=(), max_turns=40, cap_to=None, first_only=False):
    n = {"name": name, "node_type": "conversation", "task_message": task,
         "tools": list(tools), "transitions": list(transitions),
         "on_enter": on_enter or {"type": "llm"}, "max_node_turns": max_turns}
    if extraction:
        n["extraction_schema"] = list(extraction)
    if cap_to:
        n["max_turn_transition"] = cap_to
    if first_only:
        n["on_enter_first_entry_only"] = True
    return n


def _sentence(rule: str) -> str:
    """'Say that payments can take one business day to appear.' -> 'Payments can take one business day to appear.'"""
    s = rule.strip()
    for pre in ("Say that ", "say that ", "Say ", "say "):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    s = s[:1].upper() + s[1:]
    return s if s.endswith(".") else s + "."


# ----------------------------------------------------------------------------- tools

class ToolBox:
    def __init__(self, spec: CallSpec):
        self.spec = spec
        self.by_name: dict[str, Tool] = {t.name: t for t in spec.tools}
        self.fm = spec.field_map or {}

    def rq(self, tool: str, canon: str) -> str:
        """Actual request field name for a canonical one."""
        return (self.fm.get("req", {}).get(tool) or {}).get(canon, canon)

    def rs(self, tool: str, canon: str) -> str:
        """Actual response field name for a canonical one."""
        return (self.fm.get("resp", {}).get(tool) or {}).get(canon, canon)

    def url(self, name: str) -> str:
        t = self.by_name.get(name)
        if not t:
            raise KeyError(f"tool {name} not in openapi")
        return t.url

    def field(self, tool: str, name: str):
        t = self.by_name.get(tool)
        if not t:
            return None
        for f in t.fields:
            if f.name == name:
                return f
        return None

    def api_tool(self, tool_name: str, fn_name: str, desc: str, body: dict, required=(), retries=0, pre="", post="", mapping=(),
                 lifecycle=None) -> dict:
        props = {self.rq(tool_name, "customer_id"): {"type": "string", "default": "{{customer_id}}"}}
        props.update(body)
        cfg = {"timeoutMs": 12000, "maxRetries": retries}
        if lifecycle:
            cfg["alwaysRunsAt"] = [lifecycle]
        t = {
            "type": "function",
            "config": cfg,
            "function": {
                "name": fn_name,
                "handler": "__function__:api_call",
                "description": desc,
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string", "default": self.url(tool_name)},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "properties": props, "required": list(required)},
                }},
            },
        }
        if pre:
            t["pre_process_code"] = pre
        if post:
            t["post_process_code"] = post
        if mapping:
            t["response_mapping"] = [{"path": p, "variable": v} for p, v in mapping]
        return t

    def model_field(self, tool: str, name: str, desc_override: str = "", type_override: str = "") -> dict:
        """A body field the model fills: default is an unresolved placeholder named after the field."""
        f = self.field(tool, name)
        d = {"type": type_override or (f.type if f else "string"), "default": "{{" + name + "}}"}
        desc = desc_override or (f.description if f else "")
        if f and f.enum:
            d["enum"] = list(f.enum)
            desc = (desc + " One of: " + ", ".join(f.enum)).strip()
        if desc:
            d["description"] = desc
        return d


# ----------------------------------------------------------------------------- compile

def compile_workflow(spec: CallSpec) -> dict:
    tb = ToolBox(spec)
    idn, tp, sp, cf, mp = spec.identity, spec.third_party, spec.special, spec.confirm, spec.multi_product

    # ---- tools the dialogue model can call
    field_enum = [q.field for q in idn.questions]
    verify_identity = tb.api_tool(
        "verify_identity", "verify_identity",
        "Check ONE security answer. CALL it every time the customer gives a complete answer to a security question.",
        {tb.rq("verify_identity", "field"): {"type": "string", "enum": field_enum, "default": "{{field}}",
                   "description": "Which question was answered: " + " or ".join(field_enum) + "."},
         tb.rq("verify_identity", "answer"): tb.model_field("verify_identity", tb.rq("verify_identity", "answer"), desc_override="; ".join(f"{q.field}: {q.answer_format}" for q in idn.questions))},
        required=[tb.rq("verify_identity", "field"), tb.rq("verify_identity", "answer")], post=codegen.verify_post(spec), mapping=[("data.id_state", "id_state")])

    promise_body = {
        "amount_kind": {"type": "string", "enum": ["full", "floor", "custom"], "default": "{{amount_kind}}",
                        "description": "full: the full past-due amount of this product. floor: the floor of this product. custom: another agreed amount (then also give amount)."},
        tb.rq("create_promise", "amount"): tb.model_field("create_promise", tb.rq("create_promise", "amount"), desc_override="The agreed amount as a number, only when amount_kind is custom.", type_override="number"),
        tb.rq("create_promise", "date"): tb.model_field("create_promise", tb.rq("create_promise", "date"), desc_override="The agreed payment date, YYYY-MM-DD."),
    }
    if mp.enabled:
        promise_body[tb.rq("create_promise", "product_id")] = tb.model_field("create_promise", tb.rq("create_promise", "product_id"), desc_override="product_id of this product from ACCOUNT, e.g. p1. Copy it exactly.")
    create_promise = tb.api_tool(
        "create_promise", "create_promise",
        "Record ONE payment promise for ONE product. CALL it only after the customer said a clear yes to your read-back of product, amount and date.",
        promise_body, required=["amount_kind", tb.rq("create_promise", "date")] + ([tb.rq("create_promise", "product_id")] if mp.enabled else []),
        pre=codegen.promise_pre(spec), post=codegen.promise_post(spec),
        mapping=[("data.promise_state", "promise_state")] + ([("data.all_products_done", "all_products_done")] if mp.enabled else []))

    schedule_callback = tb.api_tool(
        "schedule_callback", "schedule_callback",
        "Book a callback for the customer. CALL it as soon as the person gives a day and a time inside the allowed callback window.",
        {tb.rq("schedule_callback", "date"): tb.model_field("schedule_callback", tb.rq("schedule_callback", "date"), desc_override="Callback date, YYYY-MM-DD."),
         tb.rq("schedule_callback", "time"): tb.model_field("schedule_callback", tb.rq("schedule_callback", "time"), desc_override="Callback time, HH:MM, 24-hour.")},
        required=[tb.rq("schedule_callback", "date"), tb.rq("schedule_callback", "time")], pre=codegen.callback_pre(spec), post=codegen.callback_post(spec), mapping=[("data.cb_state", "cb_state")])

    def xfer(queue: str, when: str) -> dict:
        return tb.api_tool("transfer_to_agent", f"transfer_{queue}", when, {tb.rq("transfer_to_agent", "queue"): {"type": "string", "default": queue}},
                           post=codegen.transfer_post(queue, spec), mapping=[("data.xfer_state", f"xfer_{queue}_state")])

    hs = sp.hardship
    transfer_support = xfer(hs.offer_queue, f"Transfer the call to the {hs.offer_queue} team. CALL it only when a customer with {', '.join(hs.triggers)} accepts your offer to connect them.")
    transfer_restructuring = xfer(sp.restructuring.queue, f"Transfer the call to the {sp.restructuring.queue} team. CALL it when the customer asks for {' or '.join(sp.restructuring.triggers)}.")
    transfer_general = xfer(sp.human.queue, "Transfer the call to a human agent. CALL it only when the customer still insists on a human" + (" after you asked once whether you can help." if sp.human.ask_once_if_can_help else "."))

    add_note = None
    if mp.enabled:
        rf = tb.field("add_note", tb.rq("add_note", "reason"))
        reasons = list(rf.enum) if rf and rf.enum else list(mp.note_reasons)
        add_note = tb.api_tool(
            "add_note", "add_note",
            "Record why ONE product ends without a promise. CALL it once for each product that gets no promise, with that product_id and the reason.",
            {tb.rq("add_note", "product_id"): tb.model_field("add_note", tb.rq("add_note", "product_id"), desc_override="product_id from ACCOUNT, e.g. p2. Copy it exactly."),
             tb.rq("add_note", "reason"): {"type": "string", "enum": reasons, "default": "{{note_reason}}", "description": "One of: " + ", ".join(reasons)}},
            required=[tb.rq("add_note", "product_id"), tb.rq("add_note", "reason")], pre=codegen.note_pre(spec, reasons), post=codegen.note_post(spec),
            mapping=[("data.note_state", "note_state"), ("data.all_products_done", "all_products_done")])

    close_call = tb.api_tool(
        "close_call", "close_call", "Record how the call ended.",
        {tb.rq("close_call", "outcome"): {"type": "string", "default": "{{outcome}}"}, tb.rq("close_call", "reason"): {"type": "string", "default": "{{reason}}"}},
        required=[tb.rq("close_call", "outcome")], pre=codegen.close_pre(spec), lifecycle="end_of_call")

    # ---- closing nodes: hint (outcome, reason, farewell); decide_outcome may override
    name_tok = "NAME"
    thanks = f"Thank you for your time, {name_tok}. Goodbye."
    promise_farewell = f"Your promise is recorded. {cf.after_record_sentence} {thanks}"
    closes: dict[str, tuple[str, str, str]] = {
        "close_promise": (spec.closing.promise_outcome, "", promise_farewell),
        "close_service_error": (cf.failed_twice_close.outcome, cf.failed_twice_close.reason, f"I am sorry, I could not record your promise because of a technical problem. {thanks}"),
        "close_paid": (sp.paid.close.outcome, sp.paid.close.reason, f"Thank you for letting me know. {_sentence(sp.paid.say)} {thanks}"),
        "close_dispute": (sp.dispute.close.outcome, sp.dispute.close.reason, f"I understand. {thanks}"),
        "close_refused": (spec.persuasion.refused_close.outcome, spec.persuasion.refused_close.reason, f"I understand. {thanks}"),
        "close_hardship": (hs.decline_close.outcome, hs.decline_close.reason, f"Thank you for your time, {name_tok}. Goodbye."),
        f"close_xfer_{hs.offer_queue}": (hs.accept_close.outcome, hs.accept_close.reason, f"I am connecting you with our {hs.offer_queue} team now. Thank you for your time. Goodbye."),
        f"close_xfer_{sp.restructuring.queue}": (sp.restructuring.close.outcome, sp.restructuring.close.reason, "I am connecting you with the team that handles payment plans now. Thank you for your time. Goodbye."),
        f"close_xfer_{sp.human.queue}": (sp.human.close.outcome, sp.human.close.reason, "I am connecting you with a colleague now. Thank you for your time. Goodbye."),
        "close_failed": (idn.failed_close.outcome, idn.failed_close.reason, f"I am sorry, I could not verify your identity. {idn.after_failed_text.replace('Tell the customer to ', 'Please ').replace('Do not state the debt.', '').strip()} Thank you for your time. Goodbye."),
        "close_declined": (idn.decline.close.outcome, idn.decline.close.reason, "I understand. Without the security questions I cannot continue. Thank you for your time. Goodbye."),
        "close_callback": (tp.callback_close.outcome, tp.callback_close.reason, "Thank you, we will call back then. Thank you for your time. Goodbye."),
        "close_no_callback": (tp.no_callback_close.outcome, tp.no_callback_close.reason, "Thank you, we will try again another time. Thank you for your time. Goodbye."),
        "close_wrong_number": (tp.wrong_number_close.outcome, tp.wrong_number_close.reason, "I apologise for the inconvenience. Thank you for your time. Goodbye."),
        "close_deceased": (tp.deceased_close.outcome, tp.deceased_close.reason, f"{tp.deceased_sentence} Thank you for your time. Goodbye."),
        "close_unclear": (spec.opening.unclear_close.outcome, spec.opening.unclear_close.reason, "I could not confirm who I am speaking with, so I will end the call here. Thank you for your time. Goodbye."),
        "close_account_error": (cf.failed_twice_close.outcome, cf.failed_twice_close.reason, "I am sorry, I cannot reach your account details right now because of a technical problem. Thank you for your time. Goodbye."),
    }
    if mp.enabled:
        closes["close_done"] = (spec.persuasion.refused_close.outcome, spec.persuasion.refused_close.reason, f"I understand. {thanks}")

    # ---- extraction for the opening
    line_status = {
        "name": "line_status", "type": "string", "min_confidence": 0.6,
        "enum_values": ["confirmed", "someone_else", "wrong_number", "deceased"],
        "description": prompts.line_status_description(spec),
    }

    def opening_routes():
        return [
            go("security", "The customer confirmed who they are", grp(eq("line_status", "confirmed"))),
            go("third_party", "Someone else answered", grp(eq("line_status", "someone_else"))),
            go("close_wrong_number", "Wrong number", grp(eq("line_status", "wrong_number"))),
            go("close_deceased", "The customer has died", grp(eq("line_status", "deceased"))),
        ]

    nodes: dict[str, dict] = {}
    nodes["setup"] = code_node("setup", codegen.facts_code(spec), "opening")

    # opening + retries (max_asks - 1 retry nodes)
    retries = max(1, spec.opening.max_asks) - 1
    chain = ["opening"] + [f"opening_retry_{i + 1}" for i in range(retries)]
    for i, nm in enumerate(chain):
        nxt = chain[i + 1] if i + 1 < len(chain) else "close_unclear"
        if i == 0:
            nodes[nm] = conv(nm, prompts.opening_task(spec), on_enter={"type": "tts", "text": prompts.opening_line(spec)},
                             extraction=[line_status], transitions=opening_routes() + [bye_tr("close_unclear"), always(nxt)], first_only=True,
                             max_turns=4, cap_to=nxt)
        else:
            nodes[nm] = conv(nm, prompts.retry_task(spec), extraction=[line_status],
                             transitions=opening_routes() + [bye_tr("close_unclear"), always(nxt)], first_only=True, max_turns=4, cap_to=nxt)

    sec_tools = [verify_identity] + ([transfer_general] if idn.human_request else [])
    first_q = idn.questions[0]
    nodes["security"] = conv(
        "security", prompts.security_task(spec),
        on_enter={"type": "tts", "text": f"Thank you, {spec.address_customer_as}. Before I continue, I need to ask you {len(idn.questions)} security questions. {first_q.ask}"},
        first_only=True, tools=sec_tools,
        transitions=[
            go("load_account", "All security answers verified", grp(eq("id_state", "verified"),
               eq(f"verify_identity_response.data.{tb.rs('verify_identity', 'all_verified')}", "true"), eq(f"verify_identity_response.data.{tb.rs('verify_identity', 'all_verified')}", "True"))),
            go("close_failed", "The identity check failed", grp(eq("id_state", "failed"))),
        ] + ([go(f"close_xfer_{sp.human.queue}", "Transferred to a human", grp(eq(f"xfer_{sp.human.queue}_state", "done")))] if idn.human_request else []) + [
            tool_tr("close_declined", "The customer declined the security questions twice, or said twice they do not want to talk"),
            bye_tr("close_declined"),
        ],
        max_turns=30, cap_to="close_declined")

    nodes["load_account"] = {
        "name": "load_account", "node_type": "api_request", "passthrough": True,
        "passthrough_default_transition": "account_facts", "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True, "suppress_tool_results": True,
        "pre_actions": [{
            "type": "function", "config": {"timeoutMs": 12000, "maxRetries": 2},
            "function": {"name": "get_account", "handler": "__function__:api_call", "description": "Get the late products.",
                         "parameters": {"type": "object", "properties": {
                             "url": {"type": "string", "default": tb.url("get_account")},
                             "method": {"type": "string", "default": "POST"},
                             "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                             "body": {"type": "object", "properties": {tb.rq("get_account", "customer_id"): {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
        "response_mapping": [{"path": f"data.{tb.rs('get_account', 'products')}", "variable": "products"}],
        "transitions": [always("account_facts")],
    }
    nodes["account_facts"] = code_node("account_facts", codegen.facts_code(spec), "close_account_error",
                                       transitions=[go("negotiate", "Account facts ready", grp(eq("account_state", "ok")))])

    neg_tools = [create_promise, transfer_support, transfer_restructuring, transfer_general] + ([add_note] if add_note else [])
    xfer_routes = [
        go(f"close_xfer_{q}", f"Transferred to {q}", grp(eq(f"xfer_{q}_state", "done")))
        for q in dict.fromkeys([hs.offer_queue, sp.restructuring.queue, sp.human.queue])
    ]
    if mp.enabled:
        # done when promises + notes >= n_products, enumerated from the engine's own success counters (robust to parallel tool calls)
        combos = []
        for k in range(1, 6):
            for p in range(0, k + 1):
                n = k - p
                conds = [eq("n_products", str(k))]
                if p:
                    conds.append(gt("create_promise_success_count", p - 1))
                if n:
                    conds.append(gt("add_note_success_count", n - 1))
                combos.append({"logic": "and", "conditions": conds})
        promise_route = go("close_promise", "Every product has a promise or a note", {"logic": "or", "conditions": [eq("all_products_done", "yes")] + combos})
        service_route = []
    else:
        promise_route = go("close_promise", "The promise was recorded", grp(eq("promise_state", "recorded")))
        service_route = [go("close_service_error", "The promise service failed twice", grp(eq("promise_state", "failed_twice"), gt("create_promise_failure_count", 1)))]
    neg_transitions = [promise_route] + service_route + xfer_routes
    if mp.enabled:
        neg_transitions += [
            tool_tr("close_done", "Every product has a promise or a note and the call can end"),
            tool_tr("close_hardship", f"A customer with {', '.join(hs.triggers)} declined the {hs.offer_queue} team"),
            tool_tr("close_refused", "The customer said twice they do not want to talk"),
        ]
    else:
        neg_transitions += [
            tool_tr("close_paid", f"The customer says {' or '.join(sp.paid.triggers)}"),
            tool_tr("close_dispute", f"The customer says {' or '.join(sp.dispute.triggers)}"),
            tool_tr("close_hardship", f"A customer with {', '.join(hs.triggers)} declined the {hs.offer_queue} team"),
            tool_tr("close_refused", "The persuasion attempts are used up and the customer still refuses, or said twice they do not want to talk"),
            tool_tr("close_service_error", "create_promise failed twice and nothing was recorded"),
        ]
    neg_transitions.append(bye_tr("close_on_goodbye"))
    situation = {
        "name": "situation", "type": "string", "min_confidence": 0.6,
        "enum_values": ["hardship", "paid", "dispute", "plan", "human", "refusal", "negotiating"],
        "description": ("The customer's situation from their LAST message, for closing the call correctly if they hang up. "
                        f"hardship: {', '.join(hs.triggers)}. paid: says they already paid. dispute: says the debt or product is not theirs. "
                        f"plan: asks for {' or '.join(sp.restructuring.triggers)}. human: insists on a person. refusal: refuses to pay with no date or amount. "
                        "negotiating: proposes or discusses a date or an amount. Leave empty when nothing new was said about this."),
    }
    nodes["negotiate"] = conv(
        "negotiate", prompts.negotiate_task(spec),
        on_enter={"type": "tts", "text": "{{debt_statement}}"}, first_only=True,
        tools=neg_tools, transitions=neg_transitions, extraction=[situation],
        max_turns=60 if mp.enabled else 40, cap_to="close_refused")
    closes["close_on_goodbye"] = None  # placeholder, replaced below

    nodes["third_party"] = conv(
        "third_party", prompts.third_party_task(spec), first_only=True,
        tools=[schedule_callback],
        transitions=[
            go("close_callback", "The callback is booked", grp(eq("cb_state", "booked"))),
            go("close_no_callback", "Second time outside the window", grp(eq("cb_state", "rejected_twice"))),
            tool_tr("close_no_callback", "No callback time inside the allowed window could be agreed after asking once more"),
            tool_tr("close_wrong_number", "The number does not belong to the customer"),
            tool_tr("close_deceased", "The customer has died"),
            bye_tr("close_no_callback"),
        ],
        max_turns=20, cap_to="close_no_callback")

    closes.pop("close_on_goodbye", None)
    for nm, (o, r, text) in closes.items():
        nodes[nm] = code_node(nm, codegen.close_hint_code(o, r, text), "decide_outcome")
    goodbye_map = {
        "hardship": list(closes["close_hardship"]), "paid": list(closes["close_paid"]), "dispute": list(closes["close_dispute"]),
        "default": list(closes["close_refused"]),
    }
    nodes["close_on_goodbye"] = code_node("close_on_goodbye", codegen.close_on_goodbye_code(goodbye_map), "decide_outcome")
    farewells = {
        "paid": closes["close_paid"][2],
        "no_promise": closes["close_refused"][2],
        "no_promise_" + hs.decline_close.reason: closes["close_hardship"][2],
        "no_promise_" + sp.dispute.close.reason: closes["close_dispute"][2],
        "no_promise_" + cf.failed_twice_close.reason: closes["close_service_error"][2],
        "xfer_" + hs.offer_queue: closes[f"close_xfer_{hs.offer_queue}"][2],
        "xfer_" + sp.restructuring.queue: closes[f"close_xfer_{sp.restructuring.queue}"][2],
        "xfer_" + sp.human.queue: closes[f"close_xfer_{sp.human.queue}"][2],
    }
    nodes["decide_outcome"] = code_node("decide_outcome", codegen.decide_outcome_code(spec, promise_farewell, farewells), "goodbye")
    nodes["goodbye"] = {
        "name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True, "transitions": [],
        "terminal": {"type": "function", "function": {
            "name": "call_closed", "handler": "__function__:end_call",
            "parameters": {"type": "object", "properties": {
                "message_mode": {"type": "string", "default": "custom"},
                "spoken_message": {"type": "string", "default": "{{farewell}}"}}}}},
    }

    test_vars = {"customer_id": "c_test", "now": "2026-01-05T11:00"}
    for v in spec.call_variables:
        test_vars.setdefault(v.name, {"first_name": "Test", "last_name": "Customer", "title": "Mr"}.get(v.name, "x"))

    return {
        "initial_node": "setup",
        "system_prompt": prompts.system_prompt(spec),
        "nodes": nodes,
        "global_nodes": {},
        "tools": [close_call],
        "test_variables": test_vars,
    }
