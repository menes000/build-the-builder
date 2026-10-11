From: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
To: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
Cc: Signe Ahlberg (Compliance) <s.ahlberg@freyabank.example>; Ruth Okafor (Collections Team Lead) <r.okafor@freyabank.example>
Date: Fri, 2 Oct 2026 09:12
Subject: Clear Start campaign - open points on ACP 2026/3 before we build

Ingrid,

We are building the automated caller for Clear Start from ACP 2026/3 and the tool specification. A few points where the floor tells us the Policy no longer matches practice:

1. Card floor. The minimum_payment on a lot of cards is tiny (3 percent of the balance on the older products). Is that really the floor we want?
2. Car loans. Retail Credit said something about partial payments on car loans and the repossession rules. Does the instalment floor in 7.2 still apply?
3. A customer who asks for a person before we have verified them. The Policy transfers after one "can I help first". The fraud team is not happy with transferring unverified callers.
4. Payment plan requests on credit cards. As far as we know the restructuring team only takes loans.
5. A customer who says in one breath that they lost their job and want lower instalments. 10.8 sends them down the difficult-circumstances route. Is that right?
6. Closing a multi-product call with no arrangement. 12.3 takes the reason of the first product in call order. Ops say that hides the big ones.
7. Attempts per band. Any change?

We were also thinking of asking "can you pay all of these today?" once at the start for customers with several products, to save time. OK?

Thanks,
Tomasz

---

From: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
To: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
Cc: Signe Ahlberg (Compliance); Ruth Okafor (Collections Team Lead)
Date: Fri, 2 Oct 2026 15:40
Subject: RE: Clear Start campaign - open points on ACP 2026/3 before we build

Tomasz,

In order. These replace the Policy where they differ.

1. Card floor: 30 percent of the past-due amount, rounded DOWN to the whole euro. That replaces minimum_payment as the card floor. Loans are not affected by this point.

2. Car loans: I am waiting for Retail Credit. You will have it on Monday.

3. Unverified callers asking for a person: no transfer before identity is verified. Say that once identity is confirmed you can put them through, or that they can call the number on their statement, and go back to the question. If they ask for a person again instead of answering, close not_verified / declined. After verification, 10.5 stands as written.

4. Correct, there is no restructuring for credit cards. If every product on the call is a credit card, a request for a plan, lower instalments or a payment holiday is not transferred. Say: "A payment plan for a credit card can't be arranged on this call." and treat the request as a flat refusal on the card you are discussing. If the call has at least one loan (personal or car), a plan request transfers the whole call to restructuring as 10.2 says, whichever product you are on and whether or not the loan has already been dealt with.

5. In a call with at least one loan, the plan request comes BEFORE difficult circumstances: the restructuring team looks at hardship as part of the plan. So job loss plus lower instalments goes to restructuring. In a call with only credit cards, the order in 10.8 stands.

6. Agreed. With no arrangement recorded, and not every product paid, close no_promise with the reason of the product with the LARGEST past-due amount among the products that did not end paid. Equal amounts: the one earlier in call order. This replaces the last line of 12.3.

7. Attempts: as the Policy for now. Monday.

And no to the combined question. One product at a time, as 8.1 says.

Ingrid

---

From: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
To: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
Cc: Signe Ahlberg (Compliance); Ruth Okafor (Collections Team Lead); Retail Credit
Date: Mon, 5 Oct 2026 10:05
Subject: RE: RE: Clear Start campaign - open points on ACP 2026/3 before we build

Tomasz,

The two I owed you.

Car loans. Retail Credit confirms: on a car loan we arrange the FULL past-due amount only. There is no floor and no partial amount on a car loan. If the customer says the full amount is too much, or offers less than the full amount, say "For a car loan I can only arrange the full overdue amount." and treat it as a flat refusal. The attempts on a car loan are therefore both for the full amount: attempt 1 on the payday date, attempt 2 (where the band has one) on the deadline. If those two dates are the same day, there is no attempt 2.

Attempts. The late band (36 to 60 days) gets ONE attempt, not two. Early stays at one, mid stays at two.

Ingrid

P.S. Facilities have just told me the branches are closed on Monday 2 November this year (network cut-over). Add it to the holiday list in 6.1 for every date rule: arrangement dates, business-day counting and callbacks.

---

From: Signe Ahlberg (Compliance) <s.ahlberg@freyabank.example>
To: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
Cc: Ingrid Falk (Head of Collections); Ruth Okafor (Collections Team Lead)
Date: Wed, 7 Oct 2026 08:50
Subject: Clear Start - wording and vulnerable customers (Compliance instruction)

Tomasz,

Compliance instruction for the Clear Start caller. It applies over the Policy, the mails and the floor memo.

1. Words. The caller never says "debt" or "promise" to the customer, at any point of the call. Say "overdue amount" and "payment arrangement". Before identity is verified, "balance" and "owe" are added to the words in ACP 2.2.

2. No totals. With several products, never add the amounts together or state a total. One sentence per product.

3. Fees. After the products have been stated and before the first question about paying, say once: "Freya Bank does not charge any fee for setting up a payment arrangement."

4. After each arrangement that is recorded (ok: true), say: "That payment arrangement is now set up. You will receive a text message with the details." This replaces ACP 9.5, which uses a word we no longer use.

5. Difficult circumstances. The list in ACP 10.1 is extended by: separation or divorce, and caring for a seriously ill family member. The sympathy sentence is fixed: "I'm sorry to hear that. Would you like me to put you through to our customer support team?" Nothing else is said about the circumstances.

Regards,
Signe Ahlberg
Compliance

---

From: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
To: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
Cc: Signe Ahlberg (Compliance); Ruth Okafor (Collections Team Lead); Fraud Operations
Date: Wed, 7 Oct 2026 17:20
Subject: Clear Start - three more changes

Tomasz,

Three more, after today's meeting with Fraud Operations and the core-banking team.

1. Identity: the limit is TWO wrong answers in total, not three. The second wrong answer ends the check, whichever question it falls on. Ignore whatever the tool says about answers left; it still counts to three. The day_month_swapped retry and a partial date stay free.

2. Callbacks: the weekend team is cancelled. No Saturday callbacks at all; strike the Saturday line in ACP 3.2.

3. create_promise. If it fails twice for the same product (the first try plus the one retry), the core system is down and further tries are pointless. Say it could not be set up, and do NOT go on to the other products: the failed product and every product not yet dealt with end with service_error (one note each). Arrangements already recorded on the call stay. Then close as 12.3 says. This replaces the last part of ACP 9.4.

Ruth's memo of yesterday is fine for the floor. Where it says something different from Signe or from me, the order in ACP 0.2 decides.

Ingrid

---

From: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
To: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
Cc: Ruth Okafor (Collections Team Lead)
Date: Thu, 8 Oct 2026 11:02
Subject: RE: Clear Start - three more changes

Ingrid,

Thanks. Two loose ends:

a) ACP 6.1 still lists Friday 23 October for the branch refit. Is that still on? It moves a lot of payday dates.
b) The 30 percent card floor rounded down sometimes comes out below the contractual minimum_payment (a card at 2,125.10 past due with a 637.50 minimum gives 637). Retail Credit asked whether we can arrange less than the contractual minimum.

Tomasz

---

From: Ingrid Falk (Head of Collections) <i.falk@freyabank.example>
To: Tomasz Wren (Voice Automation Lead) <t.wren@freyabank.example>
Cc: Ruth Okafor (Collections Team Lead); Signe Ahlberg (Compliance)
Date: Fri, 9 Oct 2026 09:30
Subject: RE: RE: Clear Start - three more changes

a) The refit has been postponed to next year. Friday 23 October 2026 is an ordinary business day. Take it off the list.

b) No, we cannot. The card floor is the HIGHER of the two: 30 percent of the past-due amount rounded down to the whole euro, or minimum_payment. So 637.50 in your example.

Ingrid
