From: Mara Lindqvist (Voice Automation) <m.lindqvist@freyabank.example>
To: Priya Nandakumar (Collections Operations Manager) <p.nandakumar@freyabank.example>
Cc: Retail Credit; Compliance
Date: Tue, 29 Sep 2026 10:41
Subject: Q4 early arrears campaign - questions on EATS v6

Hi Priya,

We are building the assistant for the Q4 campaign from the Early Arrears Telephony Standard v6 (attached) and the tool specification. Before we lock the flows, some points where v6 is silent or where we have heard that practice has moved on:

1. Attempts per band. v6 gives the first band one attempt. The human callers tell us they get two. Which is it?
2. The attempt-1 date. v6 says "the next business day". Is that still what you want? It lands very close to the call.
3. The 40 percent floor: whole pounds, rounded up? And do minimum_payment / instalment_amount from get_account play any part?
4. Weekend or holiday dates named by the customer. v6 says roll forward to the next business day; the team lead on the floor says you now roll back.
5. "Next Friday". v6 reads it as the following week. Customers on our recordings almost always mean the coming Friday.
6. Customers with two or three products: order of discussion, how to open, how many confirmations.
7. Difficult circumstances: v6 lists illness, bereavement and job loss. Compliance mentioned a wider list.
8. Requests for a person, and customers who say they do not want to talk.
9. create_promise failures: still one retry?

Anything else you want changed from v6, now is the moment.

Thanks,
Mara

---

From: Priya Nandakumar (Collections Operations Manager) <p.nandakumar@freyabank.example>
To: Mara Lindqvist (Voice Automation) <m.lindqvist@freyabank.example>
Cc: Retail Credit; Compliance
Date: Wed, 30 Sep 2026 16:05
Subject: RE: Q4 early arrears campaign - questions on EATS v6

Mara,

Answers in order. Treat this mail as an amendment to v6; where they differ, this mail applies. Owen is also preparing a short memo for the campaign start that may move a few more parameters (holidays, identity, callback). Build to this mail and apply his memo on top when it arrives.

1. Attempts. First band: TWO attempts, not one. Second band: two. Final band: two, as in v6. So 2 / 2 / 2 for now.

2. Attempt-1 date. Replace "the next business day" with the THIRD business day after today. Full overdue amount, or the floor if the customer has already told you the full amount is too much. If the third business day is after the product's latest date, use the latest date instead. Attempt 2 stays as v6: the floor on the latest date.

3. Floor. Yes: 40 percent of the overdue amount, rounded UP to the next whole pound, for every product type. minimum_payment and instalment_amount are returned by get_account but are NOT used in this campaign. Do not quote them and do not use them as a floor. One more thing: if a customer offers more than the overdue amount, record the overdue amount and tell them that is the figure we hold.

4. Weekend and holiday dates. The floor lead is right. If the customer names a Saturday, Sunday or bank holiday that is not after the latest date, offer the LAST business day BEFORE it. If that business day would be before today, offer the first business day after the named day instead. This replaces v6 6.4.

5. "Next <weekday>". Read it as the first such weekday after today. "This <weekday>" means the same. So "next Friday" said on a Wednesday is the Friday of the same week. Replaces v6 6.6.

6. Several products.
   - After get_account, open with the number of overdue products and the total overdue across them ("You have two overdue products with a total of 640 pounds overdue"), then one sentence per product with the product in words, its overdue amount and its days late.
   - Ask once, for all products together: "Are you able to clear this today?" This also replaces the v6 8.1 wording for single-product calls. Do not ask about today again product by product.
   - If the answer is not a yes for everything, take the products one at a time in order of days late, highest first. Two products with the same days late: the larger overdue amount first. NOT the order get_account returns them.
   - Attempts are counted per product, each product starting at attempt 1. Band and latest date are per product.
   - Confirm each product SEPARATELY: read back product, amount and date, ask "Is that correct, and may I record it?" and call create_promise straight after the yes, before moving to the next product. That confirmation wording also replaces "Do you confirm?" in v6 11.1 for single-product calls.
   - If the customer names one date for everything and that date is after one product's latest date, that product is recorded on its own latest date; say so when you read that product back. The others keep the named date.
   - A disputed or already-paid product does not end the call. Note it with add_note and carry on with the others.
   - add_note for every product that ends without a promise (reason from the code list). This includes the case where no product gets a promise. Where the call is transferred, write the notes for the products already dealt with BEFORE calling transfer_to_agent. Promises already recorded stay; promises agreed but not yet recorded are not recorded.
   - Closing with no promise recorded: if every product is noted paid, close paid. Otherwise the reason follows this priority regardless of product order: dispute, then hardship, then service_error, then refused. At least one promise recorded: close promise, unless the call was transferred, in which case transferred with the transfer's reason.

7. Difficult circumstances. The list is now: a hospital stay, a bereavement, redundancy or the closure of the customer's business, and fire or flooding at the customer's home. On any of these: no persuasion attempt, and say exactly "I'm sorry to hear that. I can put you through to our customer care team, who can look at your situation properly. Would you like that?" Accept: transfer_to_agent queue support, close transferred / support. Decline: close no_promise / hardship. If they volunteer a date or an amount anyway, record it under the normal rules. With several products the circumstance applies to the whole call, not to one product.

8. People and refusals. A request for a person is honoured at the FIRST request: no "can I help you first", straight to transfer_to_agent queue general and close transferred / human. A customer who says clearly ONCE that they do not want to talk or want to end the call: respect it at once, close no_promise / refused (before verification not_verified / declined). v6 10.4 and 10.5 are replaced.

9. create_promise. Retry TWICE, so three tries in all, before you give up on a product. Then say it could not be recorded, add_note service_error for that product, and (if nothing else was recorded) close no_promise / service_error.

Two more changes while I am at it:

10. Vague period ("next week", "after payday"): ask once for the exact day. If none comes, propose the attempt-1 date from point 2, not the latest date.

11. A date after the latest date: offer the latest date as v6 says. If the customer refuses the latest date, close no_promise / refused there and then. Do not spend further attempts.

12. Dispute: when closing a disputed product add the sentence "A colleague from our disputes team will contact you within five business days." No arguing, no promise on that product.

13. Name confirmation: three asks, not two. Line quality on the mobile routes is poor. After the third unclear answer close not_reached / unclear.

Everything else in v6 stands until Owen's memo.

Priya

---

From: Mara Lindqvist (Voice Automation) <m.lindqvist@freyabank.example>
To: Priya Nandakumar (Collections Operations Manager) <p.nandakumar@freyabank.example>
Cc: Retail Credit; Compliance
Date: Thu, 1 Oct 2026 09:17
Subject: RE: RE: Q4 early arrears campaign - questions on EATS v6

Priya,

Clear, thank you. Three follow-ups:

a) Point 6, the one-date-for-everything case: if the named date is a Saturday for product A and after the latest date for product B, we apply the weekend rule to A (roll back) and the latest date to B? Separately per product?
b) Point 2: in the final band the third business day is normally past the latest date, so attempt 1 there is "full amount on the latest date". Correct?
c) Point 8: does "once" also apply if the customer says it during the identity questions?

Mara

---

From: Priya Nandakumar (Collections Operations Manager) <p.nandakumar@freyabank.example>
To: Mara Lindqvist (Voice Automation) <m.lindqvist@freyabank.example>
Cc: Retail Credit; Compliance
Date: Thu, 1 Oct 2026 14:52
Subject: RE: RE: RE: Q4 early arrears campaign - questions on EATS v6

a) Yes, separately per product. Each product's date is checked against its own band.
b) Correct.
c) Yes. Before verification it closes not_verified / declined, after verification no_promise / refused. One clear statement is enough either way. A question like "what is this about?" is not such a statement; v6 4.5 covers that.

Priya

---

From: Priya Nandakumar (Collections Operations Manager) <p.nandakumar@freyabank.example>
To: Mara Lindqvist (Voice Automation) <m.lindqvist@freyabank.example>
Cc: Retail Credit; Compliance; Ops Training
Date: Tue, 6 Oct 2026 11:30
Subject: Q4 campaign - code list attached, memo to follow

Mara,

Ops Training has issued the close_call code list for the campaign (attached, v4). It also fixes which outcomes carry a reason, which differs from what some of the older flows did; please follow the list.

Owen's memo should be with you by the end of the week. Apply it on top of v6 and my mail of 30 September.

Priya
