"""Generate out/brief-a.workflow.json from Brief A and tools/openapi.json.

    python3 out/build_brief_a.py
"""
import json, pathlib

BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1"
OUT = pathlib.Path(__file__).resolve().parent / "brief-a.workflow.json"

# ---------------------------------------------------------------- helpers

def api_tool(name, desc, body, required=(), retries=0, pre="", post="", mapping=()):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update(body)
    t = {
        "type": "function",
        "config": {"timeoutMs": 12000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc,
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "default": f"{BASE}/{name if name not in XFER else 'transfer_to_agent'}"},
                "method": {"type": "string", "default": "POST"},
                "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                "body": {"type": "object", "properties": props, "required": list(required)},
            }},
        },
    }
    if pre: t["pre_process_code"] = pre
    if post: t["post_process_code"] = post
    if mapping: t["response_mapping"] = [{"path": p, "variable": v} for p, v in mapping]
    return t

XFER = {"transfer_support": "support", "transfer_restructuring": "restructuring", "transfer_general": "general"}

def grp(*conds):
    return {"logic": "or", "conditions": list(conds)}

def eq(var, val):
    return {"variable": var, "operator": "equals", "operand": val}

def go(target, desc, cond):
    return {"target_node": target, "description": desc, "condition": cond}

def always(target):
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}

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
    if extraction: n["extraction_schema"] = list(extraction)
    if cap_to: n["max_turn_transition"] = cap_to
    if first_only: n["on_enter_first_entry_only"] = True
    return n

# ---------------------------------------------------------------- code: dates and account facts
# No double braces anywhere in code. Never raise.

FACTS_CODE = r'''
import datetime, json, re
HOL = set(['2026-10-26', '2026-11-11', '2026-11-26', '2026-12-25', '2027-01-01'])
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
ONE = datetime.timedelta(days=1)
def isbd(d):
    return d.weekday() < 5 and d.isoformat() not in HOL
def say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year)
def nth_bd(d, n):
    c = 0
    while c < n:
        d = d + ONE
        if isbd(d):
            c += 1
    return d
def next_bd(d):
    while not isbd(d):
        d = d + ONE
    return d
def last_bd_of_week(mon):
    for i in range(4, -1, -1):
        x = mon + datetime.timedelta(days=i)
        if isbd(x):
            return x
    return None
def money(x):
    x = round(float(x), 2)
    if abs(x - round(x)) < 0.005:
        return str(int(round(x)))
    return '%.2f' % x
def as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip().startswith('['):
        try:
            return json.loads(v)
        except Exception:
            pass
        try:
            import ast
            return ast.literal_eval(v)
        except Exception:
            pass
    return None
def find_products():
    for k in ['products', 'load_account_response.data.products', 'get_account_response.data.products']:
        v = as_list(vars.get(k))
        if v:
            return v
    items = dict()
    for k in list(vars.keys()):
        m = re.search(r'products\.(\d+)\.(\w+)$', str(k))
        if m:
            items.setdefault(int(m.group(1)), dict())[m.group(2)] = vars.get(k)
    return [items[i] for i in sorted(items)]
try:
    try:
        nowdt = datetime.datetime.fromisoformat(str(vars.get('now') or '').strip()[:16])
    except Exception:
        nowdt = datetime.datetime.now()
    today = nowdt.date()
    now_hm = nowdt.strftime('%H:%M')
    vars['today_iso'] = today.isoformat()
    vars['now_hm'] = now_hm
    vars['today_text'] = say(today) + ' (' + today.isoformat() + '), time ' + now_hm
    # callback window: today after now, or the next business day, 10:00 to 19:00
    nbd = next_bd(today + ONE)
    cb = []
    cbd = []
    if now_hm < '19:00':
        start = '10:00' if now_hm < '10:00' else 'after ' + now_hm
        cb.append('today, ' + say(today) + ' (' + today.isoformat() + '), from ' + start + ' until 19:00')
        cbd.append(today.isoformat())
    cb.append(say(nbd) + ' (' + nbd.isoformat() + '), from 10:00 until 19:00')
    cbd.append(nbd.isoformat())
    vars['callback_text'] = ' or '.join(cb)
    vars['cb_dates'] = ','.join(cbd)
    # this / next weekday
    monday = today - datetime.timedelta(days=today.weekday())
    lines = []
    for i in range(7):
        a = monday + datetime.timedelta(days=i)
        b = a + datetime.timedelta(days=7)
        lines.append('- this ' + WD[i] + ' = ' + say(a) + ('' if a >= today else ' (already past)') + '; next ' + WD[i] + ' = ' + say(b))
    vars['weekday_text'] = '\n'.join(lines)
    prods = find_products()
    if prods:
        p = prods[0]
        typ = str(p.get('type') or '')
        past = float(p.get('past_due') or 0)
        dl = int(float(p.get('days_late') or 0))
        if typ == 'credit_card':
            floor = float(p.get('minimum_payment') or 0)
            label = 'credit card ending ' + str(p.get('card_last4') or '')
        else:
            floor = float(p.get('instalment_amount') or 0)
            label = 'car loan' if typ == 'car_loan' else 'personal loan'
        if dl <= 7:
            band, deadline, attempts = 'early', nth_bd(today, 12), 1
        else:
            band, deadline, attempts = 'late', nth_bd(today, 7), 2
        a1 = last_bd_of_week(monday)
        if a1 is None or a1 <= today:
            a1 = last_bd_of_week(monday + datetime.timedelta(days=7))
        if a1 > deadline:
            a1 = deadline
        valid = []
        cal = []
        d = today
        end = max(deadline + datetime.timedelta(days=10), today + datetime.timedelta(days=28))
        while d <= end:
            tag = say(d) + ' (' + d.isoformat() + ')'
            if d > deadline:
                cal.append('- ' + tag + ': after the deadline, cannot be recorded. Offer the deadline ' + say(deadline) + '.')
            elif isbd(d):
                valid.append(d.isoformat())
                cal.append('- ' + tag + ': allowed' + (' (today)' if d == today else '') + '.')
            else:
                kind = 'a bank holiday' if d.isoformat() in HOL else 'a weekend day'
                cal.append('- ' + tag + ': ' + kind + ', cannot be recorded. Offer the next business day, ' + say(next_bd(d)) + '.')
            d = d + ONE
        vars['product_id'] = str(p.get('product_id') or '')
        vars['product_label'] = label
        vars['past_due_amount'] = round(past, 2)
        vars['past_due_text'] = money(past)
        vars['floor_amount'] = round(floor, 2)
        vars['floor_text'] = money(floor)
        vars['days_late'] = dl
        vars['band'] = band
        vars['attempts'] = attempts
        vars['deadline_iso'] = deadline.isoformat()
        vars['deadline_text'] = say(deadline) + ' (' + deadline.isoformat() + ')'
        vars['attempt1_text'] = say(a1) + ' (' + a1.isoformat() + ')'
        vars['valid_dates'] = ','.join(valid)
        vars['calendar_text'] = '\n'.join(cal)
        vars['debt_statement'] = ('Thank you, the security check is complete. I am calling from the Freya Bank collections team about a late payment on your '
            + label + '. The past-due amount is ' + money(past) + ', and the payment is ' + str(dl) + (' day' if dl == 1 else ' days')
            + ' late. Can you make this payment today?')
        vars['account_state'] = 'ok'
    else:
        vars['account_state'] = 'missing'
except Exception as e:
    vars['account_state'] = 'missing'
    vars['facts_error'] = str(e)[:200]
'''

# ---------------------------------------------------------------- hooks

STRIP = "    if isinstance(result, dict):\n        result.pop('header', None)\n"

VERIFY_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        t = lambda x: str(x).lower() == 'true'
        left = d.get('wrong_answers_left')
        try:
            left = int(left)
        except Exception:
            left = None
        err = str(d.get('error') or '').lower()
        if t(d.get('all_verified')):
            d['id_state'] = 'verified'
            d['what_to_do_next'] = 'Both security answers are correct.'
        elif d.get('hint') == 'day_month_swapped':
            d['id_state'] = 'retry'
            d['what_to_do_next'] = 'This did NOT count as a wrong answer. The day and the month seem swapped. Ask the customer to say their date of birth again with the month as a word, for example 5 March 1988. Then call verify_identity again.'
        elif left is not None and left <= 0 and not t(d.get('verified')):
            d['id_state'] = 'failed'
            d['what_to_do_next'] = 'Three wrong answers: the check has failed. Say nothing about the account.'
        elif not t(d.get('ok')) and ('lock' in err or 'attempt' in err or 'fail' in err):
            d['id_state'] = 'failed'
            d['what_to_do_next'] = 'The check has failed. Say nothing about the account.'
        elif not t(d.get('ok')):
            d['id_state'] = 'retry'
            d['what_to_do_next'] = 'The answer could not be read and did NOT count as wrong. Ask the customer for the full answer again (for a date of birth: day, month and year).'
        elif t(d.get('verified')):
            d['id_state'] = 'next'
            d['what_to_do_next'] = 'This answer is correct. Now ask the security question that has not been passed yet: the last four digits of the phone number on file.'
        else:
            d['id_state'] = 'retry'
            d['what_to_do_next'] = 'This answer is wrong. Tell the customer it does not match our records and ask the same question again.'
except Exception:
    pass
'''

PROMISE_PRE = r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        good = True
        dt = str(b.get('date') or '').strip()[:10]
        b['date'] = dt
        try:
            amt = round(float(str(b.get('amount')).replace(',', '')), 2)
            b['amount'] = amt
        except Exception:
            amt = None
            good = False
        valid = [x for x in str(vars.get('valid_dates') or '').split(',') if x]
        if valid and dt not in valid:
            good = False
        try:
            fl = round(float(vars.get('floor_amount')), 2)
            full = round(float(vars.get('past_due_amount')), 2)
            if amt is not None and (amt < fl - 0.001 or amt > full + 0.001):
                good = False
        except Exception:
            pass
        pid = str(vars.get('product_id') or '')
        if pid:
            b['product_id'] = pid
        if not good:
            b['date'] = 'REJECTED'
except Exception:
    pass
'''

PROMISE_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() == 'true':
            d['promise_state'] = 'recorded'
            d['what_to_do_next'] = 'The promise is recorded.'
        elif 'unknown customer' in str(d.get('error') or '') or 'must be' in str(d.get('error') or ''):
            d['promise_state'] = 'rejected'
            d['error'] = 'not allowed by bank rules'
            d['what_to_do_next'] = 'NOT recorded: this date or amount breaks the bank rules. Allowed dates are the business days from today to the deadline. Allowed amounts are from the floor to the full past-due amount. Tell the customer that this cannot be recorded and offer a valid option following your rules. Never say it is recorded.'
        else:
            n = 0
            try:
                n = int(vars.get('promise_fail_count') or 0)
            except Exception:
                n = 0
            n = n + 1
            try:
                vars['promise_fail_count'] = n
            except Exception:
                pass
            if n >= 2:
                d['promise_state'] = 'failed_twice'
                d['what_to_do_next'] = 'The service failed again. Nothing was recorded.'
            else:
                d['promise_state'] = 'failed_once'
                d['what_to_do_next'] = 'The service failed and nothing was recorded. Call create_promise again now, once, with exactly the same amount and date. Do not say it is recorded.'
except Exception:
    pass
'''

CB_PRE = r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        good = True
        dt = str(b.get('date') or '').strip()[:10]
        b['date'] = dt
        tm = str(b.get('time') or '').strip()
        parts = tm.replace('.', ':').split(':')
        try:
            hh = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            tm = '%02d:%02d' % (hh, mm)
        except Exception:
            good = False
        b['time'] = tm
        dates = [x for x in str(vars.get('cb_dates') or '').split(',') if x]
        if dates and dt not in dates:
            good = False
        if tm < '10:00' or tm > '19:00':
            good = False
        if dt == str(vars.get('today_iso') or '') and tm <= str(vars.get('now_hm') or ''):
            good = False
        if not good:
            b['date'] = 'REJECTED'
except Exception:
    pass
'''

CB_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() == 'true':
            d['cb_state'] = 'booked'
            d['what_to_do_next'] = 'The callback is booked.'
        elif 'unknown customer' in str(d.get('error') or '') or 'must be' in str(d.get('error') or ''):
            n = 0
            try:
                n = int(vars.get('cb_reject_count') or 0)
            except Exception:
                n = 0
            n = n + 1
            try:
                vars['cb_reject_count'] = n
            except Exception:
                pass
            d['error'] = 'outside the allowed callback window'
            if n >= 2:
                d['cb_state'] = 'rejected_twice'
                d['what_to_do_next'] = 'Not booked: outside the allowed window again. Do not schedule.'
            else:
                d['cb_state'] = 'rejected'
                d['what_to_do_next'] = 'NOT booked: that day or time is outside the allowed callback window. Say we can only call back within the allowed times and ask once for another time.'
        else:
            d['cb_state'] = 'failed'
            d['what_to_do_next'] = 'The booking service failed. Call schedule_callback once more with the same date and time.'
except Exception:
    pass
'''

XFER_POST = r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get('ok')).lower() == 'true':
            d['xfer_state'] = 'done'
            d['what_to_do_next'] = 'Transferred.'
        else:
            d['xfer_state'] = 'failed'
            d['what_to_do_next'] = 'The transfer failed. Tell the customer you could not transfer the call right now.'
except Exception:
    pass
'''

CLOSE_PRE = r'''
try:
    b = config.get('body')
    if isinstance(b, dict) and (b.get('outcome') in ('promise', 'paid') or not b.get('reason')):
        b.pop('reason', None)
except Exception:
    pass
'''

# ---------------------------------------------------------------- tools

verify_identity = api_tool(
    "verify_identity",
    "Check ONE security answer. CALL it every time the customer gives a complete answer to a security question.",
    {"field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "default": "{{field}}",
               "description": "Which question was answered: date_of_birth or phone_last4."},
     "answer": {"type": "string", "default": "{{answer}}",
                "description": "date_of_birth as YYYY-MM-DD (numbers-only dates are day, month, year). phone_last4 as four digits."}},
    required=["field", "answer"], post=VERIFY_POST, mapping=[("data.id_state", "id_state")])

create_promise = api_tool(
    "create_promise",
    "Record the payment promise. CALL it only after the customer said a clear yes to your read-back of product, amount and date.",
    {"product_id": {"type": "string", "default": "{{product_id}}"},
     "amount": {"type": "number", "default": "{{promise_amount}}", "description": "The agreed amount, a number such as 120.5."},
     "date": {"type": "string", "default": "{{promise_date}}", "description": "The agreed payment date, YYYY-MM-DD."}},
    required=["amount", "date"], pre=PROMISE_PRE, post=PROMISE_POST, mapping=[("data.promise_state", "promise_state")])

schedule_callback = api_tool(
    "schedule_callback",
    "Book a callback for the customer. CALL it as soon as the person gives a day and a time inside the allowed callback window.",
    {"date": {"type": "string", "default": "{{callback_date}}", "description": "Callback date, YYYY-MM-DD."},
     "time": {"type": "string", "default": "{{callback_time}}", "description": "Callback time, HH:MM, 24-hour."}},
    required=["date", "time"], pre=CB_PRE, post=CB_POST, mapping=[("data.cb_state", "cb_state")])

def xfer(name, when):
    q = XFER[name]
    return api_tool(name, when, {"queue": {"type": "string", "default": q}},
                    post=XFER_POST, mapping=[("data.xfer_state", f"xfer_{q}_state")])

transfer_support = xfer("transfer_support", "Transfer the call to the customer support team. CALL it only when a customer with illness, a death in the family or job loss accepts your offer to connect them with customer support.")
transfer_restructuring = xfer("transfer_restructuring", "Transfer the call to the restructuring team. CALL it when the customer asks for a new payment plan or lower instalments.")
transfer_general = xfer("transfer_general", "Transfer the call to a human agent. CALL it only when the customer still insists on a human after you asked once whether you can help.")

close_call = {
    "type": "function",
    "config": {"timeoutMs": 12000, "maxRetries": 0, "alwaysRunsAt": ["end_of_call"]},
    "function": {
        "name": "close_call", "handler": "__function__:api_call",
        "description": "Record how the call ended, from the conversation.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "default": f"{BASE}/close_call"},
            "method": {"type": "string", "default": "POST"},
            "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
            "body": {"type": "object", "required": ["outcome"], "properties": {
                "customer_id": {"type": "string", "default": "{{customer_id}}"},
                "outcome": {"type": "string", "default": "{{outcome}}",
                            "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"],
                            "description": "promise: a promise was recorded. paid: customer already paid. transferred: handed to a team. no_promise: verified, no promise. not_verified: identity check did not pass. not_reached: the customer was not on the line."},
                "reason": {"type": "string", "default": "{{reason}}",
                           "description": "transferred: restructuring, human, support. no_promise: refused, hardship, dispute, service_error. not_verified: failed, declined. not_reached: callback, no_callback, wrong_number, deceased, unclear. Empty for promise and paid."},
            }},
        }},
    },
    "pre_process_code": CLOSE_PRE,
}

# ---------------------------------------------------------------- closing nodes

CLOSES = {
    "close_promise": ("promise", "", "Your promise is recorded. You will receive a text message confirming this promise. Thank you for your time, NAME. Goodbye."),
    "close_service_error": ("no_promise", "service_error", "I am sorry, I could not record your promise because of a technical problem. Thank you for your time, NAME. Goodbye."),
    "close_paid": ("paid", "", "Thank you for letting me know. Payments can take one business day to appear. Thank you for your time, NAME. Goodbye."),
    "close_dispute": ("no_promise", "dispute", "I understand. Thank you for your time, NAME. Goodbye."),
    "close_refused": ("no_promise", "refused", "I understand. Thank you for your time, NAME. Goodbye."),
    "close_hardship": ("no_promise", "hardship", "I understand. Thank you for your time, NAME, and take care. Goodbye."),
    "close_xfer_support": ("transferred", "support", "I am connecting you with our customer support team now. Thank you for your time. Goodbye."),
    "close_xfer_restructuring": ("transferred", "restructuring", "I am connecting you with our team that handles payment plans now. Thank you for your time. Goodbye."),
    "close_xfer_general": ("transferred", "human", "I am connecting you with a colleague now. Thank you for your time. Goodbye."),
    "close_failed": ("not_verified", "failed", "I am sorry, I could not verify your identity. Please use the Freya Bank mobile app or visit a branch. Thank you for your time. Goodbye."),
    "close_declined": ("not_verified", "declined", "I understand. Without the security questions I cannot continue. Thank you for your time. Goodbye."),
    "close_callback": ("not_reached", "callback", "Thank you, we will call back then. Thank you for your time. Goodbye."),
    "close_no_callback": ("not_reached", "no_callback", "Thank you, we will try again another time. Thank you for your time. Goodbye."),
    "close_wrong_number": ("not_reached", "wrong_number", "I apologise for the inconvenience. Thank you for your time. Goodbye."),
    "close_deceased": ("not_reached", "deceased", "I am sorry for your loss. Thank you for your time. Goodbye."),
    "close_unclear": ("not_reached", "unclear", "I could not confirm who I am speaking with, so I will end the call here. Thank you for your time. Goodbye."),
    "close_account_error": ("no_promise", "service_error", "I am sorry, I cannot reach your account details right now because of a technical problem. Thank you for your time. Goodbye."),
}

def close_code(outcome, reason, text):
    return ("try:\n"
            f"    vars['outcome'] = {outcome!r}\n"
            f"    vars['reason'] = {reason!r}\n"
            "    name = (str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '')).strip()\n"
            f"    vars['farewell'] = {text!r}.replace('NAME', name)\n"
            "except Exception:\n"
            f"    vars['farewell'] = {text.replace(', NAME', '')!r}\n")

# ---------------------------------------------------------------- prompts

SYSTEM = """You are Freya Bank's digital assistant on an outbound phone call. The customer is {{title}} {{last_name}} (first name {{first_name}}). Speak English. Keep each turn to one or two short sentences. Address the customer as {{title}} {{last_name}}.

Rules that always hold:
- If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue with your task.
- If asked whether this is a scam: say they can verify this call by phoning Freya Bank's customer service number, then continue.
- If asked something you cannot answer from your instructions or a tool result: say you do not have that information. Never invent figures, dates or reasons.
- Never offer a discount, a waiver, an instalment plan or any term you were not given.
- Call at most one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing.
- A tool result may contain what_to_do_next. Follow it.
- Never say that something is recorded, booked or transferred unless a tool result says so.
- When you call a transition_to_close_... tool, do not add a goodbye yourself: the closing words are spoken for you."""

OPENING_LINE = "Hello, I am a digital assistant calling from Freya Bank, and we record this call. Am I speaking with {{title}} {{last_name}}?"

line_status = {
    "name": "line_status", "type": "string", "min_confidence": 0.6,
    "enum_values": ["confirmed", "someone_else", "wrong_number", "deceased"],
    "description": ("Who answered, from the person's LAST message, after the agent asked whether it is speaking with the customer. "
                    "confirmed: the person says yes, that's me, speaking, or gives the customer's own name. "
                    "someone_else: the person is not the customer but knows them (relative, partner, colleague), or says the customer is not available. "
                    "wrong_number: the number does not belong to the customer or the person does not know them. "
                    "deceased: the customer has died. "
                    "Leave empty for a greeting, 'go ahead', 'who is this', a question, or anything unclear."),
}

def opening_routes():
    return [
        go("security", "The customer confirmed who they are", grp(eq("line_status", "confirmed"))),
        go("third_party", "Someone else answered", grp(eq("line_status", "someone_else"))),
        go("close_wrong_number", "Wrong number", grp(eq("line_status", "wrong_number"))),
        go("close_deceased", "The customer has died", grp(eq("line_status", "deceased"))),
    ]

OPENING_TASK = ("You have just asked whether you are speaking with {{title}} {{last_name}}. "
                "Do not say why you are calling and do not mention collections, debt, payment or any product. No tool call is allowed in this turn.")

RETRY_TASK = ("You asked whether you are speaking with {{title}} {{last_name}}, and the answer was not a clear yes. "
              "If the person asked a question, answer it briefly first (who is calling: Freya Bank's digital assistant; robot or AI: you are Freya Bank's digital assistant; scam: they can verify the call by phoning Freya Bank's customer service number). "
              "Never say why you are calling and never mention collections, debt, payment or any product. "
              "Then ask once more: \"Am I speaking with {{title}} {{last_name}}?\" No tool call is allowed in this turn.")

SECURITY_TASK = """The person confirmed they are {{title}} {{last_name}}. Verify their identity before anything else. Do not mention collections, debt, payment, any amount or any product until the check is complete. If asked why you are calling, say you can explain right after the security questions.

Ask two security questions, one at a time: first the date of birth, then the last four digits of the phone number on file.
- Each time the customer gives a complete answer, call verify_identity: field date_of_birth with the answer as YYYY-MM-DD, or field phone_last4 with four digits. Convert spoken dates yourself. A date given only as numbers is day, then month, then year (05/03/1988 means 1988-03-05).
- If the customer gives only part of an answer, ask for the rest before calling the tool.
- After each result, follow what_to_do_next.
- If the customer will not answer, or asks what the call is about instead of answering: explain once that these questions protect their account, and ask again. If they refuse a second time, or ask a second time what the call is about, call transition_to_close_declined.
- If the customer says twice that they do not want to talk, call transition_to_close_declined.
- If the customer asks for a human: ask once whether you can help first. If they insist, call transfer_general."""

THIRD_TASK = """The person on the line is NOT {{title}} {{last_name}}. Never say why you are calling. Never mention any account, debt, payment, amount or product, and never ask security questions. A relative may not be told anything about the account, even if they offer to pay: say you can only speak with {{title}} {{last_name}}.

Your task: find out when {{title}} {{last_name}} can be reached, and book a callback.
Now: {{today_text}}.
Allowed callback times: {{callback_text}}.
- If the person has not said yet when the customer can be reached, ask when would be a good time to reach {{title}} {{last_name}}.
- When the person gives a day and a time inside the allowed times, call schedule_callback with date YYYY-MM-DD and time HH:MM (24-hour). If they give a day but no time, or a time but no day, ask for the missing part.
- If what they offer is outside the allowed times, say we can only call back within the allowed times and ask once for another time. If the next answer is also outside them, or they cannot give a time, call transition_to_close_no_callback. Do not book anything outside the allowed times.
- If the person says this number does not belong to {{title}} {{last_name}}: call transition_to_close_wrong_number.
- If the person says {{title}} {{last_name}} has died: call transition_to_close_deceased at once and say nothing else.
- After schedule_callback, follow what_to_do_next."""

NEGOTIATE_TASK = """The customer is verified. You have just told them about the late payment and asked "Can you make this payment today?".

TOOL RULES
- create_promise: only after the customer says a clear yes to your read-back. date as YYYY-MM-DD, amount as a number.
- If create_promise fails, follow what_to_do_next: call it once more with the same values. If it says the date or amount is not allowed, tell the customer it cannot be recorded and offer a valid option.
- When a rule below says to call a tool or a transition, call it. Saying it is not enough.

ACCOUNT
- Product: {{product_label}} (say it exactly like this).
- Full past-due amount: {{past_due_text}}. Days late: {{days_late}}.
- Floor, the lowest amount you may record: {{floor_text}}.
- Today: {{today_text}}.
- Deadline, the latest date you may record: {{deadline_text}}.
- Persuasion attempts allowed: {{attempts}}.
- Attempt 1 date: {{attempt1_text}}.

SPECIAL SITUATIONS (these come first)
- Illness, a death in the family, or job loss: say one short sentence of sympathy. Make no persuasion attempt. Offer to connect them with the customer support team. If they accept, call transfer_support. If they decline, call transition_to_close_hardship. Only if they themselves name a date or an amount, record the promise with the steps below.
- "I already paid" (this past-due amount): take no promise, call transition_to_close_paid.
- "This debt is not mine", "I never had this product", or the product was closed or paid off in the past: do not argue, take no promise, call transition_to_close_dispute.
- A request for a new payment plan or lower instalments: do not describe any plan. Call transfer_restructuring.
- A request for a human: ask once whether you can help first. If they insist, call transfer_general.
- If they say a second time that they do not want to talk: call transition_to_close_refused.

HOW TO GET THE PROMISE
1. Ask for the full past-due amount {{past_due_text}} first. Never ask "how much can you pay?". You propose every amount.
2. If they say the full amount is too much: offer the floor {{floor_text}}, once, say that the rest stays overdue, and ask when they can pay it. Do not attach a date to this offer. From then on never propose the full amount again: every later offer uses the floor. If they refuse the floor amount, that is a flat refusal (step 6). A no to a date is not a refusal of the amount.
3. If they propose an amount from {{floor_text}} up to {{past_due_text}}, accept it. Below {{floor_text}}: say it cannot be recorded and offer the floor once. If they do not accept the floor, that is a flat refusal.
4. Dates: look up every date in the DATES list and do what it says. If they ask for a date after the deadline, say the latest date you can record is {{deadline_text}} and offer it. If they refuse the deadline, that is a flat refusal.
5. A vague period ("next week", "end of the month", "when my salary comes"): ask once for the exact day. If they still give none, propose the deadline {{deadline_text}}.
6. A flat refusal (a no to paying today with no date and no amount, a refused offer, or a non-answer) uses one persuasion attempt:
   - Attempt 1: if the customer has said at any point that the full amount is too much, propose the floor {{floor_text}} on {{attempt1_text}}. Otherwise propose the full amount {{past_due_text}} on {{attempt1_text}}.
   - Attempt 2, only when 2 attempts are allowed: propose the floor {{floor_text}} on the deadline {{deadline_text}}.
   - When the allowed attempts are used up and they still refuse, call transition_to_close_refused. Never repeat an offer they already refused.
   Whenever you propose the floor, say that the rest stays overdue.
   A date or an amount the customer proposes is never a refusal: handle it with steps 2 to 5.
7. When the amount and the date are agreed: read back the product, the amount and the date (weekday, day and month), then ask "Do you confirm?". Call create_promise only after a clear yes. If they change the date or the amount, check it again and read it back again.
8. A recorded promise cannot be changed or cancelled in this call; they can change it in the mobile app.

DATES (every date the customer may name, and what to do)
{{calendar_text}}

"This <weekday>" is in the current week. "Next <weekday>" is in the following calendar week:
{{weekday_text}}"""

# ---------------------------------------------------------------- nodes

def route_xfers():
    out = []
    for q, node in (("support", "close_xfer_support"), ("restructuring", "close_xfer_restructuring"), ("general", "close_xfer_general")):
        out.append(go(node, f"Transferred to {q}", grp(eq(f"xfer_{q}_state", "done"),
                                                       eq(f"transfer_{'general' if q == 'general' else q}_response.data.ok", "true"))))
    return out

nodes = {}
nodes["setup"] = code_node("setup", FACTS_CODE, "opening")
nodes["opening"] = conv("opening", OPENING_TASK, on_enter={"type": "tts", "text": OPENING_LINE},
                        extraction=[line_status], transitions=opening_routes() + [always("opening_retry")], first_only=True)
nodes["opening_retry"] = conv("opening_retry", RETRY_TASK, extraction=[line_status],
                              transitions=opening_routes() + [always("close_unclear")], first_only=True)
nodes["security"] = conv(
    "security", SECURITY_TASK,
    on_enter={"type": "tts", "text": "Thank you, {{title}} {{last_name}}. Before I continue, I need to ask you two security questions. What is your date of birth?"},
    first_only=True,
    tools=[verify_identity, transfer_general],
    transitions=[
        go("load_account", "Both security answers verified", grp(eq("id_state", "verified"),
           eq("verify_identity_response.data.all_verified", "true"), eq("verify_identity_response.data.all_verified", "True"))),
        go("close_failed", "Three wrong answers", grp(eq("id_state", "failed"))),
        go("close_xfer_general", "Transferred to a human", grp(eq("xfer_general_state", "done"))),
        tool_tr("close_declined", "The customer declined the security questions twice, or said twice they do not want to talk"),
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
                         "url": {"type": "string", "default": f"{BASE}/get_account"},
                         "method": {"type": "string", "default": "POST"},
                         "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                         "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
    "response_mapping": [{"path": "data.products", "variable": "products"}],
    "transitions": [always("account_facts")],
}
nodes["account_facts"] = code_node("account_facts", FACTS_CODE, "close_account_error",
                                   transitions=[go("negotiate", "Account facts ready", grp(eq("account_state", "ok")))])
nodes["negotiate"] = conv(
    "negotiate", NEGOTIATE_TASK,
    on_enter={"type": "tts", "text": "{{debt_statement}}"}, first_only=True,
    tools=[create_promise, transfer_support, transfer_restructuring, transfer_general],
    transitions=[
        go("close_promise", "The promise was recorded", grp(eq("promise_state", "recorded"))),
        go("close_service_error", "The promise service failed twice", grp(eq("promise_state", "failed_twice"),
           {"variable": "create_promise_failure_count", "operator": "greater_than", "operand": 1})),
    ] + route_xfers() + [
        tool_tr("close_paid", "The customer says they already paid this past-due amount"),
        tool_tr("close_dispute", "The customer says the debt or product is not theirs, or it was closed or paid off in the past"),
        tool_tr("close_hardship", "A customer with illness, a death in the family or job loss declined the support team"),
        tool_tr("close_refused", "The persuasion attempts are used up and the customer still refuses, or said twice they do not want to talk"),
        tool_tr("close_service_error", "create_promise failed twice and nothing was recorded"),
    ],
    max_turns=40, cap_to="close_refused")
nodes["third_party"] = conv(
    "third_party", THIRD_TASK, first_only=True,
    tools=[schedule_callback],
    transitions=[
        go("close_callback", "The callback is booked", grp(eq("cb_state", "booked"))),
        go("close_no_callback", "Second time outside the window", grp(eq("cb_state", "rejected_twice"))),
        tool_tr("close_no_callback", "No callback time inside the allowed window could be agreed after asking once more"),
        tool_tr("close_wrong_number", "The number does not belong to the customer"),
        tool_tr("close_deceased", "The customer has died"),
    ],
    max_turns=20, cap_to="close_no_callback")
for name, (o, r, text) in CLOSES.items():
    nodes[name] = code_node(name, close_code(o, r, text), "goodbye")
nodes["goodbye"] = {
    "name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"},
    "disable_inactivity_monitor": True, "transitions": [],
    "terminal": {"type": "function", "function": {
        "name": "call_closed", "handler": "__function__:end_call",
        "parameters": {"type": "object", "properties": {
            "message_mode": {"type": "string", "default": "custom"},
            "spoken_message": {"type": "string", "default": "{{farewell}}"}}}}},
}

workflow = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "nodes": nodes,
    "global_nodes": {},
    "tools": [close_call],
    "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"},
}

# safety: no double braces inside any code string
for n in nodes.values():
    for a in n.get("pre_actions", []):
        c = a["function"]["parameters"]["properties"].get("code", {}).get("default", "")
        assert "{{" not in c and "}}" not in c, n["name"]
for t in [verify_identity, create_promise, schedule_callback, transfer_support, close_call]:
    for k in ("pre_process_code", "post_process_code"):
        assert "{{" not in t.get(k, "") and "}}" not in t.get(k, ""), t["function"]["name"]

OUT.write_text(json.dumps(workflow, indent=1))
print("wrote", OUT, len(nodes), "nodes")
