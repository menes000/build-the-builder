# Answer key: test-briefs/brief-e

Single clean specification (`brief.md`), Brief A structure, 59 numbered rules. `openapi.json` is byte-identical to `FREYA/kit/tools/openapi.json`. Identity fields: `date_of_birth`, `phone_last4` only. Practical "today": **Wed 2026-10-14 11:00** (morning greeting).

Reason-free outcomes: `promise` and `paid`. The requested `promise_full` / `promise_partial` reasons do not exist in the openapi enum, so `promise` stays reason-free as in A.

## Final rules, with what differs from A / B / C / D

| # | Area | Brief E | Differs from |
|---|---|---|---|
| 1 | Greeting | "Good morning/afternoon (afternoon from 12:00), my name is Freya and I am calling on behalf of Freya Bank." No recording notice in sentence 1 | A/C/D: "digital/automated/virtual assistant" + recorded in sentence 1 |
| 2 | Recording notice | after name confirmation, before identity: "Before we go on, I must let you know that this call is recorded." | all others: first sentence |
| 3 | Name ask | **once only**; no confirmation → `not_reached`/`unclear`; "go ahead" does not count | A/C: 2 asks; D: 3 |
| 4 | Robot question | "Yes, I am Freya Bank's automated caller. A member of staff can call you instead if you prefer." → prefers staff = human request (rule 48) | A/D: one sentence, continue |
| 5 | Scam question | statement/back-of-card sentence, then **ask once whether to continue**; no → `not_verified`/`declined` before verification, `no_promise`/`refused` after | A/C/D: say sentence and continue |
| 6 | Identity order | date_of_birth, then phone_last4 | D: phone first (A/C: same order as E) |
| 7 | Wrong-answer counting | **per question**: 2 wrong on the same question ends the check; one wrong on each does not (max 2 total ever) | A/C: 3 total; D: 2 total |
| 8 | Partial date (year only, day+month only) | ask for full date; no verify_identity call; not a wrong answer | unspecified elsewhere |
| 9 | day_month_swapped | **resend swapped at once, no question**; a second failure counts as a wrong DOB answer | A/C/D: ask month as a word |
| 10 | Third party: message | may leave "Please ask {title} {last_name} to call Freya Bank on the number printed on their statement." | others: nothing beyond opening |
| 11 | Third party: pays | spouse/relative told payment possible in app or branch on the customer's behalf; nothing recorded; close callback / no_callback | A/C/D: may not pay, no message |
| 12 | Callback window | today (after now) or next **3 calendar days, Saturday allowed**, Sunday and holidays excluded; **13:00-16:00** inclusive; one re-ask | A: today/next bd 10-19; C: next bd 09-17:30; D: next 2 bd 10:30-18:30 |
| 13 | Deceased sentence | "I am sorry for your loss. We will not call this number again." | A: "I am sorry for your loss."; C: condolences; D: different |
| 14 | Holidays | 2026-10-21, 11-03, 11-18, 12-24, 12-26 | A: 10-26, 11-11, 11-26; C: 10-12, 11-02, 11-27; D: 10-16, 10-29, 11-09, 11-25 |
| 15 | Bands / deadline | 1-30 standard: 9th business day; 31-90 priority: 6th business day; per product | A: 12/7; C: 10/5/3cal; D: 15/8/4cal |
| 16 | "Tomorrow" | first business day after today = **2026-10-15** | – |
| 17 | Weekend/holiday date | offer **both** the business day before and after, customer chooses; neither → flat refusal; before < today → only after | A/C: next; D: previous |
| 18 | "next Friday" | **never interpret**; ask for the day of the month | A/C: following week; D: nearest |
| 19 | Vague period | ask **twice** for exact day, then propose the deadline | A/C: once then deadline; D: once then attempt-1 date |
| 20 | Date after deadline | offer deadline; refusal = flat refusal (uses the attempt) | D: closes immediately |
| 21 | Floor | credit card: `minimum_payment`; loans: **ceil(instalment_amount / 2)** | A/C: minimum_payment / full instalment; D: 50% of past_due |
| 22 | Amount below floor | floor offered **twice** (second with "lowest the bank records"); after second refusal `no_promise`/`refused`, no attempt | A/C/D: once |
| 23 | "Too much" | floor once; refuse → flat refusal → attempt (floor on deadline allowed, date differs) | A: attempt 2 only in late band |
| 24 | Above past_due | record past_due | D same; A/C unspecified |
| 25 | First ask | "Can you pay {full} by tomorrow, {date}?" (total for all products) — **no "today" ask** | A/C: "today?"; D: "clear this today?" |
| 26 | Persuasion | **one attempt per product in every band**: floor on the product's deadline | A: 1/2; C: 1/2/1; D: 2/2/1 |
| 27 | Hardship triggers | **full-time carer, mental health difficulties, prison/detention, armed forces deployment**; illness/bereavement/job loss explicitly NOT hardship (one sympathy sentence, normal rules) | A/C: illness, bereavement, job loss; D: hospital, bereavement, redundancy, fire/flood |
| 28 | Hardship sentence | "Thank you for telling me. Our customer care team can look at this with you. Shall I connect you now?" → `support`; decline → `no_promise`/`hardship` | different wording each brief |
| 29 | Read-back | **one read-back for all products**, "Have I got that right?", then create_promise per product in get_account order | D: per product; A: "Do you confirm?" |
| 30 | create_promise failure | **no retry**; say it could not be recorded; continue with other products; note `service_error` | A/C: 1 retry; D: 2 retries |
| 31 | Post-promise sentence | "Your promise is noted. A reminder will be sent the day before the payment date." | others: text-message confirmation |
| 32 | Already paid | ask **when**: today/yesterday → `paid` (or note paid); earlier → "has not reached the account", ask for a promise as if unpaid; insists with no date → treat as dispute | A/C/D: always `paid` |
| 33 | Dispute | "I will pass that to the team that looks into disputes."; one product → call ends `no_promise`/`dispute`; several → note `dispute`, continue; "never been a customer" → call ends regardless | D: disputes-team sentence, continue |
| 34 | Human request | ask once "Is there something I can help you with first?"; insists → `general`/`human` | D: immediate |
| 35 | Restructuring | **notes first**: `add_note` reason `refused`, text "payment plan requested" for every product without a recorded promise, then `transfer_to_agent` `restructuring` | B: no notes on any transfer; D: notes with their own reasons |
| 36 | Support / human transfer | **no notes** before or after | D: notes before every transfer |
| 37 | "Don't want to talk" | **twice**; before verification `not_verified`/`declined` | D: once |
| 38 | Multi-product opening | count + total, then each product in **get_account order**, never reordered | D: days_late descending |
| 39 | No-promise closing | **first product in get_account order**: note paid → `paid`; else `no_promise` with that product's reason; other notes irrelevant | B: first non-paid; D: priority |
| 40 | Single product | never `add_note` | B/D: n/a |
| 41 | Reason-free outcomes | `promise`, `paid` | D: only `promise` |
| 42 | Transfer after promise | `transferred` with transfer's reason | same everywhere |

## Computed calendar (today = Wed 2026-10-14, 11:00 → "Good morning")

Business days after today: 15, 16, 19, 20, 22, 23, 26, 27, 28, 29, 30 Oct, 2 Nov (21 Oct is a holiday).

| Quantity | Value |
|---|---|
| Tomorrow (first ask date) | 2026-10-15 |
| Standard band deadline (9th bd) | 2026-10-28 |
| Priority band deadline (6th bd) | 2026-10-23 |
| Callback days | 14 Oct (13:00-16:00, after 11:00 so whole window), 15, 16, 17 Oct (Sat); not 18 Oct (Sun) |
| Customer names Sat 17 Oct | offer Fri 16 Oct and Mon 19 Oct, customer picks |
| Customer names Wed 21 Oct (holiday) | offer Tue 20 Oct and Thu 22 Oct |
| "next Friday" | ask for the day of the month (no interpretation) |
| "End of the month" twice without a day | propose deadline: 28 Oct (standard) / 23 Oct (priority) |
| Floor examples | card min 45.00 → 45; loan instalment 310.00 → 155; loan instalment 333.00 → 167 |

## Traps worth a case each

- Recording notice must come after name confirmation, not in the opening sentence; the name is asked once only.
- Per-question wrong-answer counting: wrong DOB, right DOB, wrong phone, right phone passes; wrong DOB twice fails even though the mock still has one wrong answer left.
- Year-only date of birth must not be sent to verify_identity.
- day_month_swapped: resend immediately, no question to the customer.
- Floor for loans is half the instalment, rounded up; credit card floor is minimum_payment.
- Below-floor amount gets the floor twice, then the call closes without a persuasion attempt.
- One attempt everywhere, always the floor on the deadline; first ask is "by tomorrow", no "today" question.
- Weekend date: customer chooses between before and after; weekday names are never interpreted.
- Illness/job loss are NOT hardship here; carer / mental health / prison / armed forces are.
- "Already paid" branches on when: paid last week → ask for a promise.
- Restructuring writes `refused` notes before the transfer; support/human transfers write none.
- No retry on create_promise.
- Closing with several products follows the first product only, even when its note is `paid` and the second is `refused`.
- Callback allows Saturday and today, but only 13:00-16:00.
