# Freya platform API: personas, simulations, chat, calls, unit tests

Fetched on 2026-10-10 from Freya's public platform OpenAPI, `https://staging-app.freyavoice.ai/api/openapi.json`, which is the source behind https://docs.freyavoice.ai (index: https://docs.freyavoice.ai/llms.txt). The kit's `build-the-builder/docs/api.md` points here for personas, simulations and calls.

Nothing on these pages was tested against the event's workspace. The kit's docs were. Where they disagree, trust the kit.

| File | What it covers |
|---|---|
| [personas.md](personas.md) | Create, list, get, update, delete personas; AI persona preview |
| [simulations.md](simulations.md) | Create, start, rerun, get, list simulations; iterations; version checks |
| [chat.md](chat.md) | Turn-by-turn chat with a workflow, fork a chat at a message, close a chat |
| [calls.md](calls.md) | One call with its transcript and events |
| [unit-tests.md](unit-tests.md) | Unit tests on a fixed message history, with routing, extraction and tool-call assertions |
| [openapi-subset.json](openapi-subset.json) | The same endpoints as JSON, `$ref`s resolved, for code |

Paths are relative to `/api/v2`. The spec lists `https://app.freyavoice.ai/api/v2` as its server; the event uses `https://staging-app.freyavoice.ai`. Every response is wrapped in `{success, data: {message, result}}`.

## What the kit's docs did not say

**Personas** (`POST /personas`)
- Besides `name`, `prompt`, `successCriteria` and `tags`, a persona takes `systemPrompt`, `evaluationPrompt` and `agentIds`.
- `GET /personas` needs the query parameter `workspaceId`. This settles the "name not confirmed" note in the kit's `api.md`.
- `PUT /personas/{id}` and `DELETE /personas/{id}` exist, so a builder can update its own test personas in place instead of creating new ones each run.
- `POST /personas/preview` generates personas from a prompt.

**Simulations** (`POST /simulations`)
- `start: false` creates a draft. `POST /simulations/{id}/start` starts it later.
- `POST /simulations/{id}/rerun` runs the same simulation again as a new iteration. No new personas or settings are needed.
- `agentVersionId` pins the run to one workflow version.
- `assertions` attaches judge prompts to the simulation. `contextConfig` decides whether routing, extraction and tool-call events are shown to the judge.
- `maxRetries` (0 to 10) and `runsPerPersona` (up to 50) are settings.
- `personaLlmOverride` and `analysisLlmOverride` also take `reasoningEffort`.
- `GET /simulations/{id}` returns the persona prompt as a 280-character preview unless `include=` asks for the full text.
- `GET /simulations/{id}/iterations/{iterationId}`, which `freya.get_iteration` uses, is not in the public spec. The kit's `api.md` is the only reference for it.

**Chat** (`POST /chat/message`)
- The reply carries `messageId`, `endedByAgent` and sometimes `warning`.
- `fromMessageId` branches a conversation from an earlier assistant turn.
- `POST /chat/fork` copies a call up to one message and points it at another `versionId` or `workflowId`. A builder can replay the same opening, for example a verified identity, against a new version of its workflow without running the whole call again.
- `versionId` chats with a version that is not published.

**Calls** (`GET /call/{callId}`)
- The spec lists `workspaceId` as a required query parameter. The kit's `freya.get_call` works without it on staging.

**Unit tests** (`/unit-tests`)
- A unit test is a fixed message history (`input.messages`) plus assertions that need no simulated customer:
  - `routing`: a node was entered, or a route targeted a node (`negate` for "never").
  - `extraction`: a variable exists, equals, contains, matches a regex, or is absent.
  - `tool_call`: a tool was called with these arguments (`subset` or `exact`), or not called.
- An `expectation` text is checked by a judge model.
- `POST /unit-tests/run-all` runs every test of a workflow, with `repeat` up to 20, `mockToolResults` to fake the bank's answers, and `assistantLlmOverride` / `judgeLlmOverride`.
- This is a possible fast check for a builder: one step of the agent tested in seconds, without a full simulation. Whether unit tests are enabled in the event's workspace and count against the platform test limit is not known. Try one before building on it.
