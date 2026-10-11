# Clear Start campaign — tool codes

Issued by Ops Training, v2, Thursday 8 October 2026. For use with the tool specification (openapi.json). Codes are case-sensitive. This list names codes; the rules are in ACP 2026/3 and the instructions that amend it.

## close_call

| outcome | reason | used when |
|---|---|---|
| `promise` | — (send no reason) | at least one arrangement recorded (`create_promise` ok) and no transfer |
| `paid` | — (send no reason) | no arrangement recorded and every product ended `paid` |
| `transferred` | `restructuring` | plan / lower instalments / payment holiday, call has at least one loan |
| `transferred` | `human` | customer asked for a person after verification and insisted |
| `transferred` | `support` | difficult circumstances, customer accepted customer support |
| `no_promise` | `refused` | see "no_promise reason" below |
| `no_promise` | `hardship` | see "no_promise reason" below |
| `no_promise` | `dispute` | see "no_promise reason" below |
| `no_promise` | `service_error` | see "no_promise reason" below; also `get_account` failed twice |
| `not_verified` | `failed` | wrong-answer limit reached |
| `not_verified` | `declined` | security questions declined, a person asked for twice before verification, or "do not want to talk" twice before verification |
| `not_reached` | `callback` | callback booked for the customer |
| `not_reached` | `no_callback` | no slot inside the window, no time named, or the booking failed twice |
| `not_reached` | `wrong_number` | number is not the customer's |
| `not_reached` | `deceased` | customer has died |
| `not_reached` | `unclear` | person on the line not confirmed after the second ask |

**no_promise reason.** Every product that ended without an arrangement has a note. Take the products whose note is not `paid`; the reason is the note reason of the one with the largest past-due amount (equal amounts: the one earlier in call order). With a single product this is simply that product's note reason. The one exception is a failed `get_account` (no products known, no notes): `service_error`.

A transfer always closes as `transferred`, even after recorded arrangements. Exactly one `close_call` per call, and it is the last tool call.

## add_note

One note per product that ends without a recorded arrangement, on every call, whether it has one product or three. Written when the product ends. Not written for products that had not ended when a transfer was asked for.

| reason | the product ended because |
|---|---|
| `refused` | no persuasion attempt left; the deadline was refused with no attempt left; or the customer said twice they do not want to talk |
| `hardship` | difficult circumstances, customer declined customer support |
| `dispute` | the customer disputes the product |
| `paid` | the customer says the past-due amount is already paid |
| `service_error` | `create_promise` failed twice on this product, or the product was not reached because of such a failure |

The `text` field is optional; one short line of free text is welcome.

## transfer_to_agent queues

| queue | for |
|---|---|
| `restructuring` | payment plan, lower instalments, payment holiday (loans only) |
| `general` | customer asked for a person (after verification) |
| `support` | difficult circumstances |

## verify_identity fields

| field | asked |
|---|---|
| `date_of_birth` | first, sent as `YYYY-MM-DD` |
| `phone_last4` | second, four digits |

## Product wording

| get_account `type` | say | call order |
|---|---|---|
| `car_loan` | "car loan" | 1st |
| `personal_loan` | "personal loan" | 2nd |
| `credit_card` | "credit card ending {card_last4}" | 3rd |
