FREYA BANK — COLLECTIONS FLOOR MEMO

From: Ruth Okafor, Collections Team Lead
To: Collections floor; Voice Automation
Cc: Ingrid Falk, Head of Collections
Date: Tuesday 6 October 2026
Re: Clear Start — how we actually run the calls

This memo refines ACP 2026/3. Where it differs from the Policy, this memo applies. It does not change anything in a mail from Ingrid or from Compliance: where one of those says something different, that mail applies, whatever the dates.

**1. Names.** Since the records migration the `title` field is wrong on too many files, and customers complain. Do not use the title at all. The name check is "Am I speaking with {first_name} {last_name}?", and the customer is addressed by first and last name for the rest of the call, including the goodbye ("Thank you for your time, {first_name} {last_name}. Goodbye."). Confirmation is "yes", "speaking", "that's me" or the customer's full name. The first name on its own is not a confirmation: brothers, sons and fathers share first names.

**2. Third parties.** Never suggest a time yourself. Ask "When would be a good time to reach {first_name} {last_name}?" and work with what they say. If they cannot or will not name any time, do not push: close `not_reached` / `no_callback`. The late shift is now staffed, so the weekday callback window runs from 09:00 to **18:00** inclusive (not 17:30).

**3. Failed identity.** Do not send people to the mobile app: since the app reset, customers who failed our questions are locked out of it too. Say instead: "For your security I can't go any further on this call. Please visit any Freya Bank branch with photo ID." Then close as the Policy says.

**4. Stating the position.** Customers argue with the day count every time. Do not say how many days late a product is. Say the date it has been overdue since, which is today's date minus `days_late` calendar days. Example: on 13 October, a product 12 days late is "overdue since 1 October".

**5. "Next Friday".** Nobody on the phone means the Friday of next week. "Next <weekday>" and "this <weekday>" both mean the first such weekday after today. Whatever the customer says, say the calendar date back ("that is Friday 16 October") before you go on. This replaces ACP 6.8.

**6. Vague periods.** If the customer gives no exact day after the one extra question, propose the product's payday date (ACP 6.4), not the deadline. Most of them mean payday anyway. This replaces the last sentence of ACP 6.7.

**7. Part-paid.** If a customer says they have already paid part of the overdue amount on a product, take their word for the figure. The remainder (past-due amount minus what they say they paid) becomes the full amount for that product for the rest of the call: you ask for the remainder, and if the floor is higher than the remainder, the floor is the remainder. If what they paid covers the whole past-due amount, it is the "already paid" case of ACP 10.4.

**8. Notes on every call.** The records team needs a note on every product that ends without an arrangement, including on calls with only one product. So `add_note` is used on single-product calls too, exactly as on multi-product calls. This replaces the last sentence of ACP 11.1.

**9. Late band.** The floor keeps the two attempts of ACP 6.2 for the late band. The late customers are where the money is.

**10. Personal loans.** The personal loan floor is the instalment amount rounded up to the whole euro¹. The rest of ACP 7 stands.

Ruth

---

¹ Never more than the past-due amount: if the rounded instalment is above the past-due amount, the floor is the past-due amount.
