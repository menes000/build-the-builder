# close_call and add_note codes — Q4 early arrears campaign

Issued by Ops Training, v4, 6 October 2026. Use these codes with the tool specification (openapi.json). Names are case-sensitive.

## close_call

| outcome | reason | when |
|---|---|---|
| promise | — (no reason sent) | at least one promise recorded on the call, and no transfer afterwards |
| paid | paid | customer says the overdue amount is already paid; with several products, every product noted paid |
| transferred | restructuring | payment plan, payment holiday or lower instalments requested |
| transferred | human | customer asked for a person |
| transferred | support | difficult circumstances, customer accepted the customer care team |
| no_promise | dispute | at least one product disputed, no promise recorded |
| no_promise | hardship | difficult circumstances, customer declined the customer care team, no promise recorded |
| no_promise | service_error | create_promise failed three times on a product, no promise recorded, no dispute or hardship |
| no_promise | refused | attempts exhausted, latest date refused, or the customer said they do not want to talk (after verification) |
| not_verified | failed | wrong-answer limit reached |
| not_verified | declined | customer declined the security questions or said they do not want to talk before verification |
| not_reached | callback | callback booked |
| not_reached | no_callback | no slot inside the callback window |
| not_reached | wrong_number | number is not the customer's |
| not_reached | deceased | customer has died |
| not_reached | unclear | person on the line not confirmed as the customer after three asks |

Notes

- `promise` is the only outcome sent without a reason. Every other outcome, including `paid`, carries the reason shown.
- When no promise is recorded and several products carry notes, the no_promise reason follows the priority dispute, hardship, service_error, refused. If every product is noted `paid`, close `paid` / `paid`.
- A transfer after a recorded promise closes as `transferred` with the transfer's reason, not as `promise`.
- Exactly one `close_call` per call. It is the last tool call.

## add_note (one per product that ends without a promise)

| reason | when |
|---|---|
| refused | attempts exhausted or latest date refused for this product |
| hardship | difficult circumstances raised, no promise on this product |
| dispute | this product disputed |
| paid | customer says this product is already paid |
| service_error | create_promise failed three times for this product |

Notes are written for every product without a promise, including before a transfer for the products already discussed. The `text` field is optional; a short free-text summary is welcome.

## Product wording

| get_account type | say |
|---|---|
| credit_card | "credit card ending {card_last4}" |
| personal_loan | "personal loan" |
| car_loan | "car loan" |

## Queues for transfer_to_agent

| queue | use |
|---|---|
| restructuring | payment plan, payment holiday, lower instalments |
| general | customer asked for a person |
| support | difficult circumstances |
