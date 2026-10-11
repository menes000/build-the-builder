"""Practice customers for ANY brief, generated from the builder's CallSpec. No value is typed by hand.

    python3 tester/cases_from_callspec.py <callspec.json> [--accounts public-test-set.json] [--out results/<slot>-cases.json]
                                          [--tag OUR] [--local-bank]

How it works
  1. The CallSpec (what Dora's builder extracted from the brief: holidays, bands, floors, callback window, outcomes, sentences)
     becomes a Rules object. Dates and amounts are computed here in code, never by a model.
  2. ~30 scenario templates (the rule families of a collections call) are filled from Rules: the customer script, the judge
     checks and the expected bank ledger. A template whose rule is missing from the brief is skipped and listed.
  3. Accounts come from a pool (the organisers' practice customers by default). A template says what kind of account it
     needs (band, product type, product count). With --local-bank the pool may be extended: identity fields the brief asks
     for but the pool lacks (e.g. postcode) are added, and a band with no account gets a synthetic one. Those cases carry
     "needs_local_bank": true and run only with `local_sim.py --bank local`.
  4. check(): every expected promise is on a business day inside the deadline, every amount between floor and full,
     every callback inside the window, every outcome in the brief's outcome table. A violation stops the run.

Sunday: build -> out/<slot>.callspec.json -> this -> local_sim.py --agent local --bank local. See ILERLEME.md.
"""
import argparse, copy, datetime as dt, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = lambda d: d.isoformat()
ONE = dt.timedelta(days=1)


# ----------------------------------------------------------------------------- rules from the CallSpec
class Rules:
    def __init__(self, spec):
        self.spec = spec
        d = spec["dates"]
        self.holidays = {dt.date.fromisoformat(x) for x in d.get("holidays") or []}
        self.weekend = set(d.get("weekend_days") or [5, 6])
        self.bands = d["bands"]
        self.products = {p["type"]: p for p in spec.get("products") or []}
        self.cb = spec["third_party"]["callback"]
        self.attempt1_rule = (spec["persuasion"].get("attempt1_date_rule") or " ".join(spec["persuasion"].get("attempt_rules") or [])).lower()
        self.attempt2_floor_on_deadline = bool(spec["persuasion"].get("attempt2_uses_floor_on_deadline", True))
        self.multi = spec.get("multi_product") or {}
        self.identity_fields = [q["field"] for q in spec["identity"]["questions"]]
        self.skipped = []

    # calendar
    def business(self, d): return d.weekday() not in self.weekend and d not in self.holidays
    def next_business(self, d):
        while not self.business(d): d += ONE
        return d
    def nth_business_after(self, d, n):
        while n:
            d += ONE; n -= self.business(d)
        return d
    def last_business_of_week(self, d):
        end = d + dt.timedelta(days=6 - d.weekday())
        while not self.business(end): end -= ONE
        return end

    def band(self, product):
        dl = int(product["days_late"])
        for b in self.bands:
            if int(b["days_late_min"]) <= dl <= int(b["days_late_max"]): return b
        return None

    def deadline(self, product, today):
        b = self.band(product)
        if b is None: return None
        if b.get("deadline_business_days_after_today"): return self.nth_business_after(today, int(b["deadline_business_days_after_today"]))
        if b.get("deadline_calendar_days_after_today"): return self.next_business(today + dt.timedelta(days=int(b["deadline_calendar_days_after_today"])))
        return None

    def attempts(self, product):
        b = self.band(product); return int(b["persuasion_attempts"]) if b else None

    def attempt1_date(self, today):
        """Known rule shapes: 'last business day of this week; if today is that day, (the last business day of) next week'."""
        r = self.attempt1_rule
        if "last business day" in r and "week" in r:
            d = self.last_business_of_week(today)
            if d > today: return d
            return self.last_business_of_week(today + dt.timedelta(days=7)) if "next week" in r else d
        if "next business day" in r: return self.next_business(today + ONE)
        if "deadline" in r or "latest date" in r: return None            # caller must use the deadline
        return "unknown"

    def floor(self, product):
        pt = self.products.get(product["type"])
        if not pt: return None
        v = product.get(pt["floor_field"])
        return float(v) if v is not None else None

    def label(self, product):
        pt = self.products.get(product["type"])
        return (pt["spoken_label"] if pt else product["type"]).format(**{k: v for k, v in product.items() if isinstance(v, (str, int, float))})

    # outcomes and sentences
    def out(self, path):
        o = self.spec
        for k in path.split("."): o = o.get(k) if isinstance(o, dict) else None
        if not isinstance(o, dict) or not o.get("outcome"): return None
        return {"outcome": o["outcome"], "reason": o.get("reason") or None}

    def text(self, path, default=""):
        o = self.spec
        for k in path.split("."): o = o.get(k) if isinstance(o, dict) else None
        return o if isinstance(o, str) and o.strip() else default


def money(x):
    x = round(float(x), 2)
    return str(int(x)) if abs(x - round(x)) < 0.005 else f"{x:.2f}"


def day(d): return f"{d:%A} {d.day} {d:%B}"


# ----------------------------------------------------------------------------- accounts
def load_accounts(path):
    out = []
    for c in json.load(open(path)):
        out.append({"id": c["id"], "variables": copy.deepcopy(c["variables"]), "identity": copy.deepcopy(c.get("identity") or {}),
                    "products": copy.deepcopy(c["products"]), "faults": copy.deepcopy(c.get("faults") or [])})
    return out


SYNTH_IDENTITY = {"postcode": "SW1A1AA", "birth_year": "1985", "company_number": "12345678", "founded_year": "2001", "mother_maiden_name": "KOVACS"}


def complete_identity(acct, rules, local_bank):
    """Add identity fields the brief asks for that the account lacks (only possible with the local bank)."""
    missing = [f for f in rules.identity_fields if f not in acct["identity"]]
    if not missing: return acct, False
    if not local_bank: return None, True
    a = copy.deepcopy(acct)
    for f in missing: a["identity"][f] = SYNTH_IDENTITY.get(f, "4242")
    return a, True


class Pool:
    def __init__(self, accounts, rules, local_bank):
        self.accounts, self.rules, self.local_bank, self.used = accounts, rules, local_bank, {}

    def pick(self, pred, prefer=None, synth=None):
        """First account satisfying pred (least used first); `prefer` names an account id to try first; `synth` builds one."""
        order = sorted(self.accounts, key=lambda a: (self.used.get(a["id"], 0), a["id"]))
        if prefer: order = [a for a in order if a["id"] == prefer] + [a for a in order if a["id"] != prefer]
        for a in order:
            if pred(a):
                a2, added = complete_identity(a, self.rules, self.local_bank)
                if a2 is None: continue
                self.used[a["id"]] = self.used.get(a["id"], 0) + 1
                return a2, added
        if synth and self.local_bank:
            a = synth(copy.deepcopy(order[0])); a["id"] += "-syn"
            a2, _ = complete_identity(a, self.rules, True)
            return a2, True
        return None, False


single = lambda a: len(a["products"]) == 1
def in_band(rules, name): return lambda a: single(a) and (rules.band(a["products"][0]) or {}).get("name") == name
def with_attempts(rules, n): return lambda a: single(a) and rules.attempts(a["products"][0]) == n


# ----------------------------------------------------------------------------- templates
def build(rules, pool, tag="OUR", now_override=None):
    sp = rules.spec
    out, seq = [], [0]
    base_now = None

    def add(family, level, title, acct, script, expected, checks, third_party=False, now=None, needs_local=False):
        seq[0] += 1
        c = {"id": f"{tag}-{seq[0]:02d}", "session_case": acct["id"].replace("-syn", ""), "brief": sp.get("brief_tag", "X"), "family": family, "level": level,
             "title": title, "variables": copy.deepcopy(acct["variables"]), "identity": copy.deepcopy(acct["identity"]),
             "products": copy.deepcopy(acct["products"]), "script": script, "expected": expected, "checks": checks}
        if acct.get("faults"): c["faults"] = acct["faults"]
        if now: c["variables"]["now"] = now
        if third_party: c["third_party"] = True
        if needs_local or acct["id"].endswith("-syn"): c["needs_local_bank"] = True
        out.append(c)

    def ledger(o, promises=(), callbacks=(), transfers=(), notes=()):
        if o is None: return None
        return {"outcome": o["outcome"], "reason": o["reason"], "promises": list(promises), "notes": list(notes), "callbacks": list(callbacks), "transfers": [{"queue": q} for q in transfers]}

    def promise(amount, d, pid="p1"): return {"product_id": pid, "amount": float(amount), "date": D(d)}

    def skip(name, why): rules.skipped.append(f"{name}: {why}")

    def today_of(acct): return dt.date.fromisoformat(acct["variables"]["now"][:10])

    def need(path):
        o = rules.out(path)
        return o

    no_disclosure = ("the agent does not say why it is calling: no collections, debt, payment, product or amount is mentioned "
                     "(saying who is calling and that the call is recorded is required, not a violation)")
    not_before_id = "no product, amount or debt is mentioned before identity is verified"
    sms = rules.text("confirm.after_record_sentence")
    sms_check = f"after the recorded promise the agent says: \"{sms}\"" if sms else "the agent confirms the promise is recorded"
    q1 = sp["identity"]["questions"][0]["field"].replace("_", " ")

    # ---- third party / opening
    o = need("third_party.wrong_number_close")
    a, _ = pool.pick(lambda a: True, prefer="PUB-03")
    if o and a:
        v = a["variables"]
        add("Wrong number", "medium", "The number does not belong to the customer", a,
            f"The person who answers says there is no {v['first_name']} {v['last_name']} at this number and that the caller has the wrong number. Does not know them.",
            ledger(o), [no_disclosure, "verify_identity and get_account never called", f"closed as {o['outcome']} / {o['reason']}"], third_party=True)
    else: skip("wrong number", "no third_party.wrong_number_close")

    o = need("third_party.deceased_close"); sent = rules.text("third_party.deceased_sentence")
    a, _ = pool.pick(lambda a: True, prefer="PUB-07")
    if o and a:
        v = a["variables"]
        add("Deceased", "medium", "A relative says the customer has died", a,
            f"The person who answers is {v['first_name']}'s sister. Says {v['first_name']} passed away last month.",
            ledger(o), ([f"the agent says \"{sent}\""] if sent else ["the agent expresses condolences in one sentence"]) +
            ["after hearing of the death the agent asks nothing else", no_disclosure, "verify_identity and get_account never called"], third_party=True)
    else: skip("deceased", "no third_party.deceased_close")

    o = need("opening.unclear_close"); max_asks = int(sp["opening"].get("max_asks") or 2)
    a, _ = pool.pick(lambda a: True, prefer="PUB-08")
    if o and a:
        v = a["variables"]
        add("Unclear", "medium", "Never confirms who is on the line", a,
            f"Never confirms being {v['first_name']} {v['last_name']} and never says the name or yes. To the first question answers only 'Hello?'. "
            "To the next question answers only 'Go ahead.'. To anything after that answers only 'Mm-hm.'",
            ledger(o), [f"the agent asks at most {max_asks} times who it is speaking with", "'Hello?' and 'Go ahead.' are not taken as confirmation",
                        no_disclosure, "verify_identity and get_account never called"], third_party=True)
    else: skip("unclear", "no opening.unclear_close")

    cb = rules.cb; o_cb, o_nocb = need("third_party.callback_close"), need("third_party.no_callback_close")
    a, _ = pool.pick(lambda a: True, prefer="PUB-02")
    if o_nocb and a:
        v = a["variables"]; today = today_of(a)
        late_time = (dt.datetime.combine(today, dt.time.fromisoformat(cb["time_to"])) + dt.timedelta(minutes=60)).strftime("%H:%M")
        sunday = today + dt.timedelta(days=6 - today.weekday())
        add("Callback window", "medium", "Offers two times outside the callback window", a,
            f"The person who answers is {v['first_name']}'s husband. Says {v['first_name']} is not home. When asked when she can be reached, says {day(sunday)} in the evening. "
            f"When asked for another time, says tomorrow at {late_time}. Gives no other time.",
            ledger(o_nocb), [no_disclosure, "the agent asks once for another time after the first one", "no callback is scheduled", "verify_identity and get_account never called"], third_party=True)
    else: skip("callback outside window", "no third_party.no_callback_close")

    if o_cb and a and cb.get("allow_next_business_day", True):
        today = today_of(a); nbd = rules.next_business(today + ONE)
        t_from = dt.time.fromisoformat(cb["time_from"]); ok_time = (dt.datetime.combine(nbd, t_from) + dt.timedelta(hours=2)).strftime("%H:%M")
        evening_now = (dt.datetime.combine(today, dt.time.fromisoformat(cb["time_to"])) - dt.timedelta(minutes=30))
        earlier = (evening_now - dt.timedelta(minutes=30)).strftime("%H:%M")
        a2, _ = pool.pick(lambda a: True, prefer="PUB-10")
        v = a2["variables"]
        add("Callback window", "medium", f"Called at {evening_now:%H:%M}: a time earlier today is not allowed", a2,
            f"The person who answers is {v['first_name']}'s brother. Says {v['first_name']} is not home. When asked when she can be reached, says today at {earlier}. "
            f"When asked for another time, says {day(nbd)} at {ok_time}.",
            ledger(o_cb, callbacks=[{"date": D(nbd), "time": ok_time}]),
            [no_disclosure, f"the agent does not book {earlier} today (it is already past) and asks once for another time", f"callback scheduled for {day(nbd)} at {ok_time}",
             "verify_identity and get_account never called"], third_party=True, now=f"{D(today)}T{evening_now:%H:%M}")
    else: skip("callback booked", "no callback close or next business day not allowed")

    # ---- identity
    o = need("identity.decline.close"); explain = rules.text("identity.decline.explain_once_text")
    a, _ = pool.pick(lambda a: True, prefer="PUB-09")
    if o and a:
        v = a["variables"]
        add("Identity", "medium", "Declines the security questions twice", a,
            f"Confirms being {v['first_name']} {v['last_name']}. When asked the first security question ({q1}), refuses: does not give personal details on the phone. "
            "After the explanation, refuses again and gives no security answer at all.",
            ledger(o), ["the agent explains once that the questions protect the account", not_before_id, "get_account never called", f"closed after the second refusal, as {o['outcome']} / {o['reason']}"])
        if sp["identity"]["decline"].get("asking_purpose_counts_as_decline", True):
            a2, _ = pool.pick(lambda a: True, prefer="PUB-04"); v = a2["variables"]
            add("Identity", "medium", "Asks twice what the call is about instead of answering", a2,
                f"Confirms being {v['first_name']} {v['last_name']}. When asked the first security question, asks 'What is this call about?' instead of answering. "
                "Whatever the agent says, when asked again asks once more what the call is about and gives no security answer at all.",
                ledger(o), ["the agent explains once that the questions protect the account", not_before_id, "get_account never called",
                            f"closed after the second question about the purpose of the call, as {o['outcome']} / {o['reason']}"])
    else: skip("decline", "no identity.decline.close")

    o = need("special.refuses_twice_unverified_close")
    a, _ = pool.pick(lambda a: True, prefer="PUB-02")
    if o and a:
        v = a["variables"]
        add("Refusal", "medium", "Does not want to talk, before verification", a,
            f"Confirms being {v['first_name']} {v['last_name']}. When asked the first security question says 'I don't want to talk about anything right now.' "
            "To the next thing the agent says, repeats that they do not want to talk. Gives no security answer at all.",
            ledger(o), ["closed after the second time the customer says they do not want to talk", not_before_id, "get_account never called", f"closed as {o['outcome']} / {o['reason']}"])
    else: skip("refuses twice unverified", "no special.refuses_twice_unverified_close")

    hr = sp["identity"].get("human_request")
    if hr and hr.get("queue") and hr.get("close"):
        o = {"outcome": hr["close"]["outcome"], "reason": hr["close"].get("reason") or None}
        a, _ = pool.pick(lambda a: True, prefer="PUB-04"); v = a["variables"]
        add("Human", "medium", "Asks for a human during the security questions", a,
            f"Confirms being {v['first_name']} {v['last_name']}. When asked the first security question, says they want to speak to a real person. "
            "If asked whether the agent can help first, says no, a person. Gives no security answer.",
            ledger(o, transfers=[hr["queue"]]), ["the agent asks once whether it can help before transferring", not_before_id, "get_account is never called", f"transfer_to_agent called with queue {hr['queue']}"])
    else: skip("human during identity", "the brief has no human-request rule for the identity stage (identity.human_request empty)")

    hint = next((h for h in sp["identity"].get("retry_hints") or [] if h.get("hint") == "day_month_swapped"), None)
    dob_field = next((q["field"] for q in sp["identity"]["questions"] if "birth" in q["field"] or q["field"] == "dob"), None)
    a, _ = pool.pick(lambda a: single(a) and dob_field in a["identity"], prefer="PUB-07")
    if hint and dob_field and a:
        v, p, today = a["variables"], a["products"][0], today_of(a)
        dob = dt.date.fromisoformat(a["identity"][dob_field])
        if dob.day <= 12 and dob.day != dob.month:
            swapped = f"{dob.month:02d}, {dob.day:02d}, {dob.year}"
            add("Identity", "hard", "Gives the date of birth with day and month swapped", a,
                f"Confirms being {v['first_name']} {v['last_name']}. The first time asked for the date of birth says only '{swapped}' (month first, the way they are used to). "
                f"If asked to say the month as a word, says 'the {dob.day}th of {dob:%B} {dob.year}'. Answers the other security questions correctly. Says they can pay the full amount today. Confirms at the read-back.",
                ledger(need("closing.promise_outcome_obj") or {"outcome": sp["closing"]["promise_outcome"], "reason": None}, promises=[promise(p["past_due"], today)]),
                ["after the day_month_swapped hint the agent asks for the month as a word", "the swapped answer is not treated as a wrong answer", f"promise for {money(p['past_due'])} today ({D(today)})", sms_check])
        else: skip("day/month swapped", "no account whose birthday allows a swap")
    else: skip("day/month swapped", "no day_month_swapped hint or no date-of-birth question")

    # ---- after verification: amounts, dates, persuasion
    po = {"outcome": sp["closing"]["promise_outcome"], "reason": None}
    o_ref = need("persuasion.refused_close")
    floor_text = rules.text("amounts.floor_offer_text", "the rest stays overdue")

    a, _ = pool.pick(lambda a: single(a) and rules.floor(a["products"][0]) and rules.floor(a["products"][0]) < float(a["products"][0]["past_due"]), prefer="PUB-06")
    if a:
        p, today = a["products"][0], today_of(a); fl = rules.floor(p); d1 = rules.attempt1_date(today)
        if isinstance(d1, dt.date) and d1 <= rules.deadline(p, today):
            below = money(max(1, round(fl * 0.5)))
            add("Amounts", "hard", "Offers less than the floor, accepts the floor", a,
                f"Verified. Cannot pay today. Says the full amount is too much and offers {below} on {day(d1)}. If told that amount is not possible, accepts the minimum amount the agent names, on that day. Confirms at the read-back.",
                ledger(po, promises=[promise(fl, d1)]),
                ["the agent never asks how much the customer can pay", f"the agent does not accept {below} and does not call create_promise for {below}",
                 f"the floor {money(fl)} is offered once, with the note that {floor_text.rstrip('.').lower()}", f"promise for {money(fl)} on {day(d1)}"])
        else: skip("below floor", "attempt-1 date rule unknown or past the deadline")
    a, _ = pool.pick(lambda a: single(a) and rules.floor(a["products"][0]) and rules.floor(a["products"][0]) < float(a["products"][0]["past_due"]), prefer="PUB-04")
    if a:
        p, today = a["products"][0], today_of(a); fl, full = rules.floor(p), float(p["past_due"]); mid = round((fl + full) / 2)
        monday = rules.next_business(today + dt.timedelta(days=7 - today.weekday()))
        if monday <= rules.deadline(p, today):
            add("Amounts", "medium", "Proposes their own amount between the floor and the full amount", a,
                f"Verified. Cannot pay today. Offers to pay {money(mid)} on {day(monday)}. Confirms at the read-back.",
                ledger(po, promises=[promise(mid, monday)]), [f"the agent accepts {money(mid)} without a counter-offer", "the agent never asks how much the customer can pay", f"promise for {money(mid)} on {day(monday)}", sms_check])
        else: skip("own amount", "next Monday is past the deadline")

    dis = sp["special"].get("dispute"); o = need("special.dispute.close")
    a, _ = pool.pick(single, prefer="PUB-08")
    if o and a:
        p = a["products"][0]
        add("Dispute", "medium", "Says the product was closed years ago", a,
            f"Verified. When told about the {rules.label(p)}, says they closed that product two years ago and it is not theirs to pay. Does not change their mind.",
            ledger(o), ["the agent does not argue", "no payment is asked for after the dispute", "no promise recorded", f"closed as {o['outcome']} / {o['reason']}"])
    else: skip("dispute", "no special.dispute.close")

    hu = sp["special"].get("human"); 
    if hu and hu.get("queue") and hu.get("close"):
        o = {"outcome": hu["close"]["outcome"], "reason": hu["close"].get("reason") or None}
        a, _ = pool.pick(single, prefer="PUB-01")
        add("Human", "medium", "Asks for a human and insists", a,
            "Verified. After hearing about the debt, says they want to speak to a real person. If asked whether the agent can help, says no, they want a person.",
            ledger(o, transfers=[hu["queue"]]), ["the agent asks once whether it can help before transferring", f"transfer_to_agent called with queue {hu['queue']}", "no promise recorded"])
        a, _ = pool.pick(single, prefer="PUB-01"); p, today = a["products"][0], today_of(a)
        rule = rules.text("closing.transfer_after_promise_rule")
        if rule:
            add("Human", "hard", "Promise recorded, then asks for a human", a,
                "Verified. Says they can pay the full amount today and confirms at the read-back. After the agent says it is recorded, asks to speak to a real person. If asked whether the agent can help, says no, they want a person.",
                ledger(o, promises=[promise(p["past_due"], today)], transfers=[hu["queue"]]),
                ["create_promise called exactly once (today, " + D(today) + ")", sms_check, "the agent asks at most once whether it can help before transferring", f"transfer_to_agent called with queue {hu['queue']}"])
    else: skip("human", "no special.human rule")

    hs = sp["special"].get("hardship")
    if hs and hs.get("offer_queue") and hs.get("accept_close"):
        o = {"outcome": hs["accept_close"]["outcome"], "reason": hs["accept_close"].get("reason") or None}
        a, _ = pool.pick(single, prefer="PUB-05"); trig = (hs.get("triggers") or ["job loss"])[-1]
        add("Hardship", "medium", f"{trig.capitalize()}, accepts the support team", a,
            f"Verified. Says they are going through {trig} (lost the job last month) and cannot pay anything. Accepts when offered the {hs['offer_queue'].replace('_', ' ')} team.",
            ledger(o, transfers=[hs["offer_queue"]]), ["one short sentence of sympathy", "after the hardship is mentioned the agent proposes no payment amount or date (the 'can you pay today?' question asked before the hardship came up is required and fine)", "the support team is offered", f"transfer_to_agent called with queue {hs['offer_queue']}"])
    else: skip("hardship", "no special.hardship rule")

    o = need("special.refuses_twice_verified_close")
    a, _ = pool.pick(single, prefer="PUB-09")
    if o and a:
        add("Refusal", "medium", "Says twice they do not want to talk", a,
            "Verified. After hearing about the debt, says 'I don't want to talk about this.' To the next question says again that they do not want to talk. Gives no date, no amount and no reason.",
            ledger(o), ["the agent closes the call after the second time the customer says they do not want to talk", "no discount, waiver or instalment plan is offered (proposing a date for the normal amount is not a plan)", "no promise recorded"])
    else: skip("refuses twice verified", "no rule")

    # persuasion attempts per band
    for b in rules.bands:
        n = int(b["persuasion_attempts"])
        a, _ = pool.pick(lambda a, nm=b["name"]: in_band(rules, nm)(a) and rules.floor(a["products"][0]), prefer={"early": "PUB-08", "late": "PUB-05"}.get(b["name"]),
                         synth=lambda x, b=b: (x.__setitem__("products", [dict(x["products"][0], days_late=int(b["days_late_min"]) + 1)]) or x))
        if not a or not o_ref: skip(f"refusal band {b['name']}", "no account in this band" if o_ref else "no refused_close"); continue
        p, today = a["products"][0], today_of(a); fl, full = rules.floor(p), float(p["past_due"]); d1 = rules.attempt1_date(today); dl = rules.deadline(p, today)
        if not isinstance(d1, dt.date): skip(f"refusal band {b['name']}", "attempt-1 date rule unknown"); continue
        checks = [f"persuasion attempt 1 (the first offer after the customer refuses to pay today) proposes {money(full)} on {day(d1)}"]
        if n >= 2 and rules.attempt2_floor_on_deadline: checks.append(f"persuasion attempt 2 proposes {money(fl)} on {day(dl)}")
        checks += [f"exactly {n} offer(s) in total after the refusal to pay today; no offer after attempt {n}", "no promise recorded", f"closed as {o_ref['outcome']} / {o_ref['reason']}"]
        add("Refusal", "hard", f"{b['name']} band: refuses today and all {n} persuasion attempt(s)", a,
            "Verified. Says no to paying today and gives no date, no amount and no reason. Says a flat no to every offer, without giving any reason. Never mentions money problems, illness or job loss.",
            ledger(o_ref), checks)

    # dates
    a, _ = pool.pick(lambda a: single(a) and rules.attempts(a["products"][0]) and rules.attempts(a["products"][0]) >= 1, prefer="PUB-02")
    if a and "deadline" in rules.text("dates.vague_period_rule").lower() or (a and "latest" in rules.text("dates.vague_period_rule").lower()):
        p, today = a["products"][0], today_of(a); dl = rules.deadline(p, today)
        add("Dates", "medium", "A vague period and no exact day", a,
            "Verified. Cannot pay today. Says they will pay 'when my salary comes'. When asked for the exact day, says they do not know exactly. Accepts the date the agent proposes. Confirms at the read-back.",
            ledger(po, promises=[promise(p["past_due"], dl)]), ["the agent asks once for the exact day", f"the agent proposes the deadline, {day(dl)}", f"promise for {money(p['past_due'])} on {day(dl)}"])
    else: skip("vague period", "no vague_period_rule that proposes the deadline")

    a, _ = pool.pick(single, prefer="PUB-01")
    if a and sp["dates"].get("offer_next_business_day", True):
        p, today = a["products"][0], today_of(a)
        sat = today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7); nb = rules.next_business(sat)
        if nb <= rules.deadline(p, today):
            add("Dates", "medium", "Names a non-business day", a,
                f"Verified. Cannot pay today. Says they can pay on {day(sat)}. Accepts the day the agent offers instead. Confirms at the read-back.",
                ledger(po, promises=[promise(p["past_due"], nb)]), [f"the agent does not accept {day(sat)}", f"the agent offers the next business day, {day(nb)}", f"promise for {money(p['past_due'])} on {day(nb)}"])
    a, _ = pool.pick(single, prefer="PUB-03")
    if a and "following" in rules.text("dates.next_weekday_rule").lower():
        p, today = a["products"][0], today_of(a); nf = today + dt.timedelta(days=(4 - today.weekday()) + 7)
        if rules.business(nf) and nf <= rules.deadline(p, today):
            add("Dates", "medium", "Says 'next Friday'", a,
                "Verified. Cannot pay today. Says they can pay the full amount 'next Friday'. If asked which date that is, says 'Friday next week'. Confirms at the read-back.",
                ledger(po, promises=[promise(p["past_due"], nf)]), [f"'next Friday' is taken as {day(nf)}", f"promise for {money(p['past_due'])} on {day(nf)}", sms_check])
        else: skip("next Friday", "next Friday is a holiday or past the deadline for every account")

    a, _ = pool.pick(lambda a: with_attempts(rules, 1)(a) and rules.floor(a["products"][0]), prefer="PUB-03")
    if a and o_ref and "deadline" in rules.text("dates.after_deadline_rule").lower() or (a and o_ref and "latest" in rules.text("dates.after_deadline_rule").lower()):
        p, today = a["products"][0], today_of(a); dl = rules.deadline(p, today); d1 = rules.attempt1_date(today); far = dl + dt.timedelta(days=18)
        if isinstance(d1, dt.date):
            add("Dates", "hard", "Wants a date after the deadline, refuses the deadline", a,
                f"Verified. When asked to pay today, answers in one sentence that they cannot pay today and the only day they can pay is {day(far)} (gives that date right away, never a bare 'no'). When told the latest date is {day(dl)} and offered it, refuses: that day or nothing. Refuses any other offer too, with a flat no and no reason.",
                ledger(o_ref), [f"the agent says the latest date it can record is {day(dl)} and offers it",
                                f"after the refusal of the deadline the agent makes exactly one persuasion attempt: {money(p['past_due'])} on {day(d1)}", "no further offer after that refusal", f"no promise recorded, closed as {o_ref['outcome']} / {o_ref['reason']}"])

    a, _ = pool.pick(lambda a: with_attempts(rules, 1)(a) and rules.floor(a["products"][0]) and rules.floor(a["products"][0]) < float(a["products"][0]["past_due"]), prefer="PUB-07")
    if a and o_ref:
        p, today = a["products"][0], today_of(a); fl = rules.floor(p); d1 = rules.attempt1_date(today)
        if isinstance(d1, dt.date):
            add("Amounts", "hard", "Full amount too much, refuses the floor and the one attempt", a,
                "Verified. Cannot pay today. Says the full amount is far too much. Refuses the minimum payment when it is offered. Refuses the next offer as well, with a flat no and no reason. Never names a date or an amount.",
                ledger(o_ref), [f"the floor {money(fl)} is offered once, with the note that {floor_text.rstrip('.').lower()}", f"after the floor is refused the agent makes exactly one persuasion attempt: {money(fl)} on {day(d1)}",
                                "the full amount is not proposed again after the customer said it is too much", "no promise recorded"])

    # confirming
    a, _ = pool.pick(lambda a: single(a) and rules.floor(a["products"][0]) and rules.floor(a["products"][0]) < float(a["products"][0]["past_due"]), prefer="PUB-06")
    if a and sp["confirm"].get("recheck_if_changed", True):
        p, today = a["products"][0], today_of(a); d1 = rules.attempt1_date(today); fl, full = rules.floor(p), float(p["past_due"]); new = round((fl + full) / 2)
        if isinstance(d1, dt.date) and d1 <= rules.deadline(p, today):
            add("Confirming", "hard", "Changes the amount at the read-back", a,
                f"Verified. Cannot pay today. Offers to pay the full amount on {day(d1)}. At the read-back, before confirming, says 'actually make it {money(new)}'. Confirms the second read-back with {money(new)}.",
                ledger(po, promises=[promise(new, d1)]), [f"after the customer changes the amount to {money(new)}, the agent reads back {money(new)} and asks for confirmation again before calling create_promise",
                                                          f"create_promise called once, for {money(new)} on {day(d1)}", sms_check])
    a, _ = pool.pick(single, prefer="PUB-01"); imm = rules.text("confirm.promise_immutable_text")
    if a and sp["confirm"].get("one_promise_per_product", True) and imm:
        p, today = a["products"][0], today_of(a); d1 = rules.attempt1_date(today)
        add("Confirming", "medium", "Wants to change a recorded promise", a,
            f"Verified. Says they can pay the full amount today and confirms at the read-back. After the agent says the promise is recorded, asks to move it to {day(d1) if isinstance(d1, dt.date) else 'next week'} instead. Accepts whatever the agent answers and says goodbye.",
            ledger(po, promises=[promise(p["past_due"], today)]), [f"the agent says a recorded promise cannot be changed in this call (the brief's sentence: \"{imm}\")", "create_promise called exactly once", f"the recorded promise stays {money(p['past_due'])} on today's date ({D(today)})"])

    scam = rules.text("opening.scam_answer")
    a, _ = pool.pick(single, prefer="PUB-08")
    if a and scam:
        p, today = a["products"][0], today_of(a); v = a["variables"]
        add("Scam question", "medium", "Asks if the call is a scam before confirming", a,
            f"When first asked who they are, asks 'Is this a scam?' instead of answering. After the answer, confirms being {v['first_name']} {v['last_name']}. Answers the security questions. Says they can pay the full amount today. Confirms at the read-back.",
            ledger(po, promises=[promise(p["past_due"], today)]), [f"the agent answers the scam question as the brief says (\"{scam}\")", not_before_id, f"promise for {money(p['past_due'])} on today's date ({D(today)})", sms_check])

    # a second calendar day: today is the last business day of its week (attempt 1 rolls over), holidays inside the deadline count
    a, _ = pool.pick(lambda a: with_attempts(rules, 2)(a) and rules.floor(a["products"][0]), prefer="PUB-05")
    if a and o_ref and rules.attempt2_floor_on_deadline:
        base = today_of(a); fri = base
        while not (rules.business(fri) and rules.last_business_of_week(fri) == fri): fri += ONE
        p = a["products"][0]; fl, full = rules.floor(p), float(p["past_due"]); d1 = rules.attempt1_date(fri); dl = rules.deadline(p, fri)
        if isinstance(d1, dt.date):
            add("Dates", "hard", f"Called on {day(fri)}: attempt 1 rolls to next week", a,
                "Verified. Says no to paying today and gives no date and no amount. Says a flat no to every offer, without giving any reason. Never mentions money problems, illness or job loss.",
                ledger(o_ref), [f"attempt 1 proposes {money(full)} on {day(d1)} (not today)", f"attempt 2 proposes {money(fl)} on {day(dl)}", "no third offer after the second refusal", "no promise recorded"],
                now=f"{D(fri)}T{base_now or '11:00'}")

    # paid
    pd = sp["special"].get("paid"); o = need("special.paid.close")
    a, _ = pool.pick(single, prefer="PUB-03")
    if o and a:
        add("Paid", "medium", "Says the payment was already made", a,
            "Verified. When told about the late payment, says they already paid it yesterday through the app. Does not want to promise anything.",
            ledger(o), ["no promise is asked for or recorded after the customer says they paid", (f"the agent says: {pd.get('say')}" if pd.get("say") else "the agent explains payments take time to appear"), f"closed as {o['outcome']}" + (f" / {o['reason']}" if o['reason'] else "")])

    rs = sp["special"].get("restructuring")
    if rs and rs.get("queue") and rs.get("close"):
        o = {"outcome": rs["close"]["outcome"], "reason": rs["close"].get("reason") or None}
        a, _ = pool.pick(single, prefer="PUB-09")
        add("Restructuring", "medium", "Asks for a payment plan", a,
            "Verified. When asked to pay, says they cannot and asks for a new payment plan with lower instalments. Accepts being connected to the team that handles that.",
            ledger(o, transfers=[rs["queue"]]), ["the agent does not describe the terms of any plan or instalment option (saying it will connect the customer to the team that handles plans is fine)", f"transfer_to_agent called with queue {rs['queue']}", "no promise recorded"])

    # ---- multi product
    if rules.multi.get("enabled"):
        build_multi(rules, pool, add, ledger, promise, skip, today_of, po, o_ref, sms_check)
    return out


def build_multi(rules, pool, add, ledger, promise, skip, today_of, po, o_ref, sms_check):
    sp, m = rules.spec, rules.multi
    reasons = m.get("note_reasons") or []
    multi = lambda a: len(a["products"]) >= 2
    a, _ = pool.pick(multi, prefer="PUB-12")
    if not a: skip("multi product", "no account with 2+ products"); return
    today = today_of(a); ps = a["products"]
    d1 = rules.attempt1_date(today)
    if isinstance(d1, dt.date) and all(d1 <= rules.deadline(p, today) for p in ps) and "refused" in reasons:
        add("Multi", "hard", "Promises the first product, refuses the rest", a,
            f"Verified. Cannot pay all of them today. Will pay the {rules.label(ps[0])} in full on {day(d1)}. Flatly refuses to pay anything on the other products, whatever is offered, without giving a reason.",
            ledger(po, promises=[promise(ps[0]["past_due"], d1, "p1")], notes=[{"product_id": f"p{i+2}", "reason": "refused"} for i in range(len(ps) - 1)]),
            ["every late product is stated before any ask", f"exactly one promise, on the {rules.label(ps[0])}", "one 'refused' note for each product without a promise", "persuasion attempts are made per product, in get_account order"])
    a, _ = pool.pick(multi, prefer="PUB-13")
    if a and m.get("one_date_for_all_rule"):
        today = today_of(a); ps = a["products"]
        dls = [rules.deadline(p, today) for p in ps]
        far = max(dls); near_i = dls.index(min(dls))
        if far > min(dls) and rules.business(far):
            exp = [promise(p["past_due"], min(far, dls[i]), f"p{i+1}") for i, p in enumerate(ps)]
            add("Multi", "hard", "One date for everything, past one product's deadline", a,
                f"Verified. Cannot pay today. Wants to pay all products in full on {day(far)}. Accepts when told one product has an earlier latest date.",
                ledger(po, promises=exp), [f"the {rules.label(ps[near_i])} is recorded on its own deadline, {day(dls[near_i])}", f"the other product(s) keep {day(far)}", "the read-back names both dates and asks for one confirmation", "one create_promise per product"])
    a, _ = pool.pick(multi, prefer="PUB-11")
    if a and "paid" in reasons and m.get("dispute_or_paid_does_not_end_call", True):
        today = today_of(a); ps = a["products"]
        o_paid = rules.out("special.paid.close")
        exp_notes = [{"product_id": f"p{i+1}", "reason": "paid"} for i in range(len(ps))]
        if o_paid:
            add("Multi", "medium", "Says every product was already paid", a,
                "Verified. For each product, says it was already paid yesterday through the app. Promises nothing.",
                ledger(o_paid, notes=exp_notes), ["no promise recorded", "one 'paid' note per product", f"closed as {o_paid['outcome']}"])
        add("Multi", "hard", "One product already paid, the other promised", a,
            f"Verified. Cannot pay all today. Says the {rules.label(ps[0])} was already paid yesterday. Will pay the {rules.label(ps[1])} in full today. Confirms at the read-back." + (" Flatly refuses the rest." if len(ps) > 2 else ""),
            ledger(po, promises=[promise(ps[1]["past_due"], today, "p2")], notes=[{"product_id": "p1", "reason": "paid"}] + [{"product_id": f"p{i+1}", "reason": "refused"} for i in range(2, len(ps))]),
            ["the 'already paid' claim on one product does not end the call", f"a 'paid' note on the {rules.label(ps[0])}", f"one promise, on the {rules.label(ps[1])}", "one create_promise per promised product"])
    rs = sp["special"].get("restructuring")
    a, _ = pool.pick(multi, prefer="PUB-11")
    if a and rs and rs.get("queue") and "transfer" in (m.get("transfer_rule") or "").lower():
        o = {"outcome": rs["close"]["outcome"], "reason": rs["close"].get("reason") or None}; ps = a["products"]; today = today_of(a)
        single_rb = m.get("single_readback_single_confirmation", True)
        add("Multi", "hard", "Agrees on the first product, then asks for a payment plan before the read-back", a,
            f"Verified. Cannot pay all today. Says they will pay the {rules.label(ps[0])} in full today. When asked about the next product, asks for a new payment plan with lower instalments and insists on being connected, before any read-back or confirmation.",
            ledger(o, promises=[] if single_rb else [promise(ps[0]["past_due"], today, "p1")], transfers=[rs["queue"]]),
            [("a promise agreed but not yet read back and confirmed is NOT recorded: create_promise is never called" if single_rb else "the promise recorded before the request stays"),
             f"transfer_to_agent called with queue {rs['queue']}", "no add_note at all, before or after the transfer", f"closed as {o['outcome']} / {o['reason']}"])
    a, _ = pool.pick(multi, prefer="PUB-12")
    if a and m.get("failed_promise_note_reason"):
        ps, today = a["products"], today_of(a); a = dict(a, faults=[{"tool": "create_promise", "fail_first_n": 2}])
        add("Multi", "hard", "The promise service fails twice on the first product", a,
            f"Verified. Cannot pay all today. Will pay every product in full today. Confirms once at the read-back." ,
            ledger(po, promises=[promise(p["past_due"], today, f"p{i+1}") for i, p in enumerate(ps) if i > 0], notes=[{"product_id": "p1", "reason": m["failed_promise_note_reason"]}]),
            [f"after two failures on the {rules.label(ps[0])} the agent keeps the other promises", f"an add_note with reason {m['failed_promise_note_reason']} for the {rules.label(ps[0])}", f"the agent never claims the {rules.label(ps[0])} promise is recorded"], needs_local=True)


# ----------------------------------------------------------------------------- validation
def check(cases, rules):
    ids = [c["id"] for c in cases]; assert len(ids) == len(set(ids))
    table = {o["outcome"]: set(o.get("reasons") or []) for o in rules.spec["closing"]["outcomes"]}
    for c in cases:
        e = c["expected"]; today = dt.date.fromisoformat(c["variables"]["now"][:10])
        assert e["outcome"] in table, (c["id"], e["outcome"], "not in the outcome table")
        assert (e["reason"] or None) in (table[e["outcome"]] or {None}) or (e["reason"] is None and not table[e["outcome"]]), (c["id"], e)
        prods = {f"p{i+1}": p for i, p in enumerate(c["products"])}
        for x in e["promises"]:
            p = prods[x["product_id"]]; d = dt.date.fromisoformat(x["date"])
            assert rules.business(d) and today <= d <= rules.deadline(p, today), (c["id"], x, "date outside the rules")
            assert (rules.floor(p) or 0) <= x["amount"] <= float(p["past_due"]) + 1e-6, (c["id"], x, "amount outside floor..full")
        for cb in e["callbacks"]:
            d = dt.date.fromisoformat(cb["date"]); allowed = []
            if rules.cb.get("allow_today", True): allowed.append(today)
            if rules.cb.get("allow_next_business_day", True): allowed.append(rules.nth_business_after(today, 1))
            assert d in allowed and rules.cb["time_from"] <= cb["time"] <= rules.cb["time_to"], (c["id"], cb)
        for t in e["transfers"]:
            enum = next((f.get("enum") for tl in rules.spec.get("tools") or [] if tl["name"] == "transfer_to_agent" for f in tl["fields"] if f["name"] == "queue"), None)
            assert not enum or t["queue"] in enum, (c["id"], t, "queue not in the tool API")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callspec"); ap.add_argument("--accounts", default=next((str(p / "public-test-set.json") for p in (ROOT / "kit", ROOT / "docs" / "build-the-builder") if p.exists()), None))
    ap.add_argument("--out"); ap.add_argument("--tag", default="OUR"); ap.add_argument("--brief", default="X", help="brief tag written into each case")
    ap.add_argument("--local-bank", action="store_true", help="allow synthetic identity fields and accounts (run with local_sim.py --bank local)")
    a = ap.parse_args()
    spec = json.load(open(a.callspec)); spec["brief_tag"] = a.brief
    rules = Rules(spec); pool = Pool(load_accounts(a.accounts), rules, a.local_bank)
    cases = build(rules, pool, a.tag); check(cases, rules)
    out = pathlib.Path(a.out or (ROOT / "results" / (pathlib.Path(a.callspec).stem.replace(".callspec", "") + "-cases.json")))
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(cases, indent=1) + "\n")
    for c in cases:
        e = c["expected"]
        print(f"{c['id']} <- {c['session_case']:<7} {e['outcome']}/{e['reason']}  " + " ".join(f"{x['product_id']}:{x['amount']}@{x['date']}" for x in e["promises"]) +
              (" notes=" + ",".join(n['reason'] for n in e['notes']) if e['notes'] else "") + ("  [local bank]" if c.get("needs_local_bank") else "") + f"  | {c['title']}")
    for s in rules.skipped: print("skipped:", s)
    print(f"\n{len(cases)} cases -> {out}")


if __name__ == "__main__":
    main()
