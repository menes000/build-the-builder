"""Python snippets that run INSIDE Freya (code nodes and tool hooks), generated from a CallSpec.

Rules for every snippet (kit docs/tools-and-code.md):
  - never raise: everything inside try/except
  - no '{{' or '}}' anywhere in the source
  - read and write only through `vars`; hooks get `config` (request) or `result` (response)
  - route on strings, never on Python booleans
"""
from __future__ import annotations

import json

from ..extract.callspec import CallSpec


def _lit(x) -> str:
    """A Python expression for x with no double braces anywhere in the source.

    Nested dicts/lists are emitted as json.loads('<indented json>') because a nested literal could end in '}}'.
    """
    s = repr(x)
    if "{{" in s or "}}" in s:
        s = "json.loads(" + repr(json.dumps(x, indent=1)) + ")"
    assert "{{" not in s and "}}" not in s, "literal would contain double braces"
    return s


# ----------------------------------------------------------------------------- date / account facts

def facts_code(spec: CallSpec) -> str:
    bands = [
        {"name": b.name, "lo": b.days_late_min, "hi": b.days_late_max, "bd": b.deadline_business_days_after_today,
         "cd": b.deadline_calendar_days_after_today, "attempts": b.persuasion_attempts, "rule": b.deadline_rule}
        for b in spec.dates.bands
    ]
    ptypes = {p.type: {"floor": p.floor_field, "label": p.spoken_label, "pct": p.floor_percent, "whole": p.floor_round_up_to_whole} for p in spec.products}
    cb = spec.third_party.callback
    params = {
        "HOL": sorted(set(spec.dates.holidays)),
        "WEEKEND": list(spec.dates.weekend_days),
        "BANDS": bands,
        "PTYPES": ptypes,
        "CB_FROM": cb.time_from, "CB_TO": cb.time_to,
        "CB_TODAY": cb.allow_today, "CB_NBD": cb.allow_next_business_day, "CB_LATER": cb.must_be_later_than_now,
        "CB_DAYS": max(1, int(cb.max_business_days_ahead or 1)), "CB_CAL": bool(cb.calendar_days), "CB_SAT": bool(cb.saturday_allowed),
        "CLOSE_BY_FIRST": bool(spec.multi_product.closing_by_first_product),
        "TODAY_Q": (spec.amounts.today_question or "").strip(), "TODAY_Q_ALL": (spec.multi_product.today_question_all or "").strip(),
        "WEEKEND_OFFER": spec.dates.weekend_named_offer,
        "MULTI": spec.multi_product.enabled,
        "PER_PRODUCT_ATT1": bool(spec.multi_product.per_product_question_is_attempt1),
        "DEBT_RULE": spec.debt_statement_rule,
        "DEBT_INTRO": (spec.debt_intro_sentence or "").strip(),
        "PF": (spec.field_map or {}).get("product") or {},
        "PRODUCTS_KEY": ((spec.field_map or {}).get("resp", {}).get("get_account") or {}).get("products", "products"),
        "FIRST_QUESTION": spec.identity.questions[0].ask if spec.identity.questions else "",
        "ATT1_KIND": spec.persuasion.attempt1_date_kind,
        "ATT1_N": int(spec.persuasion.attempt1_business_days or 0),
        "GREETINGS": dict(sorted((spec.opening.greetings or {}).items())) or ({"00:00": "Good morning", "12:00": "Good afternoon", "18:00": "Good evening"} if "{greeting}" in spec.opening.first_sentence else {}),
        "FLOOR_TEXT_MODE": spec.amounts.floor_mode == "text",
        "ATT1_TEXT_MODE": spec.persuasion.attempt1_mode == "text" or spec.persuasion.attempt1_date_kind == "other",
        "CB_TEXT_MODE": cb.day_mode == "text",
        "FLOOR_RULE": spec.amounts.floor_rule, "ATT1_RULE": spec.persuasion.attempt1_date_rule, "CB_RULE": cb.day_rule,
        "DEFAULT_OUTCOME": [spec.opening.unclear_close.outcome, spec.opening.unclear_close.reason],
        "VERIFIED_DEFAULT": [spec.persuasion.refused_close.outcome, spec.persuasion.refused_close.reason],
    }
    # params are emitted one per line so no '}}' can appear
    header = "import json\n" + "\n".join(f"{k} = {_lit(v)}" for k, v in params.items())
    body = r'''
import datetime, json, re, math
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
ONE = datetime.timedelta(days=1)
HOLS = set(HOL)
def isbd(d):
    return d.weekday() not in WEEKEND and d.isoformat() not in HOLS
def say(d):
    return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year)
def tag(d):
    return say(d) + ' (' + d.isoformat() + ')'
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
    for i in range(6, -1, -1):
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
def pf(p, name):
    return p.get(PF.get(name, name), p.get(name))
def find_products():
    for k in ['products', 'load_account_response.data.' + PRODUCTS_KEY, 'get_account_response.data.' + PRODUCTS_KEY]:
        v = as_list(vars.get(k))
        if v:
            return v
    items = dict()
    for k in list(vars.keys()):
        m = re.search(PRODUCTS_KEY + r'\.(\d+)\.(\w+)$', str(k))
        if m:
            items.setdefault(int(m.group(1)), dict())[m.group(2)] = vars.get(k)
    return [items[i] for i in sorted(items)]
def band_for(dl):
    for b in BANDS:
        if b['lo'] <= dl <= b['hi']:
            return b
    return BANDS[-1] if BANDS else None
try:
    try:
        nowdt = datetime.datetime.fromisoformat(str(vars.get('now') or '').strip()[:16])
    except Exception:
        nowdt = datetime.datetime.now()
    today = nowdt.date()
    now_hm = nowdt.strftime('%H:%M')
    vars['today_iso'] = today.isoformat()
    vars['now_hm'] = now_hm
    if GREETINGS:
        g = ''
        for start in sorted(GREETINGS):
            if now_hm >= start:
                g = GREETINGS[start]
        vars['greeting'] = g or GREETINGS[sorted(GREETINGS)[0]]
    # a safe default outcome so close_call never needs a model-filled value (decide_outcome overrides it)
    if not vars.get('outcome'):
        vars['outcome'] = DEFAULT_OUTCOME[0]
        vars['reason'] = DEFAULT_OUTCOME[1]
    vars['today_text'] = tag(today) + ', time ' + now_hm
    if not vars.get('next_question'):
        vars['next_question'] = FIRST_QUESTION
    vars['tomorrow_text'] = tag(today + ONE) + (' (a business day)' if isbd(today + ONE) else ' (not a business day)')
    # callback window
    cb = []
    cbd = []
    if CB_TODAY and (not CB_LATER or now_hm < CB_TO):
        start = CB_FROM if now_hm < CB_FROM or not CB_LATER else 'after ' + now_hm
        cb.append('today, ' + tag(today) + ', from ' + start + ' until ' + CB_TO)
        cbd.append(today.isoformat())
    if CB_NBD:
        if CB_CAL:
            for k in range(1, CB_DAYS + 1):
                dd = today + datetime.timedelta(days=k)
                ok = isbd(dd) or (CB_SAT and dd.weekday() == 5 and dd.isoformat() not in HOLS)
                if ok:
                    cb.append(tag(dd) + ', from ' + CB_FROM + ' until ' + CB_TO)
                    cbd.append(dd.isoformat())
        else:
            for k in range(1, CB_DAYS + 1):
                nbd = nth_bd(today, k)
                cb.append(tag(nbd) + ', from ' + CB_FROM + ' until ' + CB_TO)
                cbd.append(nbd.isoformat())
    if CB_TEXT_MODE:
        cb = ['the days this rule allows: ' + CB_RULE + ' (today is ' + tag(today) + '), from ' + CB_FROM + ' until ' + CB_TO]
        cbd = []
    vars['callback_text'] = ' or '.join(cb)
    vars['cb_dates'] = ','.join(cbd)
    # this / next weekday table
    monday = today - datetime.timedelta(days=today.weekday())
    lines = []
    for i in range(7):
        a = monday + datetime.timedelta(days=i)
        b = a + datetime.timedelta(days=7)
        lines.append('- this ' + WD[i] + ' = ' + say(a) + ('' if a >= today else ' (already past)') + '; next ' + WD[i] + ' = ' + say(b))
    vars['weekday_text'] = '\n'.join(lines)
    # attempt-1 date: last business day of this week, or of next week if that is today or past
    a1 = last_bd_of_week(monday)
    if a1 is None or a1 <= today:
        a1 = last_bd_of_week(monday + datetime.timedelta(days=7))
    prods = find_products()
    facts = []
    if prods:
        for i, p in enumerate(prods):
            typ = str(pf(p, 'type') or '')
            pt = PTYPES.get(typ) or dict()
            past = float(pf(p, 'past_due') or 0)
            dl = int(float(pf(p, 'days_late') or 0))
            floor = float(pf(p, pt.get('floor') or '') or 0) if pt else 0.0
            if pt.get('pct'):
                base = past if (not pt.get('floor') or pt.get('floor') == 'past_due') else float(pf(p, pt.get('floor')) or 0)
                if not base:
                    base = past
                x = base * float(pt['pct']) / 100.0
                floor = float(math.ceil(x)) if pt.get('whole') else math.ceil(x * 100 - 1e-9) / 100.0
            if not floor:
                for fk in ('minimum_payment', 'instalment_amount'):
                    if pf(p, fk):
                        floor = float(pf(p, fk) or 0)
                        break
            if not floor:
                floor = round(past, 2)
            label = (pt.get('label') or typ.replace('_', ' ')).replace('{card_last4}', str(pf(p, 'card_last4') or ''))
            b = band_for(dl) or dict()
            if b.get('bd') is not None:
                deadline = nth_bd(today, int(b['bd']))
            elif b.get('cd') is not None:
                deadline = today + datetime.timedelta(days=int(b['cd']))
                if not isbd(deadline):
                    deadline = next_bd(deadline)
            else:
                deadline = nth_bd(today, 10)
            if ATT1_KIND == 'next_business_day':
                att1 = next_bd(today + ONE)
            elif ATT1_KIND == 'deadline':
                att1 = deadline
            elif ATT1_KIND == 'today':
                att1 = today if isbd(today) else next_bd(today)
            elif ATT1_KIND == 'business_days_after_today' and ATT1_N > 0:
                att1 = nth_bd(today, ATT1_N)
            else:
                att1 = a1
            att1 = att1 if att1 <= deadline else deadline
            if FLOOR_TEXT_MODE:
                floor = 0.0
            valid = []
            d = today
            while d <= deadline:
                if isbd(d):
                    valid.append(d.isoformat())
                d = d + ONE
            facts.append(dict(pid=str(pf(p, 'product_id') or ('p' + str(i + 1))), label=label, past=round(past, 2),
                              days_late=dl, band=str(b.get('name') or ''), attempts=int(b.get('attempts') or 1),
                              deadline=deadline.isoformat(), floor=round(floor, 2), valid=valid, att1=att1.isoformat()))
        vars['n_products'] = len(facts)
        vars['product_ids'] = ','.join(f['pid'] for f in facts)
        vars['facts_json'] = json.dumps(facts)
        vars['promises_json'] = '[]'
        vars['notes_json'] = '[]'
        vars['all_products_done'] = 'no'
        # calendar: every date up to the latest deadline, with its status per product
        maxdl = max(datetime.date.fromisoformat(f['deadline']) for f in facts)
        cal = []
        d = today
        end = max(maxdl + datetime.timedelta(days=10), today + datetime.timedelta(days=28))
        while d <= end:
            parts = []
            for f in facts:
                dl_d = datetime.date.fromisoformat(f['deadline'])
                who = (' for ' + f['label']) if len(facts) > 1 else ''
                if d > dl_d:
                    parts.append('after the deadline' + who + ', not allowed, offer ' + say(dl_d))
                elif isbd(d):
                    parts.append('allowed' + who + (' (today)' if d == today else ''))
                else:
                    kind = 'a bank holiday' if d.isoformat() in HOLS else 'a weekend day'
                    if WEEKEND_OFFER == 'both':
                        pv = d - ONE
                        while not isbd(pv):
                            pv = pv - ONE
                        nx = min(next_bd(d), dl_d)
                        if pv >= today and pv <= dl_d:
                            parts.append(kind + ', not allowed, offer the last business day before it, ' + say(pv) + ', or the next business day, ' + say(nx) + ', and let the customer choose')
                        else:
                            parts.append(kind + ', not allowed, offer the next business day ' + say(nx))
                    elif WEEKEND_OFFER == 'previous_business_day':
                        pv = d - ONE
                        while not isbd(pv):
                            pv = pv - ONE
                        if pv >= today and pv <= dl_d:
                            parts.append(kind + ', not allowed, offer the last business day before it, ' + say(pv))
                        else:
                            parts.append(kind + ', not allowed, offer the next business day ' + say(min(next_bd(d), dl_d)))
                    else:
                        parts.append(kind + ', not allowed, offer the next business day ' + say(next_bd(d)))
            cal.append('- ' + tag(d) + ': ' + '; '.join(parts) + '.')
            d = d + ONE
        vars['calendar_text'] = '\n'.join(cal)
        # per-product offer facts for the prompt
        ol = []
        for f in facts:
            dl_t = tag(datetime.date.fromisoformat(f['deadline']))
            a1_t = ('the attempt-1 date from this rule: ' + ATT1_RULE + ' (never after the deadline ' + dl_t + ')') if ATT1_TEXT_MODE else tag(datetime.date.fromisoformat(f['att1']))
            ol.append('- ' + f['label'] + ' (product_id ' + f['pid'] + '): full past-due amount ' + money(f['past'])
                      + ', ' + str(f['days_late']) + ' days late, band ' + f['band'] + ', floor ' + (('work it out from this rule: ' + FLOOR_RULE) if FLOOR_TEXT_MODE else money(f['floor']))
                      + ', deadline ' + dl_t + '.')
            plan = '  Refusal plan for ' + f['label'] + ' (the note_refusal tool tells you which attempt you are on; use ONLY after a flat refusal; a date or amount the customer proposes is handled by the DATES list and the amount rules instead; exactly ' + str(f['attempts']) + ' persuasion attempt' + ('s' if f['attempts'] != 1 else '') + ', then stop' + ('; do NOT ask again whether they can pay today, that was asked once for all products' if MULTI else '') + '):'
            if MULTI and len(facts) > 1 and PER_PRODUCT_ATT1:
                plan += '\n    open this product with exactly this question, which IS attempt 1 (never ask about today for this product): "For your ' + f['label'] + ', the past-due amount is ' + money(f['past']) + '. Can you pay it on ' + a1_t + '?"'
            else:
                plan += '\n    attempt 1 -> propose ' + money(f['past']) + ' (or the floor' + ('' if FLOOR_TEXT_MODE else ' ' + money(f['floor'])) + ' if they already said the amount is too much) on ' + a1_t + '.'
            if f['attempts'] >= 2:
                plan += '\n    attempt 2 -> propose the floor' + ('' if FLOOR_TEXT_MODE else ' ' + money(f['floor'])) + ' on the deadline ' + dl_t + ', and say the rest stays overdue.'
            for k in range(3, f['attempts'] + 1):
                plan += '\n    attempt ' + str(k) + ' -> propose the floor' + ('' if FLOOR_TEXT_MODE else ' ' + money(f['floor'])) + ' on the deadline ' + dl_t + '.'
            plan += '\n    after attempt ' + str(f['attempts']) + ' is refused -> stop proposing' + (', call add_note with reason refused for this product' if (MULTI and len(facts) > 1) else ', call transition_to_close_refused') + '.'
            ol.append(plan)
        vars['offers_text'] = '\n'.join(ol)
        f0 = facts[0]
        # NOTE: never write a variable named like a model-filled tool field (product_id, amount, date, reason, field, answer, time):
        # the engine would bake it and hide the parameter from the model.
        vars['product_label'] = f0['label']
        vars['past_due_text'] = money(f0['past'])
        vars['floor_text'] = ('the floor from this rule: ' + FLOOR_RULE) if FLOOR_TEXT_MODE else money(f0['floor'])
        vars['days_late'] = f0['days_late']
        vars['attempts'] = f0['attempts']
        vars['deadline_text'] = tag(datetime.date.fromisoformat(f0['deadline']))
        vars['attempt1_text'] = ('the date this rule gives: ' + ATT1_RULE) if ATT1_TEXT_MODE else tag(datetime.date.fromisoformat(f0['att1']))
        # the debt statement, spoken as the first line after verification
        sents = []
        for f in facts:
            sents.append('On your ' + f['label'] + ' the past-due amount is ' + money(f['past']) + ', and the payment is '
                         + str(f['days_late']) + (' day' if f['days_late'] == 1 else ' days') + ' late.')
        if len(facts) > 1:
            q = TODAY_Q_ALL or 'Can you pay all of them today?'
        else:
            q = TODAY_Q or 'Can you make this payment today?'
        if '{' in q:
            total = sum(float(f['past']) for f in facts)
            tmr = next_bd(today + ONE)
            def fill(m):
                k = m.group(1).lower()
                if 'tomorrow' in k:
                    return say(tmr)
                if 'today' in k:
                    return say(today)
                if 'deadline' in k or 'latest' in k:
                    return say(datetime.date.fromisoformat(facts[0]['deadline']))
                if 'total' in k or 'amount' in k or 'sum' in k or 'past' in k or 'full' in k:
                    return money(total)
                return m.group(0)
            q = re.sub(r'\{([^}]*)\}', fill, q)
        vars['outcome'] = VERIFIED_DEFAULT[0]
        vars['reason'] = VERIFIED_DEFAULT[1]
        intro = DEBT_INTRO if DEBT_INTRO else 'I am calling about an overdue payment.'
        if not intro.endswith('.'):
            intro = intro + '.'
        vars['debt_statement'] = ('Thank you, the security check is complete. ' + intro + ' ' + ' '.join(sents) + ' ' + q)
        vars['account_state'] = 'ok'
    else:
        vars['account_state'] = 'missing'
except Exception as e:
    vars['account_state'] = 'missing'
    vars['facts_error'] = str(e)[:200]
'''
    return header + "\n" + body


# ----------------------------------------------------------------------------- hooks

STRIP_HEADER = "        result.pop('header', None)\n"


def verify_pre(spec: CallSpec) -> str:
    R = ((spec.field_map or {}).get("req", {}).get("verify_identity") or {})
    return "R = " + _lit({k: R.get(k, k) for k in ("field",)}) + r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        vars['last_verify_field'] = str(b.get(R['field']) or '')
except Exception:
    pass
'''


def verify_post(spec: CallSpec) -> str:
    hints = {h.hint: (h.instruction, h.counts_as_wrong) for h in spec.identity.retry_hints}
    qs = [q.field for q in spec.identity.questions]
    asks = {q.field: q.ask for q in spec.identity.questions}
    F = ((spec.field_map or {}).get("resp", {}).get("verify_identity") or {})
    return "import json\nMAXQ = " + _lit(spec.identity.max_wrong_per_question) + "\nMAXT = " + _lit(spec.identity.max_wrong_total) + "\nHINTS = " + _lit(hints) + "\nQS = " + _lit(qs) + "\nASKS = " + _lit(asks) + "\nF = " + _lit({k: F.get(k, k) for k in ("ok", "error", "verified", "all_verified", "wrong_answers_left", "hint")}) + r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        t = lambda x: str(x).lower() == 'true'
        left = d.get(F['wrong_answers_left'])
        try:
            left = int(left)
        except Exception:
            left = None
        err = str(d.get(F['error']) or '').lower()
        hint = str(d.get(F['hint']) or '')
        if t(d.get(F['all_verified'])):
            d['id_state'] = 'verified'
            d['what_to_do_next'] = 'Both security answers are correct.'
        elif hint and hint in HINTS:
            d['id_state'] = 'retry'
            d['what_to_do_next'] = ('This counted as a wrong answer. ' if HINTS[hint][1] else 'This did NOT count as a wrong answer. ') + HINTS[hint][0]
        elif left is not None and left <= 0 and not t(d.get(F['verified'])):
            d['id_state'] = 'failed'
            d['what_to_do_next'] = 'The check has failed: no wrong answers left. Say nothing about the account.'
        elif not t(d.get(F['ok'])) and ('lock' in err or 'attempt' in err or 'fail' in err or 'ended' in err):
            d['id_state'] = 'failed'
            d['what_to_do_next'] = 'The check has failed. Say nothing about the account.'
        elif not t(d.get(F['ok'])):
            d['id_state'] = 'retry'
            d['what_to_do_next'] = 'The answer could not be read and did NOT count as wrong. Ask the customer for the full answer again.'
        elif t(d.get(F['verified'])):
            d['id_state'] = 'next'
            try:
                passed = [str(x) for x in json.loads(str(vars.get('passed_fields') or '[]'))]
            except Exception:
                passed = []
            try:
                fld = str(vars.get('last_verify_field') or '')
                if fld and fld not in passed:
                    passed.append(fld)
                vars['passed_fields'] = json.dumps(passed)
                nxt = [q for q in QS if q not in passed]
                if nxt:
                    vars['next_question'] = ASKS.get(nxt[0], 'the next security question')
            except Exception:
                nxt = []
            d['what_to_do_next'] = 'This answer is correct. Now ask the next security question: ' + (ASKS.get(nxt[0], '') if nxt else '') + ' (order: ' + ', '.join(QS) + ')'
        else:
            # a wrong answer: count it per question and in total; the brief's limits apply even if the bank allows more
            fld = str(vars.get('last_verify_field') or '')
            try:
                per = json.loads(str(vars.get('wrong_by_field') or '{}'))
            except Exception:
                per = {}
            per[fld] = int(per.get(fld) or 0) + 1
            vars['wrong_by_field'] = json.dumps(per)
            total = sum(int(x) for x in per.values())
            if (MAXQ and per[fld] >= int(MAXQ)) or (MAXT and total >= int(MAXT)):
                d['id_state'] = 'failed'
                d['what_to_do_next'] = 'The check has failed: the allowed number of wrong answers is reached. Say nothing about the account.'
            else:
                d['id_state'] = 'retry'
                d['what_to_do_next'] = 'This answer is wrong. Tell the customer it does not match our records and ask the same question again.' + ('' if left is None else ' Wrong answers left: ' + str(left) + '.')
except Exception:
    pass
'''


def promise_pre(spec: CallSpec) -> str:
    R = ((spec.field_map or {}).get("req", {}).get("create_promise") or {})
    return "R = " + _lit({k: R.get(k, k) for k in ("product_id", "amount", "date")}) + "\nFLOOR_TEXT_MODE = " + _lit(spec.amounts.floor_mode == "text") + r'''
import json
try:
    b = config.get('body')
    if isinstance(b, dict):
        facts = []
        try:
            facts = json.loads(str(vars.get('facts_json') or '[]'))
        except Exception:
            facts = []
        pid = str(b.get(R['product_id']) or '').strip()
        if len(facts) == 1:
            pid = facts[0]['pid']
        f = None
        for x in facts:
            if x['pid'] == pid:
                f = x
        b[R['product_id']] = pid
        try:
            vars['last_promise_pid'] = pid
        except Exception:
            pass
        good = f is not None
        dt = str(b.get(R['date']) or '').strip()[:10]
        b[R['date']] = dt
        kind = str(b.get('amount_kind') or '').strip().lower()
        b.pop('amount_kind', None)
        amt = None
        if f is not None and kind == 'full':
            amt = float(f['past'])
        elif f is not None and kind == 'floor' and not FLOOR_TEXT_MODE:
            amt = float(f['floor'])
        else:
            try:
                amt = round(float(str(b.get(R['amount'])).replace(',', '')), 2)
            except Exception:
                amt = None
                good = False
        if amt is not None:
            b[R['amount']] = amt
        if f is not None:
            if dt not in f['valid']:
                good = False
            low = 0.01 if FLOOR_TEXT_MODE else float(f['floor'])
            if amt is not None and (amt < low - 0.001 or amt > float(f['past']) + 0.001):
                good = False
            try:
                done = json.loads(str(vars.get('promises_json') or '[]'))
                if any(str(x.get('pid')) == pid for x in done):
                    good = False
                    vars['promise_duplicate'] = 'yes'
                else:
                    vars['promise_duplicate'] = 'no'
            except Exception:
                pass
        try:
            vars['promise_precheck'] = 'ok' if good else 'rejected'
        except Exception:
            pass
        if not good:
            b[R['date']] = 'REJECTED'
except Exception:
    pass
'''


def promise_post(spec: CallSpec) -> str:
    multi = spec.multi_product.enabled
    F = ((spec.field_map or {}).get("resp", {}).get("create_promise") or {})
    immutable = spec.confirm.promise_immutable_text or "A recorded promise cannot be changed on this call; you can change it in the mobile app."
    return "MULTI = " + _lit(multi) + "\nPROMISE_TRIES = " + _lit(max(1, int(spec.confirm.max_tries_on_failure or 2))) + "\nPROMISE_OUTCOME = " + _lit(spec.closing.promise_outcome) + "\nAFTER_RECORD = " + _lit(spec.confirm.after_record_sentence) + "\nIMMUTABLE = " + _lit(immutable) + "\nF = " + _lit({k: F.get(k, k) for k in ("ok", "error")}) + r'''
import json
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        facts = []
        try:
            facts = json.loads(str(vars.get('facts_json') or '[]'))
        except Exception:
            facts = []
        pid = str(vars.get('last_promise_pid') or vars.get('create_promise_args.product_id') or '')
        if len(facts) == 1:
            pid = facts[0]['pid']
        err = str(d.get(F['error']) or '')
        if str(d.get(F['ok'])).lower() == 'true':
            try:
                done = json.loads(str(vars.get('promises_json') or '[]'))
            except Exception:
                done = []
            done.append(dict(pid=pid))
            vars['promises_json'] = json.dumps(done)
            try:
                vars['outcome'] = PROMISE_OUTCOME
                vars['reason'] = ''
            except Exception:
                pass
            d['promise_state'] = 'recorded'
            d['what_to_do_next'] = 'The promise is recorded.' + ('' if (MULTI and len(facts) > 1) else ' Say nothing more in this turn: the confirmation is spoken for you.')
        elif str(vars.get('promise_duplicate') or '') == 'yes':
            d['promise_state'] = 'duplicate'
            d['error'] = 'this product already has a recorded promise'
            d['what_to_do_next'] = 'NOT recorded: this product already has a recorded promise and it cannot be changed or cancelled on this call. Say exactly: "' + IMMUTABLE + '" Then ask exactly: "Is there anything else?"'
        elif str(vars.get('promise_precheck') or '') == 'rejected' or 'must be' in err or 'REJECTED' in err or 'invalid' in err.lower() or 'already' in err.lower():
            d['promise_state'] = 'rejected'
            d['error'] = 'not allowed by bank rules'
            d['what_to_do_next'] = 'NOT recorded: this product, date or amount breaks the bank rules (allowed dates: business days from today to that product deadline; allowed amounts: floor to full past-due amount; one promise per product). Tell the customer it cannot be accepted and offer a valid option following your rules. Never say it is recorded.'
        else:
            key = 'promise_fail_count_' + pid
            try:
                n = int(vars.get(key) or 0)
            except Exception:
                n = 0
            n = n + 1
            try:
                vars[key] = n
                vars['promise_fail_count'] = n
            except Exception:
                pass
            if n >= PROMISE_TRIES:
                d['promise_state'] = 'failed_twice'
                d['what_to_do_next'] = 'The service failed again. Nothing was recorded for this product.' + (' Call add_note for this product with reason service_error, then continue with the other products or close.' if (MULTI and len(facts) > 1) else ' Tell the customer you could not record it.')
            else:
                d['promise_state'] = 'failed_once'
                d['what_to_do_next'] = 'The service failed and nothing was recorded. Call create_promise again now, once, with exactly the same values. Do not say it is recorded.'
        # all products handled?
        try:
            done = json.loads(str(vars.get('promises_json') or '[]'))
            notes = json.loads(str(vars.get('notes_json') or '[]'))
            handled = set(str(x.get('pid')) for x in done) | set(str(x.get('pid')) for x in notes)
            if facts and all(f['pid'] in handled for f in facts):
                vars['all_products_done'] = 'yes'
                d['all_products_done'] = 'yes'
                d['what_to_do_next'] = str(d.get('what_to_do_next') or '') + (' Every product now has a promise or a note: say goodbye in one sentence and call transition_to_close_done.' if (MULTI and len(facts) > 1) else '')
            else:
                d['all_products_done'] = 'no'
        except Exception:
            pass
except Exception:
    pass
'''


def note_pre(spec: CallSpec, reasons: list[str]) -> str:
    R = ((spec.field_map or {}).get("req", {}).get("add_note") or {})
    return "REASONS = " + _lit(reasons) + "\nR = " + _lit({k: R.get(k, k) for k in ("product_id", "reason")}) + r'''
import json
try:
    b = config.get('body')
    if isinstance(b, dict):
        facts = []
        try:
            facts = json.loads(str(vars.get('facts_json') or '[]'))
        except Exception:
            facts = []
        pid = str(b.get(R['product_id']) or '').strip()
        single = len(facts) == 1
        try:
            vars['note_single'] = 'yes' if single else 'no'
        except Exception:
            pass
        if single:
            pid = facts[0]['pid']
        b[R['product_id']] = pid
        try:
            vars['last_note_pid'] = pid
            vars['last_note_reason'] = str(b.get(R['reason']) or '')
        except Exception:
            pass
        ok = any(x['pid'] == pid for x in facts) and (not REASONS or str(b.get(R['reason'])) in REASONS)
        try:
            done = json.loads(str(vars.get('promises_json') or '[]'))
            if any(str(x.get('pid')) == pid for x in done):
                ok = False
        except Exception:
            pass
        if single:
            ok = False          # a call with one product never writes a note: the bank must not record it
        try:
            vars['note_precheck'] = 'ok' if ok else 'rejected'
        except Exception:
            pass
        if not ok:
            b[R['product_id']] = 'REJECTED'
except Exception:
    pass
'''


def note_post(spec: CallSpec) -> str:
    F = ((spec.field_map or {}).get("resp", {}).get("add_note") or {})
    return "F = " + _lit({k: F.get(k, k) for k in ("ok", "error")}) + r'''
import json
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        pid = str(vars.get('last_note_pid') or vars.get('add_note_args.product_id') or '')
        reason = str(vars.get('last_note_reason') or vars.get('add_note_args.reason') or '')
        facts = []
        try:
            facts = json.loads(str(vars.get('facts_json') or '[]'))
        except Exception:
            facts = []
        if len(facts) == 1:
            pid = facts[0]['pid']
        if str(d.get(F['ok'])).lower() == 'true':
            try:
                notes = json.loads(str(vars.get('notes_json') or '[]'))
            except Exception:
                notes = []
            notes.append(dict(pid=pid, reason=reason))
            vars['notes_json'] = json.dumps(notes)
            d['note_state'] = 'noted'
            d['what_to_do_next'] = 'Noted. Continue with the next product that is not handled yet, or close the call if every product has a promise or a note.'
            try:
                done = json.loads(str(vars.get('promises_json') or '[]'))
                handled = set(str(x.get('pid')) for x in done) | set(str(x.get('pid')) for x in notes)
                if facts and all(f['pid'] in handled for f in facts):
                    vars['all_products_done'] = 'yes'
                    d['all_products_done'] = 'yes'
                    d['what_to_do_next'] = 'Noted. Every product now has a promise or a note: say goodbye in one sentence and call transition_to_close_done.'
                else:
                    d['all_products_done'] = 'no'
            except Exception:
                pass
        elif str(vars.get('note_single') or '') == 'yes':
            d['note_state'] = 'not_needed'
            d.pop(F['error'], None)
            d['what_to_do_next'] = ('No note is written on a call with only one product. Do not call add_note again. '
                                    'Call the transition_to_close_... tool that matches the situation now: '
                                    + (('transition_to_close_' + reason) if reason else 'the matching one') + ' if it exists'
                                    + ' (already paid -> close_paid, not my debt -> close_dispute, attempts used up -> close_refused, '
                                    'difficult circumstances -> close_hardship, the promise service failed -> close_service_error).')
        else:
            d['note_state'] = 'rejected' if str(vars.get('note_precheck') or '') == 'rejected' or d.get(F['error']) else 'failed'
            d['what_to_do_next'] = 'The note was not accepted (unknown product or reason, or that product already has a promise). Use a product_id from the account and a listed reason.'
except Exception:
    pass
'''


def callback_pre(spec: CallSpec) -> str:
    cb = spec.third_party.callback
    R = ((spec.field_map or {}).get("req", {}).get("schedule_callback") or {})
    return "CB_FROM = " + _lit(cb.time_from) + "\nCB_TO = " + _lit(cb.time_to) + "\nCB_LATER = " + _lit(cb.must_be_later_than_now) + "\nR = " + _lit({k: R.get(k, k) for k in ("date", "time")}) + r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        good = True
        dt = str(b.get(R['date']) or '').strip()[:10]
        b[R['date']] = dt
        tm = str(b.get(R['time']) or '').strip()
        parts = tm.replace('.', ':').split(':')
        try:
            hh = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            tm = '%02d:%02d' % (hh, mm)
        except Exception:
            good = False
        b[R['time']] = tm
        dates = [x for x in str(vars.get('cb_dates') or '').split(',') if x]
        if dates and dt not in dates:
            good = False
        if tm < CB_FROM or tm > CB_TO:
            good = False
        if CB_LATER and dt == str(vars.get('today_iso') or '') and tm <= str(vars.get('now_hm') or ''):
            good = False
        try:
            vars['cb_precheck'] = 'ok' if good else 'rejected'
        except Exception:
            pass
        if not good:
            b[R['date']] = 'REJECTED'
except Exception:
    pass
'''


def callback_post(spec: CallSpec) -> str:
    F = ((spec.field_map or {}).get("resp", {}).get("schedule_callback") or {})
    return "F = " + _lit({k: F.get(k, k) for k in ("ok", "error")}) + r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        err = str(d.get(F['error']) or '')
        if str(d.get(F['ok'])).lower() == 'true':
            d['cb_state'] = 'booked'
            d['what_to_do_next'] = 'The callback is booked.'
        elif str(vars.get('cb_precheck') or '') == 'rejected' or 'must be' in err or 'REJECTED' in err or 'invalid' in err.lower():
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
                d['what_to_do_next'] = 'Not booked: outside the allowed window again. Do not schedule anything.'
            else:
                d['cb_state'] = 'rejected'
                d['what_to_do_next'] = 'NOT booked: that day or time is outside the allowed callback window. Say we can only call back within the allowed times and ask once for another time.'
        else:
            d['cb_state'] = 'failed'
            d['what_to_do_next'] = 'The booking service failed. Call schedule_callback once more with the same date and time.'
except Exception:
    pass
'''


def transfer_pre(spec: CallSpec, queues: list[str]) -> str:
    R = ((spec.field_map or {}).get("req", {}).get("transfer_to_agent") or {})
    return "QUEUES = " + _lit(list(queues)) + "\nR = " + _lit({k: R.get(k, k) for k in ("queue",)}) + r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        q = str(b.get(R['queue']) or '').strip()
        if QUEUES and q not in QUEUES:
            low = {x.lower(): x for x in QUEUES}
            q = low.get(q.lower(), q)
        try:
            vars['last_transfer_queue'] = q
            vars['xfer_precheck'] = 'ok' if (not QUEUES or q in QUEUES) else 'rejected'
        except Exception:
            pass
        b[R['queue']] = q
except Exception:
    pass
'''


def transfer_post(spec: CallSpec | None = None) -> str:
    F = (((spec.field_map if spec else None) or {}).get("resp", {}).get("transfer_to_agent") or {})
    return "F = " + _lit({k: F.get(k, k) for k in ("ok", "error")}) + r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        if str(d.get(F['ok'])).lower() == 'true':
            d['xfer_state'] = 'done'
            try:
                vars['transfer_queue'] = str(vars.get('last_transfer_queue') or '')
            except Exception:
                pass
            d['what_to_do_next'] = 'Transferred.'
        else:
            d['xfer_state'] = 'failed'
            d['what_to_do_next'] = 'The transfer failed (unknown queue or service error). Tell the customer you could not transfer the call right now.'
except Exception:
    pass
'''


def close_pre(spec: CallSpec, hangup_map: dict | None = None) -> str:
    """Runs when the call ends. If the customer hung up before a closing node ran (no decision, no promise,
    no transfer), the last known situation (hardship/paid/dispute) picks outcome and reason from the goodbye table."""
    R = ((spec.field_map or {}).get("req", {}).get("close_call") or {})
    return ("NO_REASON = " + _lit(list(spec.closing.outcomes_without_reason)) + "\nR = " + _lit({k: R.get(k, k) for k in ("outcome", "reason")})
            + "\nHANGUP = " + _lit({k: list(v)[:2] for k, v in (hangup_map or {}).items() if k != 'default'}) + r'''
try:
    b = config.get('body')
    if isinstance(b, dict):
        decided = str(vars.get('outcome_decided') or '') == 'true'
        promised = str(vars.get('promises_json') or '[]').strip() not in ('', '[]') or int(vars.get('create_promise_success_count') or 0) > 0
        if not decided and not promised and not vars.get('transfer_queue'):
            sit = str(vars.get('situation') or '').strip().lower()
            if sit in HANGUP:
                b[R['outcome']] = HANGUP[sit][0]
                b[R['reason']] = HANGUP[sit][1]
                vars['outcome'] = HANGUP[sit][0]
                vars['reason'] = HANGUP[sit][1]
        if b.get(R['outcome']) in NO_REASON or not b.get(R['reason']):
            b.pop(R['reason'], None)
except Exception:
    try:
        b = config.get('body')
        if isinstance(b, dict) and (b.get(R['outcome']) in NO_REASON or not b.get(R['reason'])):
            b.pop(R['reason'], None)
    except Exception:
        pass
''')


# ----------------------------------------------------------------------------- closing

def close_hint_code(outcome: str, reason: str, farewell: str) -> str:
    return ("try:\n"
            f"    vars['hint_outcome'] = {_lit(outcome)}\n"
            f"    vars['hint_reason'] = {_lit(reason)}\n"
            f"    vars['hint_farewell'] = {_lit(farewell)}\n"
            "except Exception:\n"
            "    pass\n")


def close_on_goodbye_code(mapping: dict, var: str = "situation") -> str:
    """Pick the closing hint from a variable (`situation` on goodbye, `transfer_queue` after a transfer).

    mapping: variable value -> (outcome, reason, farewell); key 'default' for anything else.
    """
    return "M = " + _lit(mapping) + "\nV = " + _lit(var) + r'''
try:
    sit = str(vars.get(V) or '').strip().lower()
    o, r, f = M.get(sit) or M.get('default')
    vars['hint_outcome'] = o
    vars['hint_reason'] = r
    vars['hint_farewell'] = f
except Exception:
    try:
        o, r, f = M.get('default')
        vars['hint_outcome'] = o
        vars['hint_reason'] = r
        vars['hint_farewell'] = f
    except Exception:
        pass
'''


def decide_outcome_code(spec: CallSpec, promise_farewell: str, farewells: dict | None = None, promise_farewell_single: str = "") -> str:
    """Final outcome from state. Overrides the hint when a transfer or a promise happened."""
    c = spec.closing
    mp = spec.multi_product
    transfer_reason_by_queue = {}
    transfer_reason_by_queue[spec.special.hardship.offer_queue] = spec.special.hardship.accept_close.reason
    transfer_reason_by_queue[spec.special.restructuring.queue] = spec.special.restructuring.close.reason
    transfer_reason_by_queue[spec.special.human.queue] = spec.special.human.close.reason
    transferred_outcome = spec.special.restructuring.close.outcome
    paid_outcome = spec.special.paid.close.outcome
    no_promise_outcome = spec.persuasion.refused_close.outcome
    params = {
        "PROMISE_OUTCOME": c.promise_outcome, "XFER_OUTCOME": transferred_outcome, "XFER_REASON": transfer_reason_by_queue,
        "PAID_OUTCOME": paid_outcome, "NO_PROMISE_OUTCOME": no_promise_outcome, "MULTI": mp.enabled, "REASON_PRIORITY": list(mp.no_promise_reason_priority or []),
        "CLOSE_BY_FIRST": bool(mp.closing_by_first_product),
        "PROMISE_FAREWELL": promise_farewell, "PROMISE_FAREWELL_SINGLE": promise_farewell_single or promise_farewell, "NAME_TOKEN": "NAME", "FAREWELLS": farewells or {},
    }
    header = "import json\n" + "\n".join(f"{k} = {_lit(v)}" for k, v in params.items())
    return header + r'''
import json
try:
    outcome = str(vars.get('hint_outcome') or NO_PROMISE_OUTCOME)
    reason = str(vars.get('hint_reason') or '')
    farewell = str(vars.get('hint_farewell') or 'Thank you for your time. Goodbye.')
    try:
        promises = json.loads(str(vars.get('promises_json') or '[]'))
    except Exception:
        promises = []
    try:
        notes = json.loads(str(vars.get('notes_json') or '[]'))
    except Exception:
        notes = []
    try:
        pc = int(vars.get('create_promise_success_count') or 0)
    except Exception:
        pc = 0
    if pc > len(promises):
        promises = promises + [dict(pid='?')] * (pc - len(promises))
    q = str(vars.get('transfer_queue') or '')
    if q:
        outcome = XFER_OUTCOME
        reason = XFER_REASON.get(q, q)
        farewell = FAREWELLS.get('xfer_' + q) or farewell
    elif promises:
        outcome = PROMISE_OUTCOME
        reason = ''
        farewell = PROMISE_FAREWELL_SINGLE if str(vars.get('n_products') or '') == '1' else PROMISE_FAREWELL
    elif MULTI and notes:
        if all(str(n.get('reason')) == 'paid' for n in notes):
            outcome = PAID_OUTCOME
            reason = ''
            farewell = FAREWELLS.get('paid') or farewell
        else:
            first = ''
            first_paid = False
            if CLOSE_BY_FIRST:
                try:
                    facts0 = json.loads(str(vars.get('facts_json') or '[]'))
                except Exception:
                    facts0 = []
                pid0 = str(facts0[0].get('pid')) if facts0 else ''
                nn = [n for n in notes if str(n.get('pid')) == pid0] or notes[:1]
                first = str(nn[0].get('reason')) if nn else ''
                if first == 'paid':
                    first_paid = True
            reasons = [str(n.get('reason')) for n in notes if str(n.get('reason')) != 'paid'] if not first else [first]
            for r in REASON_PRIORITY:
                if r in reasons:
                    first = r
                    break
            if not first and reasons:
                first = reasons[0]
            if first_paid:
                outcome = PAID_OUTCOME
                reason = ''
                farewell = FAREWELLS.get('paid') or farewell
            else:
                outcome = NO_PROMISE_OUTCOME
                reason = first
                farewell = FAREWELLS.get('no_promise_' + first) or FAREWELLS.get('no_promise') or farewell
    name = (str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '')).strip()
    vars['outcome'] = outcome
    vars['reason'] = reason
    vars['outcome_decided'] = 'true'
    vars['farewell'] = farewell.replace(NAME_TOKEN, name) if name else farewell.replace(', ' + NAME_TOKEN, '').replace(NAME_TOKEN, '')
except Exception:
    try:
        vars['outcome'] = str(vars.get('hint_outcome') or NO_PROMISE_OUTCOME)
        vars['reason'] = str(vars.get('hint_reason') or '')
        vars['farewell'] = 'Thank you for your time. Goodbye.'
    except Exception:
        pass
'''



# ----------------------------------------------------------------------------- persuasion counter (carrier: get_account)

def refusal_pre(spec: CallSpec) -> str:
    multi = spec.multi_product.enabled
    floor_text = spec.amounts.floor_offer_text
    ps = spec.persuasion
    floor_text_mode = spec.amounts.floor_mode == "text"
    att1_text_mode = ps.attempt1_mode == "text" or ps.attempt1_date_kind == "other"
    known1 = not att1_text_mode and not floor_text_mode
    params = {
        "MULTI": multi, "FLOOR_TEXT": floor_text,
        "OPENING_IS_ATTEMPT1": bool(multi and spec.multi_product.ask_today_for_all_once and spec.multi_product.per_product_question_is_attempt1),
        "KNOWN1": known1, "ATT1_FULL": bool(ps.attempt1_uses_full_amount),
        "KNOWN2": bool(ps.attempt2_uses_floor_on_deadline) and not floor_text_mode,
        "FLOOR_RULE": spec.amounts.floor_rule if floor_text_mode else "", "ATT1_RULE": ps.attempt1_date_rule if att1_text_mode else "",
        "RULES_TEXT": " ".join(ps.attempt_rules) + (" " + ps.attempt1_date_rule if ps.attempt1_date_rule else ""),
    }
    return "import json\n" + "\n".join(f"{k} = {_lit(v)}" for k, v in params.items()) + r'''
import json, datetime
WD = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MO = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
def say(iso):
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
        return WD[d.weekday()] + ' ' + str(d.day) + ' ' + MO[d.month - 1] + ' ' + str(d.year) + ' (' + d.isoformat() + ')'
    except Exception:
        return str(iso)
def money(x):
    try:
        x = round(float(x), 2)
        return str(int(round(x))) if abs(x - round(x)) < 0.005 else '%.2f' % x
    except Exception:
        return str(x)
try:
    b = config.get('body')
    if not isinstance(b, dict):
        b = dict()
    facts = []
    try:
        facts = json.loads(str(vars.get('facts_json') or '[]'))
    except Exception:
        facts = []
    pid = str(b.pop('product_id', '') or '').strip()
    if len(facts) == 1:
        pid = facts[0]['pid']
    tm = str(b.pop('amount_too_much', '') or '').strip().lower() in ('true', '1', 'yes')
    f = None
    for x in facts:
        if x['pid'] == pid:
            f = x
    key = 'attempts_used_' + pid
    # with several products the product's opening question already IS attempt 1 (the 'today?' question was asked once
    # for all); with one product the 'today?' question is not an attempt, so the first refusal starts attempt 1
    start = 1 if (OPENING_IS_ATTEMPT1 and len(facts) > 1) else 0          # one product: the 'today?' question is never an attempt
    try:
        n = int(vars.get(key) or start) + 1
    except Exception:
        n = start + 1
    vars[key] = n
    if f is None:
        instr = 'Unknown product. Use a product_id from ACCOUNT and call note_refusal again.'
        state = 'unknown'
    else:
        allowed = int(f.get('attempts') or 1)
        if n > allowed:
            state = 'exhausted'
            instr = ('Attempts used up for ' + f['label'] + ' (' + str(allowed) + ' allowed). Do NOT propose anything more. '
                     + ('Call add_note with reason refused for product ' + pid + ' and move to the next product.' if (MULTI and len(facts) > 1) else 'Call transition_to_close_refused now.'))
        elif n == 1 and KNOWN1:
            state = 'continue'
            amt = f['floor'] if (tm or not ATT1_FULL) else f['past']
            instr = ('Attempt ' + str(n) + ' of ' + str(allowed) + ' for ' + f['label'] + ': propose ' + money(amt) + ' on ' + say(f['att1']) + '.'
                     + (' ' + FLOOR_TEXT if (tm or not ATT1_FULL) else '') + ' Ask whether they can do that.')
        elif n >= 2 and KNOWN2:
            state = 'continue'
            instr = ('Attempt ' + str(n) + ' of ' + str(allowed) + ' for ' + f['label'] + ': propose the floor ' + money(f['floor']) + ' on the deadline ' + say(f['deadline']) + '. '
                     + FLOOR_TEXT + ' Ask whether they can do that.')
        else:
            state = 'continue'
            instr = ('Attempt ' + str(n) + ' of ' + str(allowed) + ' for ' + f['label'] + '. The bank rule for this attempt: ' + RULES_TEXT
                     + ' Facts: full amount ' + money(f['past']) + ', floor ' + (('from this rule: ' + FLOOR_RULE) if FLOOR_RULE else money(f['floor'])) + ', deadline ' + say(f['deadline']) + ', attempt-1 date ' + (('from this rule: ' + ATT1_RULE) if ATT1_RULE else say(f['att1'])) + '. Make exactly the proposal that rule describes.')
    vars['refusal_instruction'] = instr
    vars['refusal_state'] = state
    vars['refusal_attempt'] = n
    # the model sometimes calls note_refusal twice in one message (one per product); the hooks then run pre, pre, post, post.
    # A queue keeps each answer with its own call: the post-hook takes the oldest entry.
    try:
        q = json.loads(str(vars.get('refusal_queue') or '[]'))
    except Exception:
        q = []
    q.append({'i': instr, 's': state, 'n': n})
    vars['refusal_queue'] = json.dumps(q)
except Exception as e:
    try:
        vars['refusal_instruction'] = 'Continue with your rules.'
        vars['refusal_state'] = 'error'
    except Exception:
        pass
'''


def refusal_post(spec: CallSpec) -> str:
    return r'''
import json
try:
    if isinstance(result, dict):
        result.pop('header', None)
        entry = None
        try:
            q = json.loads(str(vars.get('refusal_queue') or '[]'))
            if q:
                entry = q.pop(0)
                vars['refusal_queue'] = json.dumps(q)
        except Exception:
            entry = None
        if not isinstance(entry, dict):
            entry = {'i': vars.get('refusal_instruction'), 's': vars.get('refusal_state'), 'n': vars.get('refusal_attempt')}
        result['data'] = {
            'ok': True,
            'attempt': entry.get('n'),
            'refusal_state': str(entry.get('s') or 'continue'),
            'what_to_do_next': str(entry.get('i') or 'Continue with your rules.'),
        }
        result['message'] = 'refusal noted'
except Exception:
    pass
'''
