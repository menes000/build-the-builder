# Task: revise a CallSpec after a practice test

The phone agent built from the CallSpec below was tested against simulated customers. Some failed. You get, for each failure, what the bank's ledger should have shown, what it showed, the judge's explanation, and the transcript. Your job is to change the CallSpec so the agent follows the brief on these points next time, without breaking anything else.

## What you may change
- Texts the agent reads: `extra_rules` lists, rule sentences (`*_rule`, `*_text`, `say`, `ask`, `instruction`, `explain_once_text`, `sympathy_rule`, `stop_rule`, `attempt_rules`), descriptions.
- Add a rule to the `extra_rules` of the section that matches the failure. Write it as a precise instruction for the agent, in the brief's own terms.

## What you must NOT change
- Outcome and reason values, queues, holidays, band numbers, time windows, amounts, field names, `tools`, `field_map`, `multi_product.enabled`. These come from the brief and the tool API; if you believe one is wrong, say so in `source_notes` instead of changing it.
- Anything about a specific customer in the failures (no names, no dates, no amounts of these customers). Rules must be general.
- Do not weaken a rule to make a failure pass. If the judge misread the brief, add a `source_notes` entry and leave the rule.

## How to decide
1. Read the brief rule the judge refers to. Find where the agent deviated in the transcript.
2. If the CallSpec already states the rule, make it more explicit: when it applies, what to say, what to call, and what NOT to do (the thing the agent did).
3. If the failure came from a technical error, a platform outage, or a judge reading that contradicts the brief, change nothing for it and explain in `source_notes`.
4. Keep every other field exactly as it is.

## Output
Write the complete revised CallSpec JSON (same schema) with the Write tool to the output path you were given. Valid JSON only, no comments. Add one `source_notes` entry per failure: what you changed, or why you changed nothing.
