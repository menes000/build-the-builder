# Brief F — answer key (Clear Start campaign)

Sources: 01 = 01-email-thread.md (mails 2 Oct–9 Oct), 02 = 02-contact-policy.md (ACP 2026/3), 03 = 03-floor-memo.md (Ruth, 6 Oct), 04 = 04-code-list.md.
Precedence (02 §0.2, repeated in 03 header and Ingrid 7 Oct): Compliance > Head of Collections (Ingrid) mails > team lead memo > Policy, **whatever the dates**; same source → later date wins.

Final holidays: Mon 2026-10-19, Mon 2026-11-02, Wed 2026-11-11, Thu 2026-12-24, Fri 2026-12-25, Thu 2026-12-31, Fri 2027-01-01. (23 Oct removed.)

## Effective rules

1. **Opening sentence** "Good day, this is Ava, Freya Bank's automated assistant. This call is recorded." — 02 §2.1.
2. **Forbidden before verification**: debt, collections, arrears, overdue, late, payment, card, loan, balance, owe; no product/amount. — 02 §2.2 + Compliance mail 7 Oct pt1 (adds balance/owe).
3. **Never say "debt" or "promise" at any point**; say "overdue amount", "payment arrangement". — Compliance 7 Oct pt1. Ex: read-back "Shall I set this up?", never "Do you confirm the promise?".
4. **Name check** "Am I speaking with {first_name} {last_name}?"; title never used; confirmation = yes / speaking / that's me / full name; first name alone is NOT confirmation; two asks then not_reached/unclear; a question answered first, next ask = 2nd. — 03 §1 overrides 02 §2.3–2.4 (title + last name, "own name"). Ex: "Daniel?" → "Daniel here" ≠ confirmation, ask again.
5. **Robot / scam** answers per 02 §2.5, then continue.
6. **Third party**: say nothing beyond opening; don't ask who they are; never suggest a time; ask "When would be a good time to reach {first_name} {last_name}?"; no time named → not_reached/no_callback at once. — 02 §3.1 + 03 §2.
7. **Callback window**: today (time ≥ now+60 min) or either of the next two business days, 09:00–18:00 inclusive; no Saturday. Outside → ask once more → still outside → no_callback. Booking fails twice → no_callback. — 02 §3.2–3.4; end time 18:00 from 03 §2 (overrides 17:30); Saturday removed by Ingrid 7 Oct pt2. Ex: now Thu 2026-10-15 11:00: allowed days Thu 15 (≥12:00), Fri 16, Tue 20 (Mon 19 holiday). "Tuesday at 18:00" → book 2026-10-20 18:00. "Saturday 11:00" → outside.
8. **Wrong number / deceased / relative wants to pay** — 02 §3.5–3.7 (deceased sentence fixed).
9. **Identity**: DOB first, then phone_last4; wrong → "That doesn't match our records." (never which part); **2 wrong answers in total end the check** (mock still says 1 left); day_month_swapped retry and partial DOB are free. — 02 §4 + Ingrid 7 Oct pt1 (overrides 3). Ex: DOB wrong, phone wrong → stop after the 2nd.
10. **Failed identity**: say "For your security I can't go any further on this call. Please visit any Freya Bank branch with photo ID." — no app — not_verified/failed. — 03 §3 overrides 02 §4.5.
11. **Declining questions**: explain once; 2nd refusal / 2nd "what's this about" → not_verified/declined. — 02 §4.6.
12. **Person asked before verification**: no transfer; say once verified you can put them through or they can call the number on their statement; asks again instead of answering → not_verified/declined. After verification: ask once if you can help; insist → transfer general, transferred/human. — Ingrid 2 Oct pt3 overrides 02 §10.5 for the pre-verification part.
13. **get_account failure**: retry once; 2nd failure → apologise, no_promise/service_error, no notes. — 02 §5.1.
14. **Stating position**: "overdue amounts on your Freya Bank account"; with >1 product say how many; one sentence per product: words, past_due, **"overdue since <today − days_late>"**, NOT the number of days; never a total. — 02 §5.2, 03 §4 (overrides day count), Compliance pt2. Ex: now 2026-10-13, 12 days → "overdue since 1 October".
15. **Call order**: car loans → personal loans → credit cards; same type in get_account order. — 02 §5.3, 04 table. Ex: get_account [p1 card, p2 personal, p3 car] → order p3, p2, p1.
16. **Fee disclosure** once after stating products, before first pay question: "Freya Bank does not charge any fee for setting up a payment arrangement." — Compliance pt3.
17. **Bands / deadlines / attempts**: early 1–14: today+10 calendar days, rolled BACK to a business day, 1 attempt; mid 15–35: 6th business day, 2 attempts; late 36–60: 3rd business day, **1 attempt**. — 02 §6.2; late attempts 1 from Ingrid 5 Oct, which beats memo 03 §9 (memo is later-dated but lower authority). Ex: now Thu 2026-10-15: early → Sun 25 → Fri 2026-10-23; mid → 2026-10-26; late → 2026-10-21.
18. **Payday date (attempt-1 date)**: next 25th after today; not a business day → last business day before; if that is today → next business day; capped at the deadline. — 02 §6.4. Ex: now Thu 10-15, mid: 25 Oct Sun → Fri 2026-10-23 (with old list it would be Thu 22); now Mon 10-26 mid: 25 Nov → capped at deadline Wed 2026-11-04.
19. **Arrangement date**: today or later, business day, ≤ deadline. — 02 §6.3.
20. **Named weekend/holiday**: Saturday → last business day before; Sunday or holiday → first business day after. — 02 §6.5. Ex: now Thu 10-15, mid loan: "Saturday 24th" → Fri 2026-10-23; "Monday 19th" → Tue 2026-10-20.
21. **Date after deadline** → offer deadline; refusing it = flat refusal. — 02 §6.6.
22. **"next/this <weekday>"** = first such weekday after today; always say the calendar date back. — 03 §5 overrides 02 §6.8. Ex: Tue 2026-10-13, "next Friday" → Fri 2026-10-16.
23. **Vague period**: ask once; none → propose the payday date. — 03 §6 overrides 02 §6.7 (deadline).
24. **Amounts**: full past-due first; never "how much can you pay"; above past_due → arrange past_due. — 02 §7.1, 7.5.
25. **Card floor** = max(minimum_payment, floor(0.30 × past_due) to whole euro). — Ingrid 2 Oct pt1 (replaces min payment) then Ingrid 9 Oct b (higher of the two). Ex: 437.20 / min 43.72 → 131; 2125.10 / min 637.50 → 637.50; 150 / min 60 → 60.
26. **Personal loan floor** = instalment rounded UP to whole euro, max past_due. — 03 §10 + footnote. Ex: 103.50 → 104; instalment 213 → 213.
27. **Car loan**: full past_due only; "too much"/partial → "For a car loan I can only arrange the full overdue amount." = flat refusal; attempts both full (attempt 2 skipped if same date). — Ingrid 5 Oct overrides 02 §7.2.
28. **Too much** → floor once for the date on the table (not an attempt); refusal = flat refusal. Below floor → floor once; refusal = flat refusal. — 02 §7.3–7.4.
29. **First ask per product**: "Can you pay the {amount} on your {product} today?"; no combined ask. — 02 §8.1; Ingrid 2 Oct confirms no combined ask.
30. **Attempts**: each flat refusal triggers the next attempt: A1 full (or floor if "too much" said) on payday date; A2 floor on deadline; skip an exact repeat; none left → product ends refused. — 02 §8.3–8.4.
31. **No discounts/waivers/plans.** — 02 §8.5.
32. **Confirm/record per product**: read back product, amount, weekday+date; "Shall I set this up?"; yes → create_promise immediately, before next product. — 02 §9.1.
33. **After ok:true**: "That payment arrangement is now set up. You will receive a text message with the details." each time. — Compliance pt4 overrides 02 §9.5.
34. **create_promise failure**: retry once; 2nd failure → say it could not be set up; that product AND every product not yet dealt with → note service_error; stop; recorded arrangements stay; close per rule 42. — Ingrid 7 Oct pt3 overrides 02 §9.4 ("continue").
35. **Hardship list**: illness/hospital, bereavement, job loss, separation/divorce, caring for a seriously ill family member; fixed sentence "I'm sorry to hear that. Would you like me to put you through to our customer support team?"; no persuasion for the rest of the call; accept → transfer support; decline → all products not yet ended noted hardship; volunteered date/amount still recorded. — 02 §10.1 + Compliance pt5.
36. **Plan request**: call has ≥1 loan (even already dealt with) → transfer restructuring. All-cards call → "A payment plan for a credit card can't be arranged on this call." + flat refusal on current card. — 02 §10.2 + Ingrid 2 Oct pt4.
37. **Several things at once**: person > (plan if call has a loan) > hardship > plan (cards-only: n/a) > dispute > paid. — 02 §10.8 + Ingrid 2 Oct pt5.
38. **Dispute**: fixed sentence, note dispute, continue. — 02 §10.3.
39. **Already paid (full)**: "Payments can take up to two business days to show.", note paid, continue. **Part-paid**: remainder becomes full amount; floor = min(floor, remainder). — 02 §10.4 + 03 §7. Ex: personal 780, paid 500 → ask 280; floor min(260, 280) = 260.
40. **Not want to talk** twice → after verification remaining products noted refused; before → not_verified/declined. — 02 §10.6.
41. **Notes on EVERY call incl. single-product**, written when the product ends; on transfer only already-ended products have notes. — 03 §8 overrides 02 §11.1; 04 add_note.
42. **Closing**: promise if ≥1 recorded and no transfer; transfer → transferred/<queue reason>; all paid → paid (no reason); else no_promise with the reason of the non-paid product with **largest past_due** (tie: earlier call order). — Ingrid 2 Oct pt6 overrides 02 §12.3; 04.
43. **Closing line** "Thank you for your time, {first_name} {last_name}. Goodbye."; before a transfer "I'm putting you through now." — 02 §12.1 + 03 §1. One close_call, last.

## Traps

- T1 Late band 1 attempt: memo (6 Oct, later) says 2 but Ingrid (5 Oct) wins by authority, not date.
- T2 23 Oct is a business day (removed 9 Oct); 2 Nov is a holiday (P.S. of 5 Oct mail).
- T3 Card floor: 30 % rounded DOWN, then max with minimum_payment.
- T4 Personal loan floor rounded UP (memo footnote cap at past_due).
- T5 Car loan: no floor, partial = flat refusal.
- T6 add_note on single-product calls.
- T7 Name check by first+last name, no title; first name alone not enough.
- T8 Callback until 18:00, no Saturday; never suggest a time.
- T9 Identity limit 2 though the mock says 3.
- T10 No app after failed identity; branch + photo ID.
- T11 No transfer to a human before verification.
- T12 Plan on cards-only call not transferred; plan beats hardship if any loan.
- T13 Closing reason by largest past_due.
- T14 "Overdue since" date, no day count, no total; never "promise"/"debt".
- T15 create_promise double failure stops the call.
- T16 Call order by type, not get_account order.

## Expected outcomes

| # | now | products (get_account order) | situation | promises | notes | close |
|---|---|---|---|---|---|---|
| 1 | Tue 2026-10-13 | p1 card 437.20, 12d, min 43.72 | too much; no today; accepts A1 | p1 131.00 2026-10-23 | — | promise |
| 2 | Thu 2026-10-15 | p1 card 510, 16d; p2 personal 1320, 16d, inst 440; p3 car 140, 7d | pays card tomorrow, refuses both loans | p1 510 2026-10-16 | p3 refused (after A1 140 on 10-23), p2 refused (A1 1320 on 10-23, A2 440 on 10-26) | promise |
| 3 | Thu 2026-10-15 | p1 car 1250, 40d, inst 400 | "too much, I can do 400"; refuses A1 (1250 on 10-21) | — | p1 refused | no_promise/refused (only one attempt) |
| 4 | Mon 2026-10-26 | p1 personal 780, 21d, inst 260 | paid 500 already; agrees remainder on A1 | p1 280 2026-11-04 | — | promise |
| 5 | Wed 2026-10-21 | p1 card 300, 4d; p2 personal 900, 20d | loan "paid off years ago"; refuses card | — | p2 dispute, p1 refused | no_promise/dispute (900 > 300) |
| 6 | Mon 2026-10-26 | p1 card 1200, 30d, min 360; p2 card 95, 4d | refuses p1 (A1 1200 on 11-04, A2 360 on 11-04); then caring for ill mother on p2, declines support | — | p1 refused, p2 hardship | no_promise/refused (1200 > 95) |
| 7 | Wed 2026-10-21 | p1 card 220, 9d; p2 personal 640, 9d; p3 car 75, 3d | car paid today; on loan: lost job + wants lower instalments | p3 75 2026-10-21 | none | transferred/restructuring |
| 8 | Tue 2026-10-13 | p1 card 365, 8d, min 109.50 | asks for a plan; accepts A1 | p1 365 2026-10-23 | — | promise (no transfer) |
| 9 | Thu 2026-10-15 | third party | Mon 9:30 (holiday) → Tue 18:00 | — | — | not_reached/callback 2026-10-20 18:00 |
| 10 | any | single card | DOB wrong, phone wrong | — | — | not_verified/failed after 2nd wrong |
| 11 | any | single | asks for a person twice before DOB | — | — | not_verified/declined, no transfer |
| 12 | Tue 2026-10-27 | p1 card 300, 4d; p2 personal 900, 20d | agrees 900 today on loan; create_promise fails twice | — | p2 service_error, p1 service_error | no_promise/service_error |
| 13 | any | single card 180 | already paid in full | — | p1 paid | paid (no reason) |
| 14 | Thu 2026-10-15 | p1 personal 640, 20d, inst 213 | names Saturday 24th | p1 640 2026-10-23 | — | promise |
| 15 | Tue 2026-10-13 | single card | "next Friday" | date 2026-10-16 | — | promise |
