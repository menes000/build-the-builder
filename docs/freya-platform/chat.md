# Chat (turn by turn)

Generated from Freya's platform OpenAPI (`https://staging-app.freyavoice.ai/api/openapi.json`), the source behind https://docs.freyavoice.ai.
Paths are relative to `/api/v2` (base URL `https://staging-app.freyavoice.ai`). Responses are wrapped in `{success, data: {message, result}}`; the response fields below are the full body as the spec states it.
Where this page and the kit's `docs/api.md` disagree, the kit was tested against the event's staging platform; prefer it.

## POST `/chat/message`

**Send a chat message**

Drives a Freya agent or workflow turn-by-turn over text. Omit `callId` and provide `agentId` or `workflowId` to start a new call; the response returns a `callId` to pass on subsequent turns. Branch by passing `fromMessageId` pointing at an earlier assistant turn.

### Request body (`application/json`)

- `callId` `string` format uuid
- `agentId` `string` format uuid
- `workflowId` `string` format uuid
- `message` `string` **required** minLength 1 maxLength 10000
- `customerVariables` `object`
- `versionId` `string` format uuid
- `fromMessageId` `string`

### Response 200: Agent reply

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `response` `string` **required**
    - `callId` `string` **required** format uuid
    - `messageId` `string` **required**
    - `warning` `string`
    - `endedByAgent` `boolean`

### Response 400: Validation error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 401: Missing or invalid token

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 403: Workspace ID mismatch or insufficient permissions

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 404: Call not found


### Response 409: Call has no resume anchor (no prior assistant turn)


### Response 422: customerVariables too large


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 502: Agent service returned no response


### Response 503: Agent service not configured


### Response 504: Agent service timed out


## POST `/chat/fork`

**Fork a chat call at an anchor**

Creates a brand-new chat call that copies the parent call's messages up to and including `fromMessageId` and retargets a different `versionId`, `agentId`, or `workflowId`. The forked call is dormant until the caller drives it via POST /chat/message. Cross-entity forks are allowed; the inherited workflowSnapshot may be partially incompatible with the new target (pipecat's resume path degrades gracefully).

### Request body (`application/json`)

- `parentCallId` `string` **required** format uuid
- `fromMessageId` `string` **required** minLength 1
- `versionId` `string` format uuid
- `agentId` `string` format uuid
- `workflowId` `string` format uuid

### Response 200: Forked call

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `callId` `string` **required** format uuid
    - `messageId` `string` **required**
    - `parentCallId` `string` **required** format uuid
    - `parentAnchorMessageId` `string` **required**
    - `entityVersionId` `string|null` **required** format uuid

### Response 400: Validation error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 401: Missing or invalid token

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 403: Workspace ID mismatch or insufficient permissions

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 404: Parent call, anchor message, or target version not found


### Response 422: Parent has no agent or workflow to inherit


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## POST `/chat/end`

**Close a chat call**

Closes a chat call. Tells pipecat to fire the end-of-call lifecycle (webhook + post-conversation analysis + end-of-call tools) — analysis runs async on pipecat; the webhook arrives at the dashboard shortly after with summary, sentiment, themes, problems, and assertions. Idempotent: a second call on an already-ended call returns 200 with `alreadyEnded: true` without re-triggering pipecat.

### Request body (`application/json`)

- `callId` `string` **required** format uuid

### Response 200: Call closed (or already closed)

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `callId` `string` **required** format uuid
    - `ended` `boolean` **required** one of `True`
    - `endedReason` `string` **required**
    - `alreadyEnded` `boolean`

### Response 400: Validation error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 401: Missing or invalid token

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 403: Workspace ID mismatch or insufficient permissions

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 404: Call not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

### Response 503: Agent service not configured


### Response 504: Agent service timed out

