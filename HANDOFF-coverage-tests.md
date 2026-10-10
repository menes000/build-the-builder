# Handoff: coverage test set for the Freya collections agent

For: Mehmet (and his Claude). From: Dora's builder repo, 10 Oct 2026 evening.
Goal: write and run **our own practice customers** that cover the brief rules the organisers' 13 practice customers do not test. Deliverable: a case file and a runner, compatible with the organisers' tooling, plus a results table.

## 1. Where we are (read this first)

- Hackathon: "Build the Builder" (Freya x YC). We submit a **builder** that reads a bank brief and creates a phone agent on Freya. The jury runs our builder on two unseen briefs and tests the agents with hidden simulated customers, 3 runs each, a customer counts only if all 3 pass.
- Dora's builder is done and works end to end: `python3 -m builder.main <brief.md> --slot <name>` → Claude extracts a CallSpec → a deterministic compiler emits the workflow JSON → dry run → published on Freya → export + trace. Read `README.md` for the layout and `NOTES.md` for every measurement and decision so far.
- Scores so far (organisers' practice set, Brief A agent): 10/10 on 3 consecutive runs; 10/10 in three speaking styles; Brief B (multi-product) 3/3 on clean runs. The organisers' own example builder scores 10/10 on A but 0/3 on B.
- The platform (staging) was unstable this evening: the Python sandbox ("snekbox") that runs code nodes and tool hooks went unreachable several times. Any run whose judge reasons mention `snekbox` or "technical error" is invalid. `builder/test/scan.py` flags that automatically.

## 2. How a test works (the organisers' mechanism, which we reuse)

1. A **case** describes one simulated customer: who they are, a `script` (what they do on the call), `checks` (sentences a judge model verifies in the transcript), and `expected` (what the bank's ledger must contain afterwards: outcome/reason, promises, notes, callbacks, transfers).
2. `kit/tools/run_cases.py <agent_id> --cases <file>` turns each case into a Freya **persona** (`persona_for()` builds the prompt from `script` and the identity answers), asks the bank mock for a fresh **session** (`POST /v1/practice/sessions {"case": <id>}` returns `customer_id`, names, `now`), starts one Freya simulation in chat mode, waits, then scores: ledger via `tools/score.py` (`score_ledger`), conversation via the persona's judge verdict.
3. The bank mock only knows the organisers' case ids (`PUB-01`..`PUB-13`). It rejects unknown ids (`unknown practice case`). **So every one of our cases must borrow an existing PUB account** (same name, identity answers, product data) and only change the script, checks and expected ledger. The mock does not enforce the brief, so a borrowed account can be used for any scenario.
4. The practice `now` is always `2026-10-14T11:00` (a Wednesday). Holidays: 2026-10-26, 11-11, 11-26, 12-25, 2027-01-01. Early band (1–7 days late) deadline = 12th business day after today = **2026-11-02**; late band (8–45) deadline = 7th business day = **2026-10-23**. Last business day of this week = Fri 2026-10-16.

Accounts you can borrow (all from `kit/public-test-set.json`):

| PUB | Customer | DOB / phone4 | Product | past_due | days_late | band | floor |
|---|---|---|---|---|---|---|---|
| 01 | Mr Daniel Reyes | 1988-03-14 / 4471 | credit card 4821 | 420 | 6 | early | 126 |
| 02 | Ms Maria Costa | 1979-11-02 / 0358 | personal loan | 310.5 | 11 | late | 103.5 |
| 03 | Mr Owen Park | 1992-07-21 / 6630 | credit card 0377 | 95 | 4 | early | 28.5 |
| 04 | Ms Lena Hoffmann | 1984-01-30 / 2219 | car loan | 1250 | 14 | late | 400 |
| 05 | Mr Tomas Novak | 1990-09-09 / 8846 | personal loan | 780 | 21 | late | 260 |
| 06 | Ms Priya Nair | 1986-05-17 / 1502 | credit card 1903 | 2125.1 | 12 | late | 637.5 |
| 07 | Mr Samuel Ortiz | 1975-12-05 / 7093 | personal loan | 540 | 5 | early | 180 |
| 08 | Ms Hannah Schmidt | 1993-04-28 / 3317 | credit card 5512 | 180 | 5 | early | 54 |
| 09 | Mr Victor Ionescu | 1981-08-11 / 5560 | personal loan | 2100 | 28 | late | 700 |
| 10 | Ms Grace Lin | 1989-02-23 / 9904 | credit card 7740 | 365 | 8 | late | 109.5 (create_promise fails once) |

## 3. What to build

### 3a. `coverage-cases.json`
Same shape as `kit/public-test-set.json`, plus one field `session_case` (the PUB id to borrow). Example:

```json
{
  "id": "OUR-01", "session_case": "PUB-03", "brief": "A", "family": "Wrong number", "level": "medium",
  "title": "The number does not belong to the customer",
  "variables": {"first_name": "Owen", "last_name": "Park", "title": "Mr", "now": "2026-10-14T11:00"},
  "identity": {"date_of_birth": "1992-07-21", "phone_last4": "6630"},
  "products": [{"type": "credit_card", "card_last4": "0377", "past_due": 95.0, "days_late": 4, "minimum_payment": 28.5}],
  "third_party": true,
  "script": "The person who answers says there is no Owen Park at this number and that the caller has the wrong number. Does not know him.",
  "expected": {"outcome": "not_reached", "reason": "wrong_number", "promises": [], "notes": [], "callbacks": [], "transfers": []},
  "checks": ["the agent does not say why it is calling and names no product, amount or debt", "verify_identity and get_account never called", "closed as not_reached / wrong_number"]
}
```

Rules for writing cases (from Brief A, `kit/briefs/brief-a.md`, read all 47 rules):
- `script` is what the simulated customer does, in the third person; the persona generator turns it into first-person instructions. Keep facts exact (dates, amounts). For third-party cases set `"third_party": true` (the persona then does not know the security answers).
- `checks` are the sentences the judge verifies; copy the brief's wording. 3–4 per case.
- `expected` must be computed from the brief for the borrowed account (deadline, floor, business days). Dates ISO. `reason` is `null` for promise and paid.
- Cover these rule families (one case each unless noted), none of which the PUB set tests:

| # | Rule | Borrow | Expected |
|---|---|---|---|
| 1 | Wrong number (rule 8) | PUB-03 | not_reached / wrong_number |
| 2 | Deceased (rule 9): "I am sorry for your loss." and nothing else | PUB-07 | not_reached / deceased |
| 3 | No clear confirmation after two asks (rule 3): "Hello?", "who is this?", "go ahead" | PUB-08 | not_reached / unclear |
| 4 | Callback outside the window twice (rule 7): Sunday evening, then tomorrow 20:00 | PUB-02 | not_reached / no_callback, no callback booked |
| 5 | Declines the security questions twice (rule 15) | PUB-09 | not_verified / declined, debt never stated |
| 6 | Day/month swapped (rule 13): says DOB as "12/05/1975"; after the hint says "5 December 1975"; then pays in full today | PUB-07 | promise 540 on 2026-10-14; the retry does not count as wrong |
| 7 | Amount below the floor, then accepts the floor for Friday (rule 27) | PUB-06 | promise 637.5 on 2026-10-16; floor offered once, "rest stays overdue" |
| 8 | Customer's own amount inside floor..full, Monday 19 Oct (rule 27) | PUB-04 | promise 800 on 2026-10-19, no counter-offer |
| 9 | Dispute: "I closed that card two years ago" (rule 40) | PUB-08 | no_promise / dispute, no argument |
| 10 | Asks for a human, insists (rule 42) | PUB-01 | transfer general → transferred / human; agent asked once if it can help |
| 11 | Hardship, accepts the support team (rule 32) | PUB-05 | transfer support → transferred / support; one sympathy sentence; no persuasion |
| 12 | Says twice they do not want to talk, after verification (rule 45) | PUB-09 | no_promise / refused |
| 13 | Promise recorded, then insists on a human (rule 46 last paragraph) | PUB-01 | promise 420 on 2026-10-14 AND transferred / human |
| 14 | Late band, refuses today, refuses attempt 1 (full on Fri 16), refuses attempt 2 (floor 260 on 23 Oct) (rules 30–31) | PUB-05 | no_promise / refused; exactly two attempts, attempt 2 = floor on the deadline, no third offer |
| 15 | Vague period ("when my salary comes"), no exact day when asked, accepts the proposed deadline (rule 21) | PUB-02 | promise 310.5 on 2026-10-23; asked once for the exact day |
| 16 | Names a Saturday (17 Oct), accepts the next business day (rule 20) | PUB-01 | promise 420 on 2026-10-19 |
| 17 | "Next Friday" said on Wednesday 14 Oct = Fri 23 Oct (rule 22), early band so allowed | PUB-03 | promise 95 on 2026-10-23 |
| 18 | Asks "is this a scam?" before confirming, then confirms and pays today (rule 43, rule 3) | PUB-08 | promise 180 on 2026-10-14; the scam answer given; the following ask counted as the second ask |

(Rule 37 "service fails twice" cannot be simulated: the mock only fails once, on PUB-10.)

### 3b. `run_coverage.py`
Do not edit the kit. The simplest runner reuses the kit's code with one change, the session lookup:

```python
# builder/test/run_coverage.py
import pathlib, sys
KIT = pathlib.Path(__file__).resolve().parents[2] / "kit"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))
src = (KIT / "tools" / "run_cases.py").read_text().replace(
    'http("/v1/practice/sessions", {"case": c["id"]})',
    'http("/v1/practice/sessions", {"case": c.get("session_case", c["id"])})')
sys.argv[0] = "run_cases.py"
exec(compile(src, "run_cases.py", "exec"), {"__name__": "__main__", "__file__": str(KIT / "tools" / "run_cases.py")})
```

Run: `source env.sh && python3 builder/test/run_coverage.py <agent_id> --cases builder/test/coverage-cases.json --out results/coverage.json`
(`--brief` is a filter by the case's `brief` field; omit it or set `brief` on every case.)

### 3c. After a run
- `python3 -m builder.test.scan results/coverage.json` → flags loops, silence, snekbox, invalid close_call, 'recorded' before success. Discard runs with `PLATFORM` flags.
- For each FAIL read the transcript: `freya.get_call(call_id)["messages"]` (call ids are in the `--out` JSON). Classify: platform / judge quirk / agent behaviour / brief rule missed. Report the class, not just the case.
- Run the set at least twice (`--reps 2`); a case that passes once can fail the next time.

## 4. Practicalities

- One Freya workspace runs **one simulation at a time**; a second `run_cases` waits. Coordinate who is running what. Best: Dora invites Mehmet to the same workspace (Settings → members) so both keys see the same agents; otherwise Mehmet runs the builder in his own workspace to create an agent (`python3 -m builder.main kit/briefs/brief-a.md --slot coverage-a`).
- `FREYA_BANK_TEAM_KEY` must be the same string for the whole team (it namespaces the bank ledger). Get it from Dora, never commit it. `env.sh` is git-ignored.
- Never publish (save_workflow) a slot while a simulation on that agent is running: live calls freeze.
- Agent ids right now: Brief A agent `a1230ea7-d704-4c24-8b07-d44e3f1d9b8a` (workflow 76b6ef99, slot `ours-a`, version 5); Brief A+B agent `c95855d9-8457-4845-b92a-07d06797f1d1` (slot `ours-ab`, version 9).
- Freya platform docs that matter: `kit/docs/workflow-format.md`, `kit/docs/tools-and-code.md`, `kit/docs/api.md`. Bank tool API: `kit/tools/openapi.json`.
- Output we want back: `builder/test/coverage-cases.json`, `builder/test/run_coverage.py`, and a short results table (case, pass/fail per rep, failure class, one-line evidence). Put raw JSON under `results/` (git-ignored) and the table in `NOTES.md` under a "Coverage set" heading.

## 5. What NOT to do

- Do not change files under `kit/` (organisers' kit, must stay pristine) or `builder/compile/` (Dora is iterating there); send findings instead.
- Do not weaken a check or an expected value to make a case pass. If a check seems wrong, re-read the brief rule and note the disagreement.
- Do not write Brief A values into the compiler or prompts; the final briefs differ and that is against the rules.
