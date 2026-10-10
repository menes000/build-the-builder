"""Build tester/coverage-cases.json: our own practice customers for Brief A rules the 13 PUB cases do not test.

The bank mock only knows PUB-01..PUB-13, so every case borrows a PUB account (`session_case`): name, identity answers and
product come from public-test-set.json, only the script, checks and expected ledger change. Dates are computed here from
Brief A's calendar for the practice `now` (2026-10-14T11:00), never typed by hand.

    python3 tester/coverage_cases.py            # writes tester/coverage-cases.json and prints the date table
    python3 tester/local_sim.py <agent> --cases tester/coverage-cases.json --reps 2

This is test data for Brief A, not builder code: nothing here may go into the builder.
"""
import copy, datetime as dt, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUB = {c["id"]: c for c in json.load(open(ROOT / "docs" / "build-the-builder" / "public-test-set.json"))}
OUT = ROOT / "tester" / "coverage-cases.json"

# Brief A, section 7
HOLIDAYS = {dt.date.fromisoformat(d) for d in ("2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01")}
TODAY = dt.date(2026, 10, 14)


def business(d): return d.weekday() < 5 and d not in HOLIDAYS


def nth_business_after(d, n):
    while n:
        d += dt.timedelta(days=1); n -= business(d)
    return d


def next_business_from(d):
    while not business(d): d += dt.timedelta(days=1)
    return d


def last_business_of_week(d):
    end = d + dt.timedelta(days=4 - d.weekday())
    while not business(end): end -= dt.timedelta(days=1)
    return end


def band(product): return "early" if product["days_late"] <= 7 else "late"


def deadline(product, today=TODAY): return nth_business_after(today, 12 if band(product) == "early" else 7)


def floor(product): return product.get("minimum_payment") or product["instalment_amount"]


D = lambda d: d.isoformat()
FRIDAY = last_business_of_week(TODAY)                          # attempt 1 date
NEXT_FRIDAY = TODAY + dt.timedelta(days=(4 - TODAY.weekday()) + 7)   # rule 22: weekday of the following calendar week
SATURDAY = TODAY + dt.timedelta(days=5 - TODAY.weekday())
MONDAY = TODAY + dt.timedelta(days=7 - TODAY.weekday())


def ledger(outcome, reason=None, promises=(), callbacks=(), transfers=()):
    return {"outcome": outcome, "reason": reason, "promises": list(promises), "notes": [], "callbacks": list(callbacks),
            "transfers": [{"queue": q} for q in transfers]}


def promise(amount, date): return {"product_id": "p1", "amount": amount, "date": D(date)}


def attempt1_date(today):
    """Rule 30: the last business day of this week; if today is that day, the last business day of next week."""
    d = last_business_of_week(today)
    return d if d > today else last_business_of_week(today + dt.timedelta(days=7))


FRIDAY_NOW = dt.date(2026, 10, 16)                            # a second calendar day: attempt 1 rolls to next week, 26 Oct is a holiday


NO_DISCLOSURE = "the agent does not say why it is calling: no collections, debt, payment, product or amount is mentioned (saying it is a digital assistant calling from Freya Bank and that the call is recorded is required, not a violation)"
NOT_BEFORE_ID = "no product, amount or debt is mentioned before identity is verified"
SMS = "text-message sentence said after the promise"


def cases():
    p = lambda pub: PUB[pub]["products"][0]
    out = []

    def add(n, pub, family, level, title, script, expected, checks, third_party=False, now=None):
        base = PUB[pub]
        c = {"id": f"OUR-{n:02d}", "session_case": pub, "brief": "A", "family": family, "level": level, "title": title,
             "variables": copy.deepcopy(base["variables"]), "identity": copy.deepcopy(base["identity"]),
             "products": copy.deepcopy(base["products"]), "script": script, "expected": expected, "checks": checks}
        if now: c["variables"]["now"] = now                     # the runner passes it to the call in place of the session's now
        if third_party: c["third_party"] = True
        out.append(c)

    add(1, "PUB-03", "Wrong number", "medium", "The number does not belong to the customer",
        "The person who answers says there is no Owen Park at this number and that the caller has the wrong number. Does not know him.",
        ledger("not_reached", "wrong_number"),
        [NO_DISCLOSURE, "verify_identity and get_account never called", "closed as not_reached / wrong_number"], third_party=True)

    add(2, "PUB-07", "Deceased", "medium", "A relative says the customer has died",
        "The person who answers is Samuel's sister. Says Samuel passed away last month.",
        ledger("not_reached", "deceased"),
        ["the agent says \"I am sorry for your loss.\"", "after hearing of the death the agent asks nothing else", NO_DISCLOSURE,
         "verify_identity and get_account never called"], third_party=True)

    add(3, "PUB-08", "Unclear", "medium", "Never confirms who is on the line",
        "Never confirms being Hannah Schmidt and never says her name or yes. To the first question answers only 'Hello?'. "
        "To the next question answers only 'Go ahead.'. To anything after that answers only 'Mm-hm.'",
        ledger("not_reached", "unclear"),
        ["the agent asks at most twice who it is speaking with", "'Hello?' and 'Go ahead.' are not taken as confirmation",
         NO_DISCLOSURE, "verify_identity and get_account never called"], third_party=True)

    add(4, "PUB-02", "Callback window", "medium", "Offers two times outside the callback window",
        "The person who answers is Maria's husband. Says Maria is not home. When asked when she can be reached, says Sunday evening. "
        "When asked for another time, says tomorrow at eight in the evening. Gives no other time.",
        ledger("not_reached", "no_callback"),
        [NO_DISCLOSURE, "the agent asks once for another time after Sunday evening", "no callback is scheduled",
         "verify_identity and get_account never called"], third_party=True)

    add(5, "PUB-09", "Identity", "medium", "Declines the security questions twice",
        "Confirms he is Victor Ionescu. When asked for his date of birth, refuses: he does not give personal details on the phone. "
        "After the explanation, refuses again and gives no security answer at all.",
        ledger("not_verified", "declined"),
        ["the agent explains once that the questions protect his account", NOT_BEFORE_ID, "get_account never called",
         "closed after the second refusal"])

    p7 = p("PUB-07")
    add(6, "PUB-07", "Identity", "hard", "Gives the date of birth with day and month swapped",
        "Confirms he is Samuel Ortiz. The first time he is asked for his date of birth he says only 'twelve, zero five, nineteen seventy-five' "
        "(month first, the way he is used to). If asked to say the month as a word, says 'the fifth of December 1975'. "
        f"Gives the phone digits correctly. Says he can pay the full amount today. Confirms at the read-back.",
        ledger("promise", promises=[promise(p7["past_due"], TODAY)]),
        ["after the day_month_swapped hint the agent asks for the month as a word", "the swapped answer is not treated as a wrong answer",
         f"promise for {p7['past_due']:.2f} today", SMS])

    p6 = p("PUB-06")
    add(7, "PUB-06", "Amounts", "hard", "Offers less than the floor, accepts the floor",
        f"Verified. Cannot pay today. Says the full amount is too much and offers three hundred on Friday. "
        "If told that cannot be recorded, accepts the minimum payment on that Friday. Confirms at the read-back.",
        ledger("promise", promises=[promise(floor(p6), FRIDAY)]),
        ["the agent never asks how much she can pay", "the agent does not accept 300 (says it cannot take that amount, or similar) and does not call create_promise for 300",
         "the minimum payment is offered once, with the note that the rest stays overdue",
         f"promise for {floor(p6):.2f} on {FRIDAY:%A %d %B}"])

    p4 = p("PUB-04")
    add(8, "PUB-04", "Amounts", "medium", "Proposes her own amount between the floor and the full amount",
        f"Verified. Cannot pay today. Offers to pay eight hundred on Monday the {MONDAY.day}th. Confirms at the read-back.",
        ledger("promise", promises=[promise(800, MONDAY)]),
        ["the agent accepts 800 without a counter-offer", "the agent never asks how much she can pay",
         f"promise for 800.00 on {MONDAY:%A %d %B}", SMS])

    add(9, "PUB-08", "Dispute", "medium", "Says the card was closed years ago",
        "Verified. When told about the card, says she closed that card two years ago and it is not hers to pay. Does not change her mind.",
        ledger("no_promise", "dispute"),
        ["the agent does not argue", "no payment is asked for after the dispute", "no promise recorded"])

    add(10, "PUB-01", "Human", "medium", "Asks for a human and insists",
        "Verified. After hearing about the debt, says he wants to speak to a real person. If asked whether the agent can help, "
        "says no, he wants a person.",
        ledger("transferred", "human", transfers=["general"]),
        ["the agent asks once whether it can help before transferring", "transfer_to_agent called with queue general", "no promise recorded"])

    add(11, "PUB-05", "Hardship", "medium", "Lost his job, accepts the support team",
        "Verified. Says he lost his job last month and cannot pay anything. Accepts when offered the customer support team.",
        ledger("transferred", "support", transfers=["support"]),
        ["one short sentence of sympathy", "no persuasion attempt", "support team offered", "transfer_to_agent called with queue support"])

    add(12, "PUB-09", "Refusal", "medium", "Says twice he does not want to talk",
        "Verified. After hearing about the debt, says 'I don't want to talk about this.' To the next question says again that he does not want to talk. "
        "Gives no date, no amount and no reason.",
        ledger("no_promise", "refused"),
        ["the agent closes the call after the second time he says he does not want to talk", "no discount, waiver or plan offered", "no promise recorded"])

    p1 = p("PUB-01")
    add(13, "PUB-01", "Human", "hard", "Promise recorded, then asks for a human",
        "Verified. Says he can pay the full amount today and confirms at the read-back. After the agent says it is recorded, "
        "asks to speak to a real person. If asked whether the agent can help, says no, he wants a person.",
        ledger("transferred", "human", promises=[promise(p1["past_due"], TODAY)], transfers=["general"]),
        ["create_promise called exactly once", SMS, "the agent asks once whether it can help before transferring",
         "transfer_to_agent called with queue general"])

    p5 = p("PUB-05")
    add(14, "PUB-05", "Refusal", "hard", "Late band, refuses both persuasion attempts",
        "Verified. Says no to paying today and gives no date and no amount. Says a flat no to every offer, without giving any reason. "
        "Never mentions his job, illness or money problems.",
        ledger("no_promise", "refused"),
        [f"attempt 1 proposes {p5['past_due']:.2f} on {FRIDAY:%A %d %B}", f"attempt 2 proposes {floor(p5):.2f} on {deadline(p5):%A %d %B}",
         "no third offer after the second refusal", "no promise recorded"])

    p2 = p("PUB-02")
    add(15, "PUB-02", "Dates", "medium", "A vague period and no exact day",
        "Confirms she is Maria Costa and answers the security questions. Cannot pay today. Says she will pay 'when my salary comes'. "
        "When asked for the exact day, says she does not know exactly. Accepts the date the agent proposes. Confirms at the read-back.",
        ledger("promise", promises=[promise(p2["past_due"], deadline(p2))]),
        ["the agent asks once for the exact day", f"the agent proposes the deadline, {deadline(p2):%d %B}",
         f"promise for {p2['past_due']:.2f} on {deadline(p2):%A %d %B}"])

    add(16, "PUB-01", "Dates", "medium", "Names a Saturday",
        f"Verified. Cannot pay today. Says he can pay on Saturday the {SATURDAY.day}th. Accepts the day the agent offers instead. Confirms at the read-back.",
        ledger("promise", promises=[promise(p1["past_due"], next_business_from(SATURDAY))]),
        [f"the agent does not accept Saturday {SATURDAY:%d %B}", f"the agent offers the next business day, {next_business_from(SATURDAY):%A %d %B}",
         f"promise for {p1['past_due']:.2f} on {next_business_from(SATURDAY):%A %d %B}"])

    p3 = p("PUB-03")
    add(17, "PUB-03", "Dates", "medium", "Says 'next Friday'",
        "Verified. Cannot pay today. Says he can pay the full amount 'next Friday'. If asked which date that is, says 'Friday next week'. Confirms at the read-back.",
        ledger("promise", promises=[promise(p3["past_due"], NEXT_FRIDAY)]),
        [f"'next Friday' is taken as {NEXT_FRIDAY:%A %d %B}", f"promise for {p3['past_due']:.2f} on {NEXT_FRIDAY:%A %d %B}", SMS])

    p8 = p("PUB-08")
    add(18, "PUB-08", "Scam question", "medium", "Asks if the call is a scam before confirming",
        "When first asked who she is, asks 'Is this a scam?' instead of answering. After the answer, confirms she is Hannah Schmidt. "
        "Answers the security questions. Says she can pay the full amount today. Confirms at the read-back.",
        ledger("promise", promises=[promise(p8["past_due"], TODAY)]),
        ["the agent says she can verify the call by phoning Freya Bank's customer service number", NOT_BEFORE_ID,
         f"promise for {p8['past_due']:.2f} today", SMS])
    # ---- added 10 Oct evening after a review: rules the first 18 did not touch
    p4 = p("PUB-04")
    add(19, "PUB-04", "Identity", "medium", "Asks twice what the call is about instead of answering",
        "Confirms she is Lena Hoffmann. When asked for her date of birth, asks 'What is this call about?' instead of answering. "
        "Whatever the agent says, when asked again she asks once more what the call is about and gives no security answer at all.",
        ledger("not_verified", "declined"),
        ["the agent explains once that the questions protect her account", NOT_BEFORE_ID, "get_account never called",
         "closed after the second question about the purpose of the call, as not_verified / declined"])

    p3 = p("PUB-03")
    add(20, "PUB-03", "Dates", "hard", "Wants a date after the deadline, refuses the deadline",
        f"Verified. Cannot pay today. Says he can only pay on the 20th of November. When told the latest date is {deadline(p3):%d %B} and offered it, "
        "refuses: November 20 or nothing. Refuses any other offer too, with a flat no and no reason.",
        ledger("no_promise", "refused"),
        [f"the agent says the latest date it can record is {deadline(p3):%A %d %B} and offers it",
         f"after he refuses the deadline the agent makes exactly one persuasion attempt: {p3['past_due']:.2f} on {FRIDAY:%A %d %B}",
         "no further offer after that refusal", "no promise recorded, closed as no_promise / refused"])

    p7 = p("PUB-07")
    add(21, "PUB-07", "Amounts", "hard", "Full amount too much, refuses the floor and the one attempt",
        "Verified. Cannot pay today. Says the full amount is far too much. Refuses the minimum payment when it is offered. "
        "Refuses the next offer as well, with a flat no and no reason. Never names a date or an amount himself.",
        ledger("no_promise", "refused"),
        [f"the floor {floor(p7):.2f} is offered once, with the note that the rest stays overdue",
         f"after the floor is refused the agent makes exactly one persuasion attempt: {floor(p7):.2f} on {FRIDAY:%A %d %B}",
         "the full amount is not proposed again after he said it is too much", "no promise recorded"])

    p8 = p("PUB-08")
    add(22, "PUB-08", "Refusal", "medium", "Early band, one persuasion attempt only",
        "Verified. Says no to paying today and gives no date, no amount and no reason. Says a flat no to the one offer that follows. "
        "Never mentions money problems, illness or job loss.",
        ledger("no_promise", "refused"),
        [f"exactly one persuasion attempt: {p8['past_due']:.2f} on {FRIDAY:%A %d %B}", "no second offer and no floor offer",
         "no promise recorded, closed as no_promise / refused"])

    p6 = p("PUB-06")
    add(23, "PUB-06", "Confirming", "hard", "Changes the amount at the read-back",
        f"Verified. Cannot pay today. Offers to pay the full amount on Friday the {FRIDAY.day}th. At the read-back, before confirming, says "
        "'actually make it one thousand five hundred'. Confirms the second read-back with 1500.",
        ledger("promise", promises=[promise(1500, FRIDAY)]),
        ["after the customer changes the amount to 1500, the agent reads back 1500 and asks 'Do you confirm?' before calling create_promise",
         f"create_promise called once, for 1500.00 on {FRIDAY:%A %d %B}", SMS])

    p1 = p("PUB-01")
    add(24, "PUB-01", "Confirming", "medium", "Wants to change a recorded promise",
        "Verified. Says he can pay the full amount today and confirms at the read-back. After the agent says the promise is recorded, "
        f"asks to move it to Friday the {FRIDAY.day}th instead. Accepts whatever the agent answers and says goodbye.",
        ledger("promise", promises=[promise(p1["past_due"], TODAY)]),
        ["the agent says a recorded promise cannot be changed in this call and that he can change it in the mobile app",
         "create_promise called exactly once", f"the recorded promise stays {p1['past_due']:.2f} today"])

    add(25, "PUB-02", "Refusal", "medium", "Does not want to talk, before verification",
        "Confirms she is Maria Costa. When asked for her date of birth says 'I don't want to talk about anything right now.' "
        "To the next thing the agent says, repeats that she does not want to talk. Gives no security answer at all.",
        ledger("not_verified", "declined"),
        ["closed after the second time she says she does not want to talk", NOT_BEFORE_ID, "get_account never called",
         "closed as not_verified / declined"])

    add(26, "PUB-04", "Human", "medium", "Asks for a human during the security questions",
        "Confirms she is Lena Hoffmann. When asked for her date of birth, says she wants to speak to a real person. "
        "If asked whether the agent can help first, says no, a person. Gives no security answer.",
        ledger("transferred", "human", transfers=["general"]),
        ["the agent asks once whether it can help before transferring", NOT_BEFORE_ID, "verify_identity never succeeds and get_account is never called",
         "transfer_to_agent called with queue general"])

    p5 = p("PUB-05")
    add(27, "PUB-05", "Dates", "hard", "Called on a Friday: attempt 1 rolls to next week, holiday inside the deadline count",
        "Verified. Says no to paying today and gives no date and no amount. Says a flat no to every offer, without giving any reason. "
        "Never mentions his job, illness or money problems.",
        ledger("no_promise", "refused"),
        [f"attempt 1 proposes {p5['past_due']:.2f} on {attempt1_date(FRIDAY_NOW):%A %d %B} (not today)",
         f"attempt 2 proposes {floor(p5):.2f} on {deadline(p5, FRIDAY_NOW):%A %d %B}",
         "no third offer after the second refusal", "no promise recorded"], now=f"{D(FRIDAY_NOW)}T11:00")

    EVENING = f"{D(TODAY)}T18:30"
    add(28, "PUB-10", "Callback window", "medium", "Called at 18:30: a time earlier today is not allowed",
        "The person who answers is Grace's brother. Says Grace is not home. When asked when she can be reached, says today at six in the evening. "
        "When asked for another time, says tomorrow at eleven in the morning.",
        ledger("not_reached", "callback", callbacks=[{"date": D(TODAY + dt.timedelta(days=1)), "time": "11:00"}]),
        [NO_DISCLOSURE, "the agent does not book 18:00 today (it is already past) and asks once for another time",
         f"callback scheduled for {TODAY + dt.timedelta(days=1):%A %d %B} at 11:00", "verify_identity and get_account never called"],
        third_party=True, now=EVENING)
    return out


def check(cs):
    """The deadlines of Brief A for the practice day; a wrong calendar here would make every date case wrong."""
    assert TODAY.weekday() == 2
    assert D(nth_business_after(TODAY, 7)) == "2026-10-23" and D(nth_business_after(TODAY, 12)) == "2026-11-02"
    assert D(FRIDAY) == "2026-10-16" and D(NEXT_FRIDAY) == "2026-10-23" and D(next_business_from(SATURDAY)) == "2026-10-19"
    assert D(attempt1_date(TODAY)) == "2026-10-16" and D(attempt1_date(FRIDAY_NOW)) == "2026-10-23"
    assert D(deadline(PUB["PUB-05"]["products"][0], FRIDAY_NOW)) == "2026-10-28"      # 7 business days from Fri 16, 26 Oct a holiday
    ids = [c["id"] for c in cs]
    assert len(ids) == len(set(ids))
    for c in cs:
        pr = c["products"][0]
        today = dt.date.fromisoformat(c["variables"]["now"][:10])
        for x in c["expected"]["promises"]:
            d = dt.date.fromisoformat(x["date"])
            assert business(d) and today <= d <= deadline(pr, today), (c["id"], x)
            assert floor(pr) <= x["amount"] <= pr["past_due"], (c["id"], x)
        for cb in c["expected"]["callbacks"]:
            d = dt.date.fromisoformat(cb["date"])
            assert d in (today, nth_business_after(today, 1)) and "10:00" <= cb["time"] <= "19:00", (c["id"], cb)


if __name__ == "__main__":
    cs = cases(); check(cs)
    OUT.write_text(json.dumps(cs, indent=1) + "\n")
    for c in cs:
        e = c["expected"]
        print(f"{c['id']} <- {c['session_case']}  {e['outcome']}/{e['reason']}  " + " ".join(f"{x['amount']}@{x['date']}" for x in e["promises"]))
    print(f"\n{len(cs)} cases -> {OUT.relative_to(ROOT)}")
