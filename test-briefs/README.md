# test-briefs: dress rehearsals for the hidden briefs

`brief-c/` = Dora's raw-material rehearsal brief (mail + memo + code list, 11 Oct) with ONE change: memo item 6 drops the postcode
question (the organisers' bank mock only knows date_of_birth and phone_last4, so an agent for this brief can also be tested on Freya).
`openapi.json` is the standard tool API (mock-compatible). `openapi-renamed.local-only.json` renames fields (payment_amount, promise_date,
team, result, code, callback_time); it is for the local fake bank only, the real mock would reject those names.

Flow: Dora builds from this folder (python3 builder/build.py test-briefs/brief-c test-briefs/brief-c/openapi.json) -> callspec + export here
-> tester generates cases into cases.json here -> 3 hard cases locally (Gemini) -> the same 3 on Freya (run_coverage.py) -> compare.
