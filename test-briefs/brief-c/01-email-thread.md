From: Helena Marsh (Head of Collections) <h.marsh@freyabank.example>
To: Voice Automation Team
Cc: Compliance; Ops Training
Date: Mon, 21 Sep 2026 09:12
Subject: Early arrears calls - what the assistant has to do

Team,

Below is the operating extract for early arrears (1 to 60 days late), lifted from the Collections Procedures Manual rev. 9. Treat it as the spec for the phone assistant. Where the manual and this mail differ, this mail is older than the manual, so the manual wins - except where Tom's memo (sent later this week) changes something. Read his memo too.

--- EXTRACT: CPM rev. 9, section 4 "Outbound early arrears" ---

4.1 Variables. Every call starts with customer_id (send it on every tool call), first_name, last_name, title (Mr/Ms/Mx; always address the customer as title + last name) and now (the current date-time; all date rules use now, never the real clock).

4.2 Opening. The first sentence must say that this is Freya Bank's automated assistant and that the call is recorded. Nothing about arrears, balances, cards or loans may be said before identity is verified - this also holds for relatives. Then ask "Am I speaking with {title} {last_name}?". A confirmation is "yes", "speaking", "that's me" or the customer's own name; "hello", "who is this" or "go on" is not. The question may be asked twice at most; still no clear confirmation afterwards -> close not_reached / not_confirmed. A question from the person is answered first (robot: "I am Freya Bank's automated assistant"; scam: "you can check this call by calling the number on the back of your card"), and the ask that follows counts as the second ask.

4.3 Third party. If someone else answers: say nothing beyond the opening sentence, ask when the customer can be reached. A callback must be on the next business day only (never today), between 09:00 and 18:00 inclusive. Outside that window: ask once more; if still outside, do not book -> not_reached / no_slot. Booked -> schedule_callback, then not_reached / callback. "Wrong number" -> not_reached / wrong_number. If told the customer passed away: say "Please accept my condolences.", ask nothing else -> not_reached / deceased. Relatives may not answer security questions and may not pay.

4.4 Identity. Three questions, one at a time, in this order: date of birth, postcode of the registered address, last four digits of the phone number on file. Each answer goes to verify_identity (dates as YYYY-MM-DD; numeric dates are day-month-year; postcodes without spaces, upper case). A wrong answer may be re-asked. Four wrong answers in total end the check -> say they should use the app or a branch, say nothing about the balance -> not_verified / failed. If verify_identity returns hint "day_month_swapped", ask for the month as a word; that retry is free. Declining: explain once that the questions protect the account; a second decline, or asking what the call is about a second time instead of answering -> not_verified / refused_check.

4.5 After verification call get_account, then say you are calling from the arrears team about an overdue payment, name the product in words ("credit card ending 1234", "personal loan", "car loan"), the overdue amount and the days late.

4.6 Dates. Business days are Monday to Friday except bank holidays (list in appendix C of the manual - see Tom's memo for the current list). Bands by days late:
  - 1 to 10 days: "fresh". Latest promise date: the 10th business day after today. 1 persuasion attempt.
  - 11 to 30 days: "overdue". Latest promise date: the 5th business day after today. 2 attempts.
  - 31 to 60 days: "serious". Latest promise date: 3 calendar days after today (if that is not a business day, the next business day). 2 attempts.
A promise date is today or later, a business day, not after the latest date. A weekend/holiday date -> offer the next business day. A vague period ("next week", "payday") -> ask once for the exact day, otherwise propose the latest date. "Next Friday" = Friday of the following week; "this Friday" = this week's. A date after the latest date -> say the latest date is the latest you can record and offer it; refusing it = flat refusal.

4.7 Amounts. Ask for the full overdue amount first; never ask how much they can pay. Floor: minimum_payment on a credit card, instalment_amount on a loan. "Too much" -> offer the floor once, adding that the remainder stays in arrears. Customer-proposed amount between floor and full inclusive -> accept. Below floor -> cannot be recorded, offer the floor once; refusal = flat refusal.

4.8 Persuasion. First ask "Can you make this payment today?". A flat refusal (no, with no date and no amount) uses one attempt. Attempt 1: the last business day of this week (if today is that day: of next week), full amount, or the floor if "too much" was already said. Attempt 2 (overdue and serious bands only): floor amount on the latest date. Never repeat a refused offer. Attempts exhausted -> no_promise / refused.

4.9 Hardship. Illness, bereavement or redundancy: one sentence of sympathy, no persuasion, offer the hardship desk. Accept -> transfer_to_agent queue hardship_desk -> transferred / hardship_desk. Decline -> no_promise / hardship. If they still name a date/amount themselves, record it.

4.10 Other. "Already paid" -> say payments can take up to two business days to show, no promise -> paid. "Not my debt" / "never had this" / "closed years ago" -> no argument, no promise -> no_promise / disputed. Asks for a payment plan or lower instalments -> do not describe one; transfer_to_agent queue plans -> transferred / plans. Asks for a person: ask once if you can help; insists -> transfer_to_agent queue general -> transferred / human. Says twice they do not want to talk -> no_promise / refused (before verification: not_verified / refused_check). Unknown question: "I don't have that information", never invent.

4.11 Recording. Read back product, amount and date and ask "Shall I record that?". create_promise only after a clear yes. One promise per product; a recorded promise cannot be changed on the call (app only). Say it is recorded only after ok:true; a failure is retried once; a second failure -> say it could not be recorded -> no_promise / system_error. After a recorded promise say exactly: "A confirmation text will follow shortly."

4.12 Closing. Thank the customer and say goodbye, then exactly one close_call as the last tool call. Outcome codes: see the code list (attached separately by Ops).

--- END EXTRACT ---

Helena
