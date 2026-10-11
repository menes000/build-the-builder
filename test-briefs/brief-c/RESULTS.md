# Brief C rehearsal (11 Oct 12:30–12:45) — an "unseen" raw brief through the whole pipeline

Build: Dora's builder from `FREYA/` (scratch copy, claude login), `python3 builder/build.py brief-c brief-c/openapi.json`: 62 s,
extraction 59 s / $0.51, 31 nodes, 10 tools. Workflow cf3be82c, agent 3dfb3d55. Trace: build-trace.log.

Extraction vs the memo: all 6 memo items in the CallSpec (two identity questions after memo item 6, callback 09:00–17:30, new holidays,
3 wrong answers, new text-message sentence, serious band 1 attempt). `rule_diff.py`: 0 differences, field_map vs openapi clean.

Cases: `cases.json`, 31 generated from the CallSpec (no hand-typed value). Skipped: identity-stage human request (no such rule in the brief).

Local run (Gemini agent, fake bank with openapi validation, gpt-5.4-mini judge), 3 hard cases × 2 reps: 6/6 PASS, 50 s.
| case | title | local | Freya |
|---|---|---|---|
| TC-23 | wants a date after the deadline, refuses the deadline | 2/2 | pending (platform 504) |
| TC-14 | promise recorded, then asks for a human | 2/2 | pending |
| TC-25 | changes the amount at the read-back | 2/2 | pending |

Observation for Dora (TC-25 rep 1): to a bare "I cannot pay today" the agent asked "When can you pay the full amount?" instead of
proposing attempt 1 (Friday 16 October, full amount). Passed here because the customer then named a date; a jury check
"attempt 1 proposes X on Friday" would fail. TC-23 handled the same situation correctly, so it is model variance; confirm on Freya.
