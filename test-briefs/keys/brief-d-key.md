# Answer key: test-briefs/brief-d

Source documents, oldest to newest. A later document wins where they disagree.

1. `02-policy.md` — EATS v6, effective 1 Jun 2026 (base).
2. `01-email-thread.md` — Priya's mail of 30 Sep + clarifications 1 Oct (amends v6).
3. `04-code-list.md` — Ops Training v4, 6 Oct (codes; fixes reason-free outcomes).
4. `03-memo.md` — Owen, 9 Oct (overrides everything above where it differs).

`openapi.json` is byte-identical to `FREYA/kit/tools/openapi.json`. Identity fields: `date_of_birth`, `phone_last4` only. Practical "today" for all computed values below: **Wed 2026-10-14 11:00**.

⚑ = the memo overrides an earlier value. Rows without a marker take their final value from the email thread or the policy.

## Final rules

| # | Area | Policy v6 | Email (30 Sep / 1 Oct) | Memo 9 Oct | FINAL |
|---|---|---|---|---|---|
| 1 ⚑ | Holidays | 10-29, 11-09, 11-25, 12-28, 12-31 | – | adds **10-16** | 2026-10-16, 10-29, 11-09, 11-25, 12-28, 12-31 |
| 2 | Bands (days_late) | 1-5 first / 6-20 second / 21-50 final | same | – | same |
| 3 | Latest date (deadline) | first: 15th business day after today; second: 8th business day; final: 4 **calendar** days, rolled forward to a business day | same | – | first **2026-11-06**, second **2026-10-27**, final **2026-10-19** (18 Oct is Sunday) |
| 4 ⚑ | Persuasion attempts | 1 / 2 / 2 | 2 / 2 / 2 | final band → **1** | **2 / 2 / 1** |
| 5 | Attempt 1 | next business day, full amount | **3rd business day after today**, full amount (floor if "too much" already said); if after the latest date, the latest date | – | **2026-10-20**; final band: 2026-10-19 |
| 6 | Attempt 2 | floor on latest date | same | – | floor on latest date (first and second bands only) |
| 7 ⚑ | Floor | 40 % of past_due, rounded up to whole pound, all products | 40 % confirmed; minimum_payment / instalment_amount **not used**; amount above past_due recorded as past_due | **50 %** | ceil(0.5 × past_due); e.g. 187.40 → 94 |
| 8 ⚑ | Identity order | DOB, then phone_last4 | – | **phone_last4 first, then DOB** | phone_last4 → date_of_birth |
| 9 ⚑ | Wrong-answer limit | 3 | – | **2** | 2 in total; day_month_swapped retry free |
| 10 | Name-confirmation asks | 2 | **3** | – | 3 asks, then `not_reached`/`unclear`; first name alone counts as yes |
| 11 ⚑ | Callback window | today or next business day, 09:30-20:00, after now | – | **never today; next business day or the one after; 10:30-18:30 inclusive** | from 14 Oct (16 Oct is a holiday): **Thu 15 Oct or Mon 19 Oct**, 10:30-18:30; one re-ask, else `not_reached`/`no_callback` |
| 12 | Weekend/holiday date named | next business day | **last business day before it**; if that is before today, first business day after | – | Sat 17 Oct → **Thu 15 Oct**; Fri 16 Oct → Thu 15 Oct |
| 13 | "next <weekday>" | following week | **first such weekday after today**; "this" identical | – | "next Friday" on 14 Oct = 16 Oct → holiday → rule 12 → 15 Oct |
| 14 | Vague period | ask once, then propose latest date | ask once, then propose **attempt-1 date** | – | 2026-10-20 (final band 10-19) |
| 15 | Date after latest date | offer latest date; refusal = flat refusal (uses attempt) | refusal of latest date → **close `no_promise`/`refused` at once** | – | as email |
| 16 | First ask wording | "Can you pay this today?" | **"Are you able to clear this today?"** (once for all products) | – | email wording |
| 17 | Hardship triggers | illness, bereavement, job loss | **hospital stay, bereavement, redundancy or business closure, fire or flooding at home** | – | as email |
| 18 | Hardship sentence | "one short sentence of sympathy" | **"I'm sorry to hear that. I can put you through to our customer care team, who can look at your situation properly. Would you like that?"** | – | queue `support` → `transferred`/`support`; decline → `no_promise`/`hardship`; no persuasion attempt; whole-call, not per product |
| 19 | Request for a person | ask once if you can help, then `general` | **transfer at first request**, no pushback | – | queue `general` → `transferred`/`human` |
| 20 | "Don't want to talk" | twice | **once** | – | after verification `no_promise`/`refused`; before `not_verified`/`declined`; "what is this about?" is not such a statement (v6 4.5: second time = declined) |
| 21 ⚑ | "Already paid" | "payments can take one business day to show" | – | **"A payment can take up to three business days to reach the account; if it has not shown by then, please call us."** | no promise; note `paid` |
| 22 | Dispute | no argument, no promise | add **"A colleague from our disputes team will contact you within five business days."** | – | note `dispute`; call continues with other products |
| 23 | Confirmation question | "Do you confirm?" | **"Is that correct, and may I record it?"** | – | email wording |
| 24 | create_promise failure | retry once (2 tries) | **retry twice (3 tries)** | – | then note `service_error`; close `no_promise`/`service_error` if nothing else recorded |
| 25 ⚑ | Post-promise sentence | "You'll get an SMS confirmation." | – | **"We will send you a confirmation by text within the hour."** | memo sentence |
| 26 | Multi-product opening | one sentence per product | **count + total overdue first**, then one sentence per product | – | as email |
| 27 | Multi-product order | get_account order | **days_late descending; tie → larger past_due first** | – | as email |
| 28 | Multi-product confirmation | one read-back, one yes, then create_promise per product | **confirm each product separately, create_promise right after each yes** | – | as email |
| 29 | One date for everything | – | per product: after that product's latest date → that product on its latest date (say so); weekend → rule 12 per product | – | as email |
| 30 | add_note | every product without a promise | same, **also written before a transfer** for products already discussed | – | reasons: refused, hardship, dispute, paid, service_error |
| 31 | No-promise closing reason | – | **priority dispute > hardship > service_error > refused**; all paid → `paid` | – | as email |
| 32 | Reason-free outcomes | (code list of previous campaigns: promise, paid) | code list v4: **only `promise`**; `paid` carries reason `paid` | – | only `promise` |
| 33 | Transfer after promise | – | close `transferred` with transfer's reason | – | as code list |
| 34 | Opening sentence | "This is Freya Bank's virtual assistant. This call is recorded for quality and training." No arrears/card/loan words before verification, relatives included | – | – | policy |
| 35 | Robot / scam answers | "I am a virtual assistant working for Freya Bank." / "You can hang up and call the number printed on your statement to verify this call." then continue | – | – | policy |
| 36 | Deceased | "I'm very sorry to hear that. I won't take up any more of your time." → `not_reached`/`deceased` | – | – | policy |
| 37 | Wrong number | `not_reached`/`wrong_number` | – | – | policy |
| 38 | Restructuring request | queue `restructuring` → `transferred`/`restructuring`; no plan described | notes for discussed products first; recorded promises stay | – | policy + email |
| 39 | Identity limit reached | no balance; app or branch; `not_verified`/`failed` | – | – | policy |
| 40 | Amounts | ask full first; never "how much can you pay"; floor offered once; floor..full inclusive accepted; below floor → floor once | + above past_due → record past_due | – | policy + email |
| 41 | No discounts / plans / waivers | banned | – | – | policy |
| 42 | Promise date validity | today or later, business day, ≤ latest date | – | – | policy |
| 43 | Recorded promise immutable | change only in app | – | – | policy |
| 44 | Closing | thank + goodbye, exactly one close_call last | – | – | policy |

Memo overrides: rows 1, 4, 7, 8, 9, 11, 21, 25 (eight).

## Computed calendar (today = Wed 2026-10-14)

Business days after today, in order: 15 Oct, 19, 20, 21, 22, 23, 26, 27, 28, 30 Oct, 2 Nov, 3, 4, 5, 6 Nov.

| Quantity | Value |
|---|---|
| 1st business day after today | 2026-10-15 |
| 3rd business day (attempt 1, vague-period fallback) | 2026-10-20 |
| 8th business day (second-band latest date) | 2026-10-27 |
| 15th business day (first-band latest date) | 2026-11-06 |
| today + 4 calendar days = Sun 18 Oct → final-band latest date | 2026-10-19 |
| Callback days | 2026-10-15, 2026-10-19 (10:30-18:30) |
| "next Friday" / "this Friday" | 2026-10-16 → holiday → 2026-10-15 |
| "Saturday" (17 Oct) | → 2026-10-15 |
| "next Monday" | 2026-10-19 |
| "end of the month" (31 Oct, Sat; after 2nd-band latest date 27 Oct) | first band: 30 Oct (Fri, business day, ≤ 6 Nov); second band: offer 27 Oct |

## Traps worth a case each

- 16 Oct is this week's Friday and a holiday only in the memo. Business-day counts from the policy alone come out one day early.
- Weekend/holiday rolls **back**, not forward (unlike A, B, C).
- "next Friday" = the coming Friday (A/C read it as the following week).
- Floor is a percentage of past_due; minimum_payment / instalment_amount are a decoy.
- Final band: attempt 1 already lands on the latest date; only one attempt after the memo.
- phone_last4 is asked first; two wrong answers end the check.
- Product order is by days_late descending, not get_account order.
- Confirmation and create_promise per product, not one batch.
- Notes are written before a transfer (B forbids notes on a transferred call).
- No-promise reason by priority, not by product order.
- `paid` is closed **with** reason `paid`; only `promise` is reason-free.
- A single "I don't want to talk" ends the call; a human is transferred at the first request.
- Callback never today, but the day after next business day is allowed.
