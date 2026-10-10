# Personas

Generated from Freya's platform OpenAPI (`https://staging-app.freyavoice.ai/api/openapi.json`), the source behind https://docs.freyavoice.ai.
Paths are relative to `/api/v2` (base URL `https://staging-app.freyavoice.ai`). Responses are wrapped in `{success, data: {message, result}}`; the response fields below are the full body as the spec states it.
Where this page and the kit's `docs/api.md` disagree, the kit was tested against the event's staging platform; prefer it.

## GET `/personas`

**List personas**

Returns personas for a workspace. prompt and successCriteria carry the first 280 characters (with promptTruncated / successCriteriaTruncated) and systemPrompt, evaluationPrompt and simulationVariables are omitted unless `include` names them; GET /personas/{personaId} returns the full persona.

### Parameters

- `workspaceId` `query` `string` **required**
- `search` `query` `string`
- `filters` `query` `string`: Base64-encoded filter state
- `sortBy` `query` `string`
- `sortOrder` `query` `string` one of `asc`, `desc`
- `limit` `query` `integer`
- `offset` `query` `['integer', 'null']`
- `ids` `query` `string`
- `include` `query` `string`: Opt-in full fields: prompt and successCriteria return in full instead of a preview; systemPrompt, evaluationPrompt and simulationVariables are omitted otherwise. Any include caps limit at 100.
- `export` `query` `string`
- `exportFormat` `query` `string`
- `exportColumns` `query` `string`
- `exportFilename` `query` `string`

### Response 200: Personas list

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `personas` `array` **required**
      - each item:
        - `id` `string` **required**
        - `workspaceId` `string` **required** format uuid
        - `name` `string` **required**
        - `prompt` `string|null` **required**: First 280 characters unless include=prompt
        - `successCriteria` `string|null` **required**: First 280 characters unless include=successCriteria
        - `systemPrompt` `string|null`: Only with include=systemPrompt
        - `evaluationPrompt` `string|null`: Only with include=evaluationPrompt
        - `tags` `array` **required**
        - `agentIds` `array` **required**
        - `simulationVariables` `object`: Only with include=simulationVariables
        - `versionNumber` `integer`
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
        - `createdBy` `string|null` **required**
        - `updatedBy` `string|null` **required**
        - `promptTruncated` `boolean`: True when prompt was cut to the preview length
        - `successCriteriaTruncated` `boolean`: True when successCriteria was cut to the preview length
    - `total` `integer` **required** minimum 0

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

### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## POST `/personas`

**Create persona**

Creates a new persona for simulation testing.

### Request body (`application/json`)

- `personas` `array` **required**
  - each item:
    - `name` `string` **required** minLength 1
    - `prompt` `string` **required** minLength 1 maxLength 100000
    - `successCriteria` `string` maxLength 100000
    - `systemPrompt` `string` maxLength 100000
    - `evaluationPrompt` `string` maxLength 100000
    - `tags` `array`
    - `agentIds` `array`

### Response 201: Persona created

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `personas` `array` **required**
      - each item:
        - `id` `string` **required**
        - `workspaceId` `string` **required** format uuid
        - `name` `string` **required**
        - `prompt` `string|null` **required**
        - `successCriteria` `string|null` **required**
        - `systemPrompt` `string|null` **required**
        - `evaluationPrompt` `string|null` **required**
        - `tags` `array` **required**
        - `agentIds` `array` **required**
        - `simulationVariables` `object` default `{}`: Most-recently-used simulation variable values, keyed by simulated agentId
        - `versionNumber` `integer`
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
        - `createdBy` `string|null` **required**
        - `updatedBy` `string|null` **required**

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

### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## POST `/personas/preview`

**Generate persona preview**

Generates AI-powered persona previews based on a prompt.

### Request body (`application/json`)

- `agentId` `string` **required** format uuid
- `prompt` `string` **required** minLength 1
- `count` `integer` default `3` minimum 1 maximum 50

### Response 200: Generated personas

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `personas` `array` **required**
      - each item:
        - `name` `string` **required**
        - `prompt` `string` **required**
        - `successCriteria` `string` **required**
        - `tags` `array` **required**

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

### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## GET `/personas/{personaId}`

**Get persona**

Returns detailed persona information.

### Parameters

- `personaId` `path` `string` **required**

### Response 200: Persona details

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `persona` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `name` `string` **required**
      - `prompt` `string|null` **required**
      - `successCriteria` `string|null` **required**
      - `systemPrompt` `string|null` **required**
      - `evaluationPrompt` `string|null` **required**
      - `tags` `array` **required**
      - `agentIds` `array` **required**
      - `simulationVariables` `object` default `{}`: Most-recently-used simulation variable values, keyed by simulated agentId
      - `versionNumber` `integer`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**
      - `createdBy` `string|null` **required**
      - `updatedBy` `string|null` **required**

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

### Response 404: Persona not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## PUT `/personas/{personaId}`

**Update persona**

Updates an existing persona.

### Parameters

- `personaId` `path` `string` **required**

### Request body (`application/json`)

- `name` `string` minLength 1
- `prompt` `string` minLength 1 maxLength 100000
- `successCriteria` `string|null` maxLength 100000
- `systemPrompt` `string|null` maxLength 100000
- `evaluationPrompt` `string|null` maxLength 100000
- `tags` `array`
- `agentIds` `array`

### Response 200: Persona updated

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `persona` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `name` `string` **required**
      - `prompt` `string|null` **required**
      - `successCriteria` `string|null` **required**
      - `systemPrompt` `string|null` **required**
      - `evaluationPrompt` `string|null` **required**
      - `tags` `array` **required**
      - `agentIds` `array` **required**
      - `simulationVariables` `object` default `{}`: Most-recently-used simulation variable values, keyed by simulated agentId
      - `versionNumber` `integer`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**
      - `createdBy` `string|null` **required**
      - `updatedBy` `string|null` **required**

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

### Response 404: Persona not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## DELETE `/personas/{personaId}`

**Delete persona**

Deletes a persona. Refuses with 409 while simulations use it; `force=true` deletes it anyway and removes it from those simulations.

### Parameters

- `personaId` `path` `string` **required**
- `force` `query` `string` one of `true`, `false`

### Response 200: Persona deleted

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `success` `boolean` **required**

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

### Response 404: Persona not found


### Response 409: Simulations use this persona; the response lists them


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 
