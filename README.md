<p align="center">
  <img src="assets/banner.svg" alt="Build the Builder · Freya × Y Combinator" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Result-13th%20of%20all%20teams-FB651E?style=for-the-badge" alt="13th of all teams">
  <img src="https://img.shields.io/badge/Freya-voice%20agents-16140f?style=for-the-badge" alt="Freya">
  <img src="https://img.shields.io/badge/Y%20Combinator-hackathon-FB651E?style=for-the-badge&logo=ycombinator&logoColor=white" alt="Y Combinator">
  <img src="https://img.shields.io/badge/Claude-Opus%205.5-D97757?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/Cloudflare-Workers-F38020?style=for-the-badge&logo=cloudflare&logoColor=white" alt="Cloudflare Workers">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</p>

<p align="center">
  <b>A bank sends its documents. Our builder sends back a working phone agent.</b><br>
  No hand edits. One command. Every decision written to a trace.<br><br>
  <b>Finished 13th among all teams in the Freya × Y Combinator hackathon.</b>
</p>

---

## The problem

A bank wants software to answer its phone calls. Before that software can talk to a single customer, someone has to read the bank's material and turn it into a working agent: who to ask for, what to say, which dates are allowed, what to do when a service fails. The material is spread across a dozen documents, written months apart, and the documents contradict each other. **Done by hand, one bank takes days.**

Our builder does that work by itself, and checks its own work.

---

## The heart of it: a builder that corrects itself

Writing an agent once is easy. Writing one that is **right** is the hard part. So our builder does not stop after the first draft. It tests its own agent, reads why customers failed, fixes itself and keeps the fix **only if it really helps**. All inside one command, with no human in the loop.

<p align="center"><img src="assets/loop.svg" alt="The self-correcting loop" width="100%"></p>

```bash
python3 main.py <brief file or folder> <tool openapi.json>
```

### What makes the loop work

| Idea | How |
|---|---|
| **Two readers, not one** | After Claude fills the CallSpec, a second model (GPT) reads the raw brief on its own. Every field where the two readings disagree goes back to Claude, which re-reads the brief for exactly those fields and writes down why it kept or changed each one. |
| **Customers with exact answers** | Test customers are generated from the CallSpec: about 30 single-product and 7 multi-product cases. Every expected date and amount is computed in code (bands, deadlines, business days, holidays, floors), so a judge has a hard answer to check against, not an opinion. |
| **The same customers for the whole run** | The set is fixed once. Every version of the agent is measured against the same customers, so "better" means better. |
| **Fixes change words, never facts** | For each failed customer, the script, the expected outcome, the checks the judge marked as failed and the transcript go to Claude. Claude may rewrite texts and instructions; the brief's values (dates, limits, amounts) stay exactly as extracted. |
| **A gate that cannot be fooled** | A fix is accepted only if **more customers pass and none that passed before fails**. One lost customer, and the builder rolls back to the best version and stops. |
| **Always something to submit** | Version 1 is published before testing starts, so a valid agent exists from minute one. The loop ends when all pass, a fix is rejected, or the time budget is spent. |
| **Everything on the record** | Every round writes its request, the CallSpec diff, the test result and the decision (`fixN.decision.json`). Every model conversation is saved under `chats/`. |

### The loop at work (real traces)

The cross-check settling a conflict between a mail and a memo on its own:

> *"attempt2_rule: kept. 01-email-thread.md CPM rev. 9 section 4.8 gives attempt 2 (floor on the latest date) for overdue and serious; 02-memo-changes.md item 2 cuts serious to one attempt, so attempt 2 is for the overdue band only. The second reader says the same thing in other words."*
> <sub>[`runs/deneme-c/20261011-171829/recheck.result.json`](runs/deneme-c/20261011-171829/recheck.result.json)</sub>

The gate stopping a fix that looked good but broke two passing customers:

```
fix1: rejected, 2/10 -> 0/10, newly failing: DENEME-04, DENEME-18; keeping v1
```
<sub>[`traces/20261011-163126-deneme-e.txt`](traces/20261011-163126-deneme-e.txt)</sub>

> **Nothing about any bank or brief is written into the builder's code.** Every rule, value and sentence comes from the documents at run time.

---

## A team of agents inside one build

The builder is not one model call. One build runs a small team of agents, each with one job, and they check each other.

| Agent | Model | Job |
|---|---|---|
| **Extractor** | Claude Opus | Reads every brief file and fills the CallSpec. |
| **Second reader** | GPT | Reads the raw brief on its own. Where the two readings disagree, the extractor re-reads the brief and justifies each field. |
| **Customer agents** | Gemini | Play the generated customers in five styles: talkative, corrects themselves, says numbers in pieces, asks questions back, says amounts in words. |
| **Agent under test** | emulated locally | The compiled workflow, run step by step: routing, extraction, code nodes, hooks and bank calls. |
| **Judge** | Gemini (GPT optional) | Reads the transcript and the bank's records and checks policy and outcome against each case. |
| **Fixer** | Claude Opus | Gets each failed customer's script, expected outcome, failed checks and transcript. Rewrites texts, never values. |

---

## Testing locally, so the loop can run

A self-correcting loop is only as good as its tests, and only as fast as them. On the platform, simulations run one at a time per workspace and ten cases take 3 to 11 minutes. That is too slow to test, fix and retest inside a single build. So we built our own **local test bench**: it runs the agent, the customers, the bank and the judge on our machine, **in parallel**, and a full set finishes in minutes. It is what makes the loop possible.

<p align="center"><img src="assets/testbench.svg" alt="Local test bench" width="100%"></p>

| Tool | What it does |
|---|---|
| [`emulator.py`](tester/emulator.py) | Runs a Freya workflow locally and reports any Freya feature it cannot emulate |
| [`fakebank.py`](tester/fakebank.py) | A local bank: every identity field, injected faults, wrong-answer limit, field-name mapping, OpenAPI checks |
| [`cases_from_callspec.py`](tester/cases_from_callspec.py) | Generates single- and multi-product customers; every date and amount computed in code |
| [`local_sim.py`](tester/local_sim.py) / [`local_test.py`](tester/local_test.py) | Runs the set, in parallel and with repetitions; the builder can call it |
| [`rule_diff.py`](tester/rule_diff.py) | A second model reads the raw brief on its own; diffs it against the CallSpec field by field |
| [`run_coverage.py`](tester/run_coverage.py) | The official path on Freya, with retries on platform errors |

<table>
<tr>
<td align="center"><h2>26 / 28</h2>same verdict as the real platform<br/><sub>both differences: platform-model behaviour, not the workflow</sub></td>
<td align="center"><h2>4</h2>rehearsal briefs we wrote ourselves<br/><sub>built blind, each with an answer key</sub></td>
<td align="center"><h2>62 s</h2>to build Brief C<br/><sub>extraction caught all 6 memo items, rule diff: 0</sub></td>
</tr>
</table>

---

## When a call does not fit the template

The CallSpec covers one family of calls. If a bank's tool API has none of the tools that family needs, the builder does not crash. It falls back to a free-form path: Claude designs the workflow from the documents, and the builder keeps sending structural problems back until Freya accepts it. The hidden final case, an inbound statement call in Turkish served by our own Cloudflare Worker mock ([`mock/`](mock/)), went through this path. Its design note is in [`FREYA/out/final.freeform.notes.md`](FREYA/out/final.freeform.notes.md).

---

## Repository

```
main.py                    the self-correcting run: extract → cross-check → compile → test → fix → gate
FREYA/                     the builder
├── builder/build.py       submission entry point
├── builder/main.py        read → plan → build → check → publish → trace
├── builder/extract/       reading material · CallSpec extraction · contract → OpenAPI
├── builder/compile/       compiler · code generation · lint · self-check
├── builder/test/          practice runs and the fixer
├── builder/freeform.py    fallback for calls outside the template
├── submission/            exported workflows (final.workflow.json is our entry)
├── traces/                one trace per run
└── out/                   everything a run wrote: OpenAPI, design note, workflow
tester/                    local test bench: emulator, fake bank, case generator, judge
mock/                      Cloudflare Worker: the bank's services
test-briefs/               our rehearsal briefs C–F with answer keys
watch.py                   live browser view of a running build
submission.json            the submission form
```

---

## Run it

```bash
pip install -r FREYA/requirements.txt
cp FREYA/kit/env.example env.sh   # FREYA_API_KEY · FREYA_BANK_TEAM_KEY · FREYA_WORKSPACE_ID · ANTHROPIC_API_KEY
source env.sh
cd FREYA

# the self-correcting run on a brief
python3 ../main.py kit/briefs/brief-a.md kit/tools/openapi.json --cross-check

# a practice brief, with tests and a fix round
python3 builder/build.py kit/briefs/brief-a.md kit/tools/openapi.json --test A --fix-rounds 1

# watch a build live → http://localhost:8765
python3 ../watch.py
```

Both commands end with a JSON line that holds the workflow id, the agent id and the export path. `build.py` writes its trace to `FREYA/traces/`, `main.py` to `traces/`.

---

<p align="center">
  <b>Team MOSES</b><br>
  <a href="https://github.com/menes000">Mehmet Enes Arslan</a> · self-correcting loop & local test bench &nbsp;|&nbsp; <a href="https://github.com/Dora-19">Dora Alkan</a> · builder (CallSpec, compiler, fallback) & mock<br><br>
  <sub>Built with Claude Code · phone agents run on Freya · made for the Freya × Y Combinator "Build the Builder" hackathon, October 2026</sub>
</p>
