# Task: turn a bank's collections brief into a CallSpec

You are given one or more brief files from a bank. Together they specify how an outbound collections phone agent must behave. Your job is to read ALL of them, completely, and fill in a JSON document that follows the CallSpec JSON schema exactly.

## How to read the brief
- Read every file from top to bottom. Do not skim and do not search by keyword: most failed calls come from one rule that was skipped.
- When several files are given, later files build on earlier ones. A later file replaces a rule only where it says so; every other rule of the earlier file still applies.
- When the material is raw (emails, memos, policy extracts, code lists): a dated later decision overrides an earlier one. Write what you resolved and why into `source_notes`.
- Take every number, date, name, threshold, outcome value and reason value from the brief. Never invent one, never take one from memory of another bank's rules.
- Every rule must land somewhere: in the matching field if one exists, otherwise in the `extra_rules` list of the closest section, in the brief's own words (shortened is fine, meaning unchanged). Nothing may be dropped.
- Outcome and reason strings must be copied exactly as the brief writes them (they go into an API call).
- `holidays` are ISO dates. `weekend_days` are Python weekday numbers (Monday=0 ... Sunday=6) that are not business days.
- For each band, set `deadline_business_days_after_today` when the deadline is "the Nth business day after today"; set `deadline_calendar_days_after_today` when it is "N (calendar) days after today"; set neither when the rule has another form and describe it in `deadline_rule`.
- `persuasion.attempt1_date_kind`: classify the attempt-1 date rule; use `other` only when none of the kinds fits, and then describe it fully in `attempt1_date_rule` and `attempt_rules`.
- `multi_product.enabled` is true only when the brief says a customer can be late on more than one product.
- Texts the agent must say verbatim (first sentence, sympathy sentence, the sentence after a recorded promise) must be quoted exactly.
- When the brief only describes the opening sentence (who is calling, the call is recorded) rather than quoting it, write it as "... and we record this call." Avoid the word "recorded" in the opening: the transcript judge associates that word with recording a promise.
- Fields described as "the exact sentence the agent says" (`after_failed_text`, `special.*.say`, `debt_intro_sentence`, `deceased_sentence`, `after_record_sentence`, `first_sentence`, `identity.decline.explain_once_text`) must be the words the agent will speak, first person, no quotes, no "Say that ..." or "Tell the customer ...". If the brief only describes the content, write the sentence yourself from that content.
- `debt_intro_sentence` names the team and the purpose exactly as the brief words them (e.g. collections team / arrears team, late payment / overdue payment).
- Do not fill `tools`: the builder reads them from the tool API file.

## Output
Write the JSON to the output path you were given. Output only valid JSON that satisfies the schema; no comments, no markdown. If a field does not apply, give the schema's default (an empty list, empty string, or false), never null.


## Rule variants that have their own field (use the field, never only the text)
- A floor that is a PERCENTAGE of some field: `products[].floor_percent` applies to the value of `floor_field`
  (`past_due` for "x % of the overdue amount", `instalment_amount` for "half the instalment"); `floor_round_up_to_whole`
  if it rounds up to a whole unit. The text in `amounts.floor_rule` must say the same.
- A callback window in CALENDAR days or one that allows Saturdays: `third_party.callback.calendar_days`, `saturday_allowed`,
  with `max_business_days_ahead` as the number of days.
- The exact sentence spoken after the name is confirmed and before the first security question (for example a recording
  notice): `identity.intro_text`.
- With several products and no promise, a closing that follows the first product's note only: `multi_product.closing_by_first_product`.
- A weekend/holiday date where both the business day before and after are offered: `dates.weekend_named_offer = "both"`.
- create_promise with NO retry on failure: `confirm.max_tries_on_failure = 1`.
- `amounts.today_question` / `multi_product.today_question_all` may contain the placeholders {amount}, {total}, {today},
  {tomorrow}, {deadline}; the code fills them.
- A band deadline in CALENDAR days: `deadline_calendar_days_after_today`; in business days: `deadline_business_days_after_today`.
  Exactly one of the two per band; the validator rejects a band with neither.
- The exact wording of the "can you pay today" question, if the brief dictates it: `amounts.today_question`
  (one product) and `multi_product.today_question_all` (all products at once).
- A callback allowed on the next business day OR the one after it: `third_party.callback.max_business_days_ahead = 2`.
- A first refusal of the security questions that closes the call at once, without an explanation: `identity.decline.explain_first = false`.
- More than one retry of create_promise on a technical failure: `confirm.max_tries_on_failure` (3 = two retries).
- A ranking of note reasons for the closing reason with several products: `multi_product.no_promise_reason_priority`.
- A weekend/holiday date that is moved to the LAST business day before it: `dates.weekend_named_offer = "previous_business_day"`.
- A vague period that falls back to the attempt-1 date instead of the deadline: `dates.vague_period_fallback = "attempt1"`.
Every number or choice that appears in a text rule must also be in its structured field. If a rule fits no field at all,
put it in the nearest `extra_rules` list and say so in `source_notes`.

## When a quantity fits no field at all
Set `amounts.floor_mode`, `persuasion.attempt1_mode` or `third_party.callback.day_mode` to "text" ONLY when the brief's
rule for the floor, the attempt-1 date or the allowed callback days cannot be expressed with the structured fields
above. The code then stops computing that quantity and the agent applies the rule text (`floor_rule`,
`attempt1_date_rule`, `callback.day_rule`), which must then state the rule completely. Prefer the fields whenever they fit.

## Time-of-day greeting and per-question identity limits
- If the opening sentence starts with a greeting that depends on the time ("Good morning" before 12:00, "Good afternoon"
  after), write `{greeting}` in `opening.first_sentence` and fill `opening.greetings` with start times.
- If wrong security answers are counted per question, set `identity.max_wrong_per_question`; `identity.max_wrong_total`
  stays the total limit the brief states.

- `multi_product.per_product_question_is_attempt1`: true when, after the one question for all products, the first
  question for each product already counts as persuasion attempt 1; false when the brief says it is not an attempt.

- Language. `language` is the language the calls are held in (the brief or its example conversations say it; default
  English). When it is not English: every sentence the agent says that you write into the CallSpec (opening, questions,
  confirmation and closing sentences, examples of what the customer may say) is in that language, in the wording and tone
  of the brief's example conversations if it has any; and fill `phrases` with every key listed in its description,
  translated into that language with every {placeholder} kept. Field names, enum values, outcome and reason codes stay
  exactly as the tool API writes them. When the calls are in English, leave `phrases` empty.
- A folder of loose material can include a README that says what each document is, test customers, a Q&A and example
  conversations: read all of them. Rules come from the brief, its announcements and the Q&A (a later announcement or
  answer overrides an earlier text); the example conversations show the expected wording and order, and the test
  customers show the data the agent will see.
