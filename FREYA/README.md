# Freya Bank collections builder

A builder for the Freya x YC "Build the Builder" hackathon. It reads a bank's collections brief and creates a phone agent on Freya.

## How it works

```
brief file(s) + tools/openapi.json
   │
   ▼
1. EXTRACT   Claude reads every brief file and fills a CallSpec: a fixed, brief-independent form
   │         (identity questions, bands and deadlines, holidays, floors, outcome table, special cases...).
   │         Rules that fit no field go into `extra_rules` and are appended to the matching node prompt.
   ▼
2. COMPILE   Deterministic Python turns the CallSpec into a Freya workflow: code nodes compute every date
   │         and amount, tool hooks validate promises/callbacks before they reach the bank and translate
   │         results into plain instructions, a final code node decides outcome and reason from state.
   ▼
3. CHECK     Lint (kit checklist), local execution of every generated snippet, Freya dry run.
   ▼
4. SAVE      `freya.save_workflow(slot, ...)`: the same slot is updated in place, then published.
   ▼
5. TEST      Optional: the kit's practice customers (`--test A --test B`, `--style pieces`), within the time budget.
   ▼
5b. FIX      If customers failed and budget remains (`--fix-rounds 1`): the failed transcripts, ledger diffs and
   │         judge reasons go to Claude, which revises the CallSpec texts (never the brief's values), the compiler
   │         rebuilds, the tests rerun, and the better version is kept (rollback otherwise). All by the builder.
   ▼
6. EXPORT    `out/<slot>.export.workflow.json` and a trace in `traces/`.
```

The builder never edits a phone agent by hand and contains no value from any brief: holidays, bands, floors, queues, outcomes and sentences all come from the CallSpec that Claude extracts at run time. Tool request and response field names come from the tool API file through `tools.field_map()` (exact name, then synonyms, then a loose match, with warnings in the trace), so a final API that renames `all_verified` or `products` still works.

## Setup

Python 3.10+.

```bash
pip install -r requirements.txt
cp kit/env.example env.sh     # FREYA_API_KEY, FREYA_BANK_TEAM_KEY, FREYA_WORKSPACE_ID
# Claude: either `claude` CLI logged in, or ANTHROPIC_API_KEY in env.sh
source env.sh
```

## Run (submission form)

```bash
source env.sh
python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log
# -> submission/hidden-1.workflow.json (the exported workflow) + traces/<time>-hidden-1.txt/.jsonl
```

The first argument is a brief file or a folder of loose material (emails, memos, code lists: every file in name order);
the second is the bank's tool API file. The name of the file or folder becomes the agent slot and the output name.
Extra options go through to the builder unchanged, for example `--test A --fix-rounds 1` for a practice brief.

## Run (developer form)

```bash
# one brief
python3 -m builder.main kit/briefs/brief-a.md --slot brief-a --test A

# a brief that builds on another: pass both, in order
python3 -m builder.main kit/briefs/brief-a.md kit/briefs/brief-b.md --slot brief-ab --test B --test A

# a final brief with its own tool API file
python3 -m builder.main final/brief-x.md --openapi final/openapi.json --slot brief-x
```

Outputs per run:

| File | What |
|---|---|
| `out/<slot>.callspec.json` | what the builder understood from the brief |
| `out/<slot>.workflow.json` | the compiled workflow as sent |
| `submission/<name>.workflow.json` (build.py) or `out/<slot>.export.workflow.json` | the workflow as stored on Freya: **this is the submission file** |
| `traces/<time>-<slot>.txt` / `.jsonl` | the run trace: start/end, every model call, what was created, every test |

The run prints `{"workflow_id", "agent_id", "export"}` at the end.

Options: `--budget-min 25` (tests and fix rounds are skipped once the budget is spent), `--fix-rounds 1`, `--style <pieces|corrects|talkative|asks_back|in_words>`, `--model claude-opus-5-5`, `--spec file.json` (skip extraction, developer use), `--cases file.json`.

## How it works, as a page

`docs/workflow-map.html` explains the whole system for a newcomer (big picture, the builder's steps, how one call flows with a worked example, the engine's turn loop, a glossary) and draws the real node graph from a compiled workflow. Regenerate after a compiler change:

```bash
python3 tools/workflow_map.py out/brief-a.workflow.json docs/workflow-map.html
```

## Layout

```
builder/
  build.py                submission entry point: brief (file or folder) + tool API -> submission/<name>.workflow.json
  main.py                 CLI and pipeline
  trace.py                run trace
  extract/callspec.py     the CallSpec schema (Pydantic)
  extract/extractor.py    brief -> CallSpec via Claude Agent SDK (validation errors fed back, 2 retries)
  extract/tools.py        tool API -> Tool objects (field names and enums come from here)
  extract/prompts/        the extraction instructions
  compile/compiler.py     CallSpec -> workflow nodes, tools, transitions
  compile/codegen.py      Python that runs inside Freya: date/account facts, tool hooks, outcome decision
  compile/prompts.py      node prompt templates
  compile/lint.py         kit checklist checks
  compile/selfcheck.py    runs every generated snippet locally
  test/fixer.py           the fix loop: failures -> revised CallSpec (Claude), with structural guards
  test/scan.py            scans every call of a run for loops, silence, platform errors, invalid close_call
  extract/prompts/fix_callspec.md   the revision instructions
  build_from_spec.py      compile a CallSpec file without extraction (developer tool)
tools/workflow_map.py     the explanatory page generator -> docs/workflow-map.html
kit/                      the organisers' starter kit, unchanged
fixtures/                 hand-written CallSpecs, the example builder's output, Claude's extractions
results/, out/, traces/   run artefacts
NOTES.md                  decisions, baselines, measurements
```

## Design notes

- Three model calls per turn on Freya (extraction, routing, dialogue) do not share a prompt, so routing lives in transitions and extraction enums, never in prose.
- Outcome and reason are never written by the model. Each closing path sets a hint; `decide_outcome` overrides it from recorded state (transfer > promise > notes > hint).
- `create_promise` takes `amount_kind: full | floor | custom`; for full and floor the amount is taken from the account, not from what the model heard.
- A model-filled tool field must not share its name with a variable that is already set (the engine bakes it and hides the parameter). The facts code therefore never writes `product_id`, `amount`, `date`, `reason`, `field`, `answer`, `time`.
- Hooks pass the model's arguments to the post-hook through `vars` (`last_note_pid`...), because `<tool>_args.*` is not yet set when the post-hook runs.
