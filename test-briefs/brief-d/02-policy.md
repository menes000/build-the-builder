# Freya Bank — Early Arrears Telephony Standard

Document: EATS v6
Owner: Collections Operations
Effective: 1 June 2026
Applies to: outbound calls to retail customers 1 to 50 days past due on credit cards, personal loans and car loans. Automated and human callers alike.

Where a later written instruction from Collections Operations or Retail Credit differs from this Standard, the later instruction applies.

---

## 1. Call set-up

1.1 Each call starts with: `customer_id` (send it on every tool call), `first_name`, `last_name`, `title` (Mr, Ms or Mx; the customer is always addressed as title + last name) and `now`, the current date and time. Every date rule in this Standard is worked from `now`. The caller never uses the real clock.

1.2 A customer may be behind on one, two or three products at the same time. `get_account` returns them all.

## 2. Opening

2.1 First sentence, without exception: "This is Freya Bank's virtual assistant. This call is recorded for quality and training." Nothing about arrears, an overdue payment, a card or a loan may be said until identity has been verified. This applies to whoever is on the line, including a spouse or relative.

2.2 Then ask: "Am I speaking with {title} {last_name}?"

2.3 "Yes", "speaking", "that's me", the customer's full name or the customer's first name on its own all count as confirmation. "Hello", "go on", "who's calling" and "what is this about" do not. The question may be put twice. If there is still no clear confirmation, close `not_reached` / `unclear`.

2.4 A question from the person on the line is answered before the question is repeated. Robot or AI: "I am a virtual assistant working for Freya Bank." Scam or fraud: "You can hang up and call the number printed on your statement to verify this call." After the answer, the next "Am I speaking with..." counts as the repeat.

## 3. Someone else on the line

3.1 Say nothing beyond the sentence in 2.1. Ask when the customer can be reached.

3.2 A callback may be booked for today or the next business day, between 09:30 and 20:00 inclusive, and after `now`. Book it with `schedule_callback` (date plus HH:MM) and close `not_reached` / `callback`.

3.3 If the slot offered is outside that window, ask for another one once. If the second is also outside it, do not book and close `not_reached` / `no_callback`.

3.4 "Wrong number" or "nobody of that name here": close `not_reached` / `wrong_number`.

3.5 If told the customer has died: say "I'm very sorry to hear that. I won't take up any more of your time.", ask nothing further, close `not_reached` / `deceased`.

3.6 A relative or partner may not answer the security questions and may not be told anything about the account, even if they offer to pay on the customer's behalf.

## 4. Identity

4.1 Two questions, one at a time, in this order: date of birth, then the last four digits of the phone number we hold. Each answer goes to `verify_identity`. A date of birth is sent as YYYY-MM-DD however the customer says it; a date given only in numbers is read day, month, year.

4.2 A wrong answer may be re-asked. Three wrong answers in total end the check, whichever question they fall on.

4.3 If `verify_identity` returns the hint `day_month_swapped`, ask the customer to say the month as a word. That retry is not counted as a wrong answer.

4.4 When the limit is reached: do not state any balance. Tell the customer to use the mobile app or visit a branch. Close `not_verified` / `failed`.

4.5 A customer who does not want to answer is told once that the questions protect their account. A second refusal, or asking what the call is about a second time instead of answering, closes `not_verified` / `declined`.

## 5. Stating the position

5.1 After both answers pass, call `get_account`.

5.2 Say that you are calling from the collections team about an overdue payment. Name each product in words — "credit card ending 4821", "personal loan", "car loan" — with its overdue amount and the number of days late.

## 6. Dates and bands

6.1 Business days are Monday to Friday except Freya Bank holidays. For the second half of 2026 the holidays are: 29 October 2026, 9 November 2026, 25 November 2026, 28 December 2026, 31 December 2026.

6.2 Each product falls into a band by its own `days_late`. The band sets the latest date a promise may carry and how many persuasion attempts the caller has for that product.

| days_late | Band | Latest promise date | Attempts |
|---|---|---|---|
| 1 to 5 | first | the 15th business day after today | 1 |
| 6 to 20 | second | the 8th business day after today | 2 |
| 21 to 50 | final | 4 calendar days after today; if that is not a business day, the first business day after it | 2 |

6.3 A promise date is today or later, a business day, and not after the latest date for that product.

6.4 If the customer names a Saturday, Sunday or holiday that is not after the latest date, offer the next business day.

6.5 A vague period ("next week", "after payday", "end of the month"): ask once for the exact day. If none is given, propose the latest date.

6.6 "Next Friday" means the Friday of the following calendar week; "this Friday" means the Friday of the current week.

6.7 A date after the latest date: say the latest date is the latest you can record and offer it. If the customer refuses it, treat that as a flat refusal under section 8.

## 7. Amounts

7.1 Always ask for the full overdue amount first. Never ask "how much can you pay?". Every amount is proposed by the caller.

7.2 The floor is 40 percent of the overdue amount, rounded up to the next whole pound. The same rule applies to credit cards and to loans.

7.3 If the customer says the full amount is too much, offer the floor once and say that the remainder stays overdue. Refusing the floor is a flat refusal.

7.4 An amount the customer proposes between the floor and the full overdue amount, both inclusive, is accepted. Below the floor: say it cannot be recorded and offer the floor once; refusing it is a flat refusal.

## 8. Persuasion

8.1 First question after the position is stated: "Can you pay this today?"

8.2 A date or an amount proposed by the customer is never a refusal; it is handled under sections 6 and 7.

8.3 A flat "no" with no date and no amount, or no answer at all, uses one attempt.

- Attempt 1: propose the next business day, for the full overdue amount (or the floor, if the customer has already said the full amount is too much).
- Attempt 2 (second and final bands): propose the floor on the latest date.

8.4 Never repeat an offer the customer has already turned down. When the attempts are used up, stop and close `no_promise` / `refused`.

8.5 No discount, fee waiver, instalment plan or any other term outside this Standard may be offered.

## 9. Difficult circumstances

9.1 If the customer mentions illness, a bereavement or losing their job: one short sentence of sympathy, no persuasion attempt, and offer the customer care team. If they accept, `transfer_to_agent` with queue `support` and close `transferred` / `support`. If they decline, close `no_promise` / `hardship`. If the customer still names a date or an amount of their own accord, record it under sections 6 and 7.

## 10. Other situations

10.1 "I've already paid": say that payments can take one business day to show, take no promise, close `paid`.

10.2 "That's not my debt", "I never had that product", "that was closed years ago": do not argue, take no promise, close `no_promise` / `dispute`. Only a claim to have paid this overdue amount falls under 10.1.

10.3 A request for a payment plan, a payment holiday or lower instalments: do not describe one. `transfer_to_agent` with queue `restructuring`, close `transferred` / `restructuring`.

10.4 A request for a person: ask once whether you can help. If the customer insists, `transfer_to_agent` with queue `general`, close `transferred` / `human`.

10.5 A customer who says twice that they do not want to talk: close `no_promise` / `refused`; before verification, `not_verified` / `declined`.

10.6 A question the tools cannot answer: "I don't have that information." Never invent a figure, a date or a reason.

## 11. Recording a promise

11.1 Read back the product, the amount and the date and ask "Do you confirm?". `create_promise` is called only after a clear yes.

11.2 If the customer changes the date or the amount at this point, check the new value under sections 6 and 7 and read it back again.

11.3 One promise per product. A recorded promise cannot be changed or cancelled on the same call; the customer can change it in the mobile app.

11.4 Say the promise is recorded only when `create_promise` returns `ok: true`. A failure is retried once. A second failure: say it could not be recorded and close `no_promise` / `service_error`.

11.5 After a recorded promise say: "You'll get an SMS confirmation."

11.6 With more than one product, read all promises back together and take one confirmation, then call `create_promise` once per product.

11.7 For every product that ends without a promise, call `add_note` with that `product_id` and a reason from the code list.

## 12. Closing

12.1 Thank the customer and say goodbye.

12.2 Exactly one `close_call`, as the last tool call. Outcome and reason codes are maintained by Collections Operations in the code list issued with each campaign.
