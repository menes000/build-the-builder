# Build the Builder: a builder that writes bank phone agents

Our entry for the **Freya × Y Combinator "Build the Builder"** hackathon (10–11 October 2026).

A bank hands over whatever it has about a phone call: a specification, mails, memos, meeting notes, a service contract, a flow drawing. Our **builder** reads that material and creates a working phone agent on Freya: steps, prompts, routes, code and tool calls. Nobody edits the agent by hand. One command in, one agent out, with a trace of every decision.

```bash
python3 FREYA/builder/build.py <case folder | zip | brief file> <mock_url | openapi.json>
```

---

## The idea

Writing a phone agent for a bank is slow because the rules are spread across documents that disagree with each other. Our builder does that reading and design work itself. It runs in two modes and picks one on its own:

| Mode | When it runs | What it does |
|---|---|---|
| **Template mode** | The call is a type the builder has a model for (outbound collections: identity check, debt, payment promise). | Claude fills a **CallSpec**, a fixed form of the bank's rules. A deterministic compiler then turns it into a Freya workflow. Every date, amount and limit is computed in code, never guessed by the model. |
| **Free-form mode** | A call type the builder has never seen. | Claude reads the whole case pack, resolves conflicts between the sources, writes a design and then the workflow. The builder checks the result and sends every problem back to Claude until Freya accepts it. |

The builder chooses the mode from the tool API: if the tools the template needs are missing, it switches to free-form mode. Nothing about any particular bank, brief or case is written into the code. Every rule, value and sentence comes from the documents at run time.

---

## How a build runs

```
case material (md, txt, pdf, docx, xlsx, zip)  +  tool API or service contract
   │
   ▼
0. READ        every file to text (pdftotext, docx/xlsx without extra tools); large files are cut, with a pointer for Claude
   │           no OpenAPI file in the pack? Claude writes one from the service contract
   ▼
1. PLAN        does the call fit the template?  ── yes ──►  TEMPLATE MODE
   │                                              no  ──►  FREE-FORM MODE
   ▼
   TEMPLATE                                       FREE-FORM
   ├─ EXTRACT  Claude → CallSpec                  ├─ DESIGN    Claude reads all sources, newest decision wins,
   ├─ COMPILE  CallSpec → workflow                │            writes a design note
   │           (code nodes for dates/amounts,     ├─ WORKFLOW  Claude writes the Freya workflow from the design
   │            hooks that check promises)        └─ CHECK     JSON · lint · code compiles · URLs only inside the
   └─ TEST+FIX practice customers → Claude                     tool API · Freya dryRun → problems back to Claude
               revises texts → recompile
   ▼
2. PUBLISH     save the agent on Freya (same slot, a new version), export it
   ▼
3. TRACE       start/end, every model call (model, purpose, time, cost), what was created, every test
```

---

## The final case

The hidden final case was a call type nobody had practised: an **inbound credit-card statement call in Turkish**. The phone menu has already identified the caller. The agent finds the right card, reads the statement debt in lira, dollars, euros and pounds, says when it is due, can move the statement week and can e-mail the statement PDF. Callers who want to pay or ask for a person are handed to an agent. The material came as mails, two versions of an analysis document, meeting transcripts, a service contract, an IVR prompt sheet, an FAQ and a flow drawing, and the sources do not always agree.

What the builder produced, in one run, with no hand edits:

- **A tool API** written from the bank's service contract: 7 services, with exact paths and field names.
- **A design note** (`FREYA/out/final.freeform.notes.md`) that lists the flow and **12 conflicts between the sources**, each resolved by "the latest decision wins": silence handling, the angry-caller limit, which card digits may be spoken, the once-a-year week change, the joint-card warning and more.
- **A 31-node Turkish workflow** (`FREYA/submission/final.workflow.json`) that Freya accepted on the first round:
  - Code nodes write every amount and date as exact Turkish text: amounts in words, kuruş, sent and peni, the right Turkish suffix, and "due date passed" or "statement cut today" decided from `now`.
  - A pre-hook maps the caller's card choice to the masked card number that `cards.list` returned, so the number is never rebuilt from what the caller said.
  - Write calls (`statement.week.change`, `statement.pdf.send`) run once, and only after an explicit yes.
  - 16 closing nodes, each with its own sentence and end reason, plus global routes for payment, dispute, third party, non-Turkish speech and requests for a person.

Agent `cc044dcc`. The full run, including the earlier attempts, is in `FREYA/traces/`.

**Our own mock of the bank.** The final case also asked for a mock of the bank's services. `mock/` is a Cloudflare Worker that serves the 7 services with the exact request and response shapes of the integration document and returns the stored answer, HTTP status included, for every test customer. `mock/check_mock.py` checks a deployed Worker against the test data.

---

## Testing without spending the platform

Freya allows one simulation at a time per workspace, and the platform was limited during the final. So we built a **local test bench** (`tester/`) that runs a whole test set in a few minutes, in parallel:

| Tool | What it does |
|---|---|
| `emulator.py` | Runs a Freya workflow JSON locally: routing, extraction, conversation, code nodes and hooks, and API calls. It reports any Freya feature it cannot emulate. |
| `fakebank.py` | A local copy of the bank API: every identity field, injected faults (`fail_first_n`), the wrong-answer limit, field-name mapping, and request validation from the OpenAPI file. |
| `cases_from_callspec.py` | Generates about 30 single-product and 7 multi-product customers from the CallSpec. Every date and amount in them is computed in code, from bands, deadlines, business days, holidays and floors. |
| `local_sim.py` / `local_test.py` | Runs the test set: PASS/FAIL per customer, the failed checks, flags (silent turns, repeated refusals, parallel tool calls) and the path taken. The builder can call it with `--local-test`. |
| `rule_diff.py` | A second model reads the raw brief on its own; the result is compared with the CallSpec field by field. |
| `run_coverage.py` | The official path: the kit's scorer on Freya, with retries on platform errors. |

**Calibration:** On 28 cases the emulator and the real Freya platform reached the same verdict 26 times. Both differences came from how the platform model behaves, not from the workflow. Our judge model and Freya's judge agreed on the same cases.

**Rehearsals on unseen briefs:** Before the final we wrote extra briefs ourselves (`test-briefs/`): C, D, E and F, including a messy multi-product one made of loose mails and memos, each with an answer key. We built each of them blind, as if they were the hidden brief. For example, Brief C built in 62 seconds, the extraction picked up all six items of the memo, and the rule diff found no differences.

---

## Repository

```
FREYA/               the builder
  builder/build.py     submission entry point
  builder/main.py      the run: read → plan → build → check → publish → trace
  builder/extract/     reading material, CallSpec extraction, contract → OpenAPI
  builder/compile/     CallSpec → workflow compiler, code generation, lint, self-check
  builder/freeform.py  free-form mode: design → workflow → checks → feedback rounds
  builder/test/        practice runs and the fix loop
  submission/          exported workflows (final.workflow.json is our entry)
  traces/              one trace per run
  out/                 everything a run wrote: OpenAPI, design note, workflow
mock/                Cloudflare Worker: the bank's services for the final case
tester/              local test bench (emulator, fake bank, case generator, judge, runners)
test-briefs/         our rehearsal briefs C–F with answer keys
docs/                the hackathon material and our notes
watch.py             live browser view of a running build (trace, tests, chats)
submission.json      the submission form
```

---

## Run it

```bash
pip install -r FREYA/requirements.txt
cp FREYA/kit/env.example env.sh     # FREYA_API_KEY, FREYA_BANK_TEAM_KEY, FREYA_WORKSPACE_ID, ANTHROPIC_API_KEY
source env.sh

# the final case (folder or zip) against our mock
cd FREYA
python3 builder/build.py ../final/case https://freya-mock.freya-hecaton.workers.dev 2>&1 | tee traces/final.log

# a practice brief with the kit's tool API, with tests and one fix round
python3 builder/build.py kit/briefs/brief-a.md kit/tools/openapi.json --test A --fix-rounds 1

# watch a run live
python3 ../watch.py    # http://localhost:8765
```

Each run prints `{"workflow_id", "agent_id", "export"}` at the end and writes its trace to `FREYA/traces/`.

---

## Team

[@Dora-19](https://github.com/Dora-19): builder and mock · [@menes000](https://github.com/menes000): test bench

Built with Claude Code (Opus 5.5). The phone agents run on Freya's model; the builder uses Claude.
