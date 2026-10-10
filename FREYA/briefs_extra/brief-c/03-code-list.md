# Outcome code list for close_call (Ops, v3, 2026-09-22)

| outcome | reason | when |
|---|---|---|
| promise | (none) | at least one promise recorded |
| paid | (none) | customer says already paid |
| transferred | plans | payment plan / lower instalments |
| transferred | human | customer insisted on a person |
| transferred | hardship_desk | hardship, accepted the desk |
| no_promise | refused | attempts exhausted, or twice "don't want to talk" after verification |
| no_promise | hardship | hardship, declined the desk |
| no_promise | disputed | debt or product disputed |
| no_promise | system_error | create_promise failed twice |
| not_verified | failed | wrong-answer limit reached |
| not_verified | refused_check | declined the security questions |
| not_reached | callback | callback booked |
| not_reached | no_slot | no callback inside the window |
| not_reached | wrong_number | number is not the customer's |
| not_reached | deceased | customer passed away |
| not_reached | not_confirmed | identity of the person on the line not confirmed after two asks |

Notes: outcomes promise and paid are sent without a reason. Transfer after a recorded promise: close as transferred with the transfer's reason. add_note is not used in this campaign.
