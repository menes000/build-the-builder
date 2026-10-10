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
- `multi_product.enabled` is true only when the brief says a customer can be late on more than one product.
- Texts the agent must say verbatim (first sentence, sympathy sentence, the sentence after a recorded promise) must be quoted exactly.
- When the brief only describes the opening sentence (who is calling, the call is recorded) rather than quoting it, write it as "... and we record this call." Avoid the word "recorded" in the opening: the transcript judge associates that word with recording a promise.
- Fields described as "the exact sentence the agent says" (`after_failed_text`, `special.*.say`, `debt_intro_sentence`, `deceased_sentence`, `after_record_sentence`, `first_sentence`) must be the words the agent will speak, first person, no quotes, no "Say that ..." or "Tell the customer ...". If the brief only describes the content, write the sentence yourself from that content.
- `debt_intro_sentence` names the team and the purpose exactly as the brief words them (e.g. collections team / arrears team, late payment / overdue payment).
- Do not fill `tools`: the builder reads them from the tool API file.

## Output
Write the JSON to the output path you were given. Output only valid JSON that satisfies the schema; no comments, no markdown. If a field does not apply, give the schema's default (an empty list, empty string, or false), never null.
