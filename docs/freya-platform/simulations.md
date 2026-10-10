# Simulations and iterations

Generated from Freya's platform OpenAPI (`https://staging-app.freyavoice.ai/api/openapi.json`), the source behind https://docs.freyavoice.ai.
Paths are relative to `/api/v2` (base URL `https://staging-app.freyavoice.ai`). Responses are wrapped in `{success, data: {message, result}}`; the response fields below are the full body as the spec states it.
Where this page and the kit's `docs/api.md` disagree, the kit was tested against the event's staging platform; prefer it.

## GET `/simulations/tags`

**List simulation tags**

Returns the distinct tags across all simulations in the workspace.

### Parameters

- `workspaceId` `query` `string` **required**

### Response 200: Distinct tags

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
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

## GET `/simulations`

**List simulations**

Returns simulations for a workspace.

### Parameters

- `workspaceId` `query` `string` **required**
- `status` `query` `string` one of `draft`, `running`, `paused`, `completed`
- `search` `query` `string`
- `filters` `query` `string`
- `sortBy` `query` `string`
- `sortOrder` `query` `string` one of `asc`, `desc`
- `limit` `query` `integer`
- `offset` `query` `integer`

### Response 200: Simulations list

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `simulations` `array` **required**
      - each item:
        - `id` `string` **required**
        - `workspaceId` `string` **required** format uuid
        - `agentId` `string|null` **required** format uuid
        - `name` `string` **required**
        - `description` `string|null`
        - `tags` `array` default `[]`
        - `status` `string` **required** one of `draft`, `running`, `paused`, `completed`
        - `settings` `object` **required**
          - `maxConcurrentCalls` `integer` default `1` minimum 1 maximum 1000
          - `maxCallDurationSeconds` `integer` default `240` minimum 60 maximum 3600
          - `maxRetries` `integer` default `3` minimum 0 maximum 10
          - `runsPerPersona` `integer` default `1` minimum 1 maximum 50
        - `metrics` `object|null`
          - `totalRuns` `integer` default `0` minimum 0
          - `passedRuns` `integer` default `0` minimum 0
          - `failedRuns` `integer` default `0` minimum 0
          - `averageLatencyMs` `number|null` default `null` minimum 0
          - `averageDurationSeconds` `number|null` default `null` minimum 0
          - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
        - `latestPassRate` `number|null` minimum 0 maximum 1
        - `personaCount` `integer` minimum 0: Number of personas linked to the simulation
        - `createdBy` `string|null`
        - `updatedBy` `string|null`
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
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

## POST `/simulations`

**Create simulation**

Creates a new simulation for agent testing.

### Request body (`application/json`)

- `name` `string` **required** minLength 1
- `description` `string`
- `tags` `array`
- `agentId` `string` **required** format uuid
- `mode` `string` one of `voice`, `chat` default `"voice"`
- `selectedPersonaIds` `array` **required**
- `assertions` `array`
- `customerVariablesMap` `object`: Per-persona variable values for this run, keyed by personaId. Saved as the persona's most-recently-used values for the simulated agent.
- `maxConcurrentCalls` `integer` minimum 1 maximum 1000
- `maxCallDurationSeconds` `integer` minimum 60 maximum 3600
- `maxRetries` `integer` minimum 0 maximum 10
- `runsPerPersona` `integer` minimum 1 maximum 50
- `assistantLlmOverride` `object|null`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
- `personaLlmOverride` `object|null`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
  - `reasoningEffort` `string` one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`
- `analysisLlmOverride` `object|null`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
  - `reasoningEffort` `string` one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`
- `routingLlmOverride` `object|null`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
- `extractionLlmOverride` `object|null`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
- `agentVersionId` `string` format uuid
- `start` `boolean`: When false, the simulation is created as a draft and no calls are placed until POST /simulations/{id}/start.

### Response 200: Simulation created

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `simulation` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `agentId` `string|null` **required** format uuid
      - `name` `string` **required**
      - `description` `string|null`
      - `tags` `array` default `[]`
      - `status` `string` **required** one of `draft`, `running`, `paused`, `completed`
      - `settings` `object` **required**
        - `maxConcurrentCalls` `integer` default `1` minimum 1 maximum 1000
        - `maxCallDurationSeconds` `integer` default `240` minimum 60 maximum 3600
        - `maxRetries` `integer` default `3` minimum 0 maximum 10
        - `runsPerPersona` `integer` default `1` minimum 1 maximum 50
      - `metrics` `object|null`
        - `totalRuns` `integer` default `0` minimum 0
        - `passedRuns` `integer` default `0` minimum 0
        - `failedRuns` `integer` default `0` minimum 0
        - `averageLatencyMs` `number|null` default `null` minimum 0
        - `averageDurationSeconds` `number|null` default `null` minimum 0
        - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
      - `latestPassRate` `number|null` minimum 0 maximum 1
      - `personaCount` `integer` minimum 0: Number of personas linked to the simulation
      - `createdBy` `string|null`
      - `updatedBy` `string|null`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**

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

## GET `/simulations/{simulationId}`

**Get simulation**

Returns detailed simulation information including personas and assertions. Persona `prompt` and `successCriteria` are 280-character previews (with `promptTruncated` / `successCriteriaTruncated`) and `systemPrompt`, `evaluationPrompt` and `simulationVariables` are omitted unless `include=` names them; `GET /personas/{personaId}` returns one persona in full.

### Parameters

- `simulationId` `path` `string` **required**
- `include` `query` `string`: Opt-in full persona fields: prompt and successCriteria return in full instead of a preview; systemPrompt, evaluationPrompt and simulationVariables are omitted otherwise.

### Response 200: Simulation details

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `simulation` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `agentId` `string|null` **required** format uuid
      - `name` `string` **required**
      - `description` `string|null`
      - `tags` `array` default `[]`
      - `status` `string` **required** one of `draft`, `running`, `paused`, `completed`
      - `settings` `object` **required**
        - `maxConcurrentCalls` `integer` default `1` minimum 1 maximum 1000
        - `maxCallDurationSeconds` `integer` default `240` minimum 60 maximum 3600
        - `maxRetries` `integer` default `3` minimum 0 maximum 10
        - `runsPerPersona` `integer` default `1` minimum 1 maximum 50
      - `metrics` `object|null`
        - `totalRuns` `integer` default `0` minimum 0
        - `passedRuns` `integer` default `0` minimum 0
        - `failedRuns` `integer` default `0` minimum 0
        - `averageLatencyMs` `number|null` default `null` minimum 0
        - `averageDurationSeconds` `number|null` default `null` minimum 0
        - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
      - `latestPassRate` `number|null` minimum 0 maximum 1
      - `personaCount` `integer` minimum 0: Number of personas linked to the simulation
      - `createdBy` `string|null`
      - `updatedBy` `string|null`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**
    - `personas` `array` **required**: Persona prompts are previews unless include= names them
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
    - `assertions` `array` **required**
      - each item:
        - `id` `string` **required**
        - `workspaceId` `string` **required**
        - `name` `string` **required**
        - `prompt` `string` **required**
        - `contextConfig` `object|null`
          - `includeRoutingEvents` `boolean`
          - `includeExtractionEvents` `boolean`
          - `includeToolCalls` `boolean`
          - `includeOtherEvents` `boolean`
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
    - `metrics` `object|null`
      - `totalRuns` `integer` default `0` minimum 0
      - `passedRuns` `integer` default `0` minimum 0
      - `failedRuns` `integer` default `0` minimum 0
      - `averageLatencyMs` `number|null` default `null` minimum 0
      - `averageDurationSeconds` `number|null` default `null` minimum 0
      - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
    - `publishedVersionId` `string|null` format uuid

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

### Response 404: Simulation not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## PUT `/simulations/{simulationId}`

**Update simulation**

Updates an existing simulation.

### Parameters

- `simulationId` `path` `string` **required**

### Request body (`application/json`)

- `name` `string` minLength 1
- `description` `string|null`
- `tags` `array`
- `status` `string` one of `draft`, `running`, `paused`, `completed`
- `agentId` `string` format uuid
- `selectedPersonaIds` `array`
- `assertions` `array`
- `maxConcurrentCalls` `integer` minimum 1 maximum 1000
- `maxCallDurationSeconds` `integer` minimum 60 maximum 3600
- `maxRetries` `integer` minimum 0 maximum 10
- `runsPerPersona` `integer` minimum 1 maximum 50
- `metrics` `object`
  - `totalRuns` `integer` default `0` minimum 0
  - `passedRuns` `integer` default `0` minimum 0
  - `failedRuns` `integer` default `0` minimum 0
  - `averageLatencyMs` `number|null` default `null` minimum 0
  - `averageDurationSeconds` `number|null` default `null` minimum 0
  - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1

### Response 200: Simulation updated

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `simulation` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `agentId` `string|null` **required** format uuid
      - `name` `string` **required**
      - `description` `string|null`
      - `tags` `array` default `[]`
      - `status` `string` **required** one of `draft`, `running`, `paused`, `completed`
      - `settings` `object` **required**
        - `maxConcurrentCalls` `integer` default `1` minimum 1 maximum 1000
        - `maxCallDurationSeconds` `integer` default `240` minimum 60 maximum 3600
        - `maxRetries` `integer` default `3` minimum 0 maximum 10
        - `runsPerPersona` `integer` default `1` minimum 1 maximum 50
      - `metrics` `object|null`
        - `totalRuns` `integer` default `0` minimum 0
        - `passedRuns` `integer` default `0` minimum 0
        - `failedRuns` `integer` default `0` minimum 0
        - `averageLatencyMs` `number|null` default `null` minimum 0
        - `averageDurationSeconds` `number|null` default `null` minimum 0
        - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
      - `latestPassRate` `number|null` minimum 0 maximum 1
      - `personaCount` `integer` minimum 0: Number of personas linked to the simulation
      - `createdBy` `string|null`
      - `updatedBy` `string|null`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**
    - `personas` `array` **required**: Persona prompts are previews unless include= names them
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
    - `assertions` `array` **required**
      - each item:
        - `id` `string` **required**
        - `workspaceId` `string` **required**
        - `name` `string` **required**
        - `prompt` `string` **required**
        - `contextConfig` `object|null`
          - `includeRoutingEvents` `boolean`
          - `includeExtractionEvents` `boolean`
          - `includeToolCalls` `boolean`
          - `includeOtherEvents` `boolean`
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
    - `metrics` `object|null`
      - `totalRuns` `integer` default `0` minimum 0
      - `passedRuns` `integer` default `0` minimum 0
      - `failedRuns` `integer` default `0` minimum 0
      - `averageLatencyMs` `number|null` default `null` minimum 0
      - `averageDurationSeconds` `number|null` default `null` minimum 0
      - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
    - `publishedVersionId` `string|null` format uuid

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

### Response 404: Simulation not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## DELETE `/simulations/{simulationId}`

**Delete simulation**

Deletes a simulation and all associated data.

### Parameters

- `simulationId` `path` `string` **required**

### Response 200: Simulation deleted

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

### Response 404: Simulation not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## GET `/simulations/{simulationId}/iterations`

**List iterations**

Returns iteration history for a simulation, newest first, one page at a time (limit default 100, max 200). `total` counts every iteration.

### Parameters

- `simulationId` `path` `string` **required**
- `limit` `query` `integer` default `100`: Maximum number of results to return (1-200)
- `offset` `query` `['integer', 'null']` default `0`: Number of results to skip for pagination

### Response 200: Iteration list

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `iterations` `array` **required**
      - each item:
        - `id` `string` **required**
        - `simulationId` `string` **required**
        - `workspaceId` `string` format uuid
        - `iterationIndex` `integer` **required**
        - `label` `string|null` **required**
        - `notes` `string|null` **required**
        - `status` `string` **required**
        - `source` `string` **required**
        - `totalRuns` `integer` **required** minimum 0
        - `passedRuns` `integer` **required** minimum 0
        - `failedRuns` `integer` **required** minimum 0
        - `inconclusiveRuns` `integer` default `0` minimum 0
        - `errorRuns` `integer` default `0` minimum 0
        - `analyzingRuns` `integer` default `0` minimum 0
        - `passRate` `number|null` **required** minimum 0 maximum 1
        - `agentVersionId` `string|null` format uuid
        - `agentVersionNumber` `number|null`
        - `agentLlm` `object|null`
          - `provider` `string` **required** maxLength 100
          - `model` `string` **required** maxLength 200
        - `runAssistantLlms` `object|null`
          - `recorded` `array` **required**
            - each item:
          - `unrecordedRuns` `integer` **required** minimum 0
        - `agentName` `string|null`
        - `params` `object`
          - `assistantLlmOverride` `object`
            - `provider` `string` **required** maxLength 100
            - `model` `string` **required** maxLength 200
          - `personaLlmOverride` `object`
            - `provider` `string` **required** maxLength 100
            - `model` `string` **required** maxLength 200
            - `reasoningEffort` `string` one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`
          - `analysisLlmOverride` `object`
            - `provider` `string` **required** maxLength 100
            - `model` `string` **required** maxLength 200
            - `reasoningEffort` `string` one of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`
          - `routingLlmOverride` `object`
            - `provider` `string` **required** maxLength 100
            - `model` `string` **required** maxLength 200
          - `extractionLlmOverride` `object`
            - `provider` `string` **required** maxLength 100
            - `model` `string` **required** maxLength 200
          - `runsPerPersona` `integer` minimum 1 maximum 50
          - `maxConcurrentCalls` `integer` minimum 1 maximum 1000
        - `createdAt` `string|null`
        - `updatedAt` `string|null`
        - `startedAt` `string|null`
        - `completedAt` `string|null`
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

### Response 404: Simulation not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## GET `/simulations/version-checks`

**List simulation checks for a version**

Returns the simulations that ran against a single agent/workflow version as check rows (latest iteration per simulation, bucketed as passed/failed/running), newest first.

### Parameters

- `workspaceId` `query` `string` **required**
- `entityVersionId` `query` `string` **required**

### Response 200: Simulation checks for the version

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `checks` `array` **required**
      - each item:
        - `simulationId` `string` **required**
        - `name` `string` **required**
        - `status` `string` **required** one of `passed`, `failed`, `running`, `not_run`
        - `failedRuns` `integer` **required** minimum 0
        - `score` `number|null` minimum 0 maximum 1
        - `latestIterationId` `string` **required**
        - `latestAt` `string|null` **required**

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

## GET `/simulations/version-persona-runs`

**List simulation persona runs for a version**

Returns the personas that ran against a single agent/workflow version as check rows (one per persona on each simulation's latest iteration, bucketed as passed/failed/running), newest first.

### Parameters

- `workspaceId` `query` `string` **required**
- `entityVersionId` `query` `string` **required**

### Response 200: Simulation persona runs for the version

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `runs` `array` **required**
      - each item:
        - `personaId` `string` **required**
        - `personaName` `string` **required**
        - `simulationId` `string` **required**
        - `simulationName` `string` **required**
        - `tags` `array` **required**
        - `status` `string` **required** one of `passed`, `failed`, `running`, `not_run`
        - `runId` `string|null`
        - `latestAt` `string|null`

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

## POST `/simulations/{simulationId}/start`

**Start a draft simulation**

Dispatches the initial iteration of a simulation created with start=false. Only draft simulations can be started.

### Parameters

- `simulationId` `path` `string` **required**

### Response 200: Simulation started

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `simulation` `object` **required**
      - `id` `string` **required**
      - `workspaceId` `string` **required** format uuid
      - `agentId` `string|null` **required** format uuid
      - `name` `string` **required**
      - `description` `string|null`
      - `tags` `array` default `[]`
      - `status` `string` **required** one of `draft`, `running`, `paused`, `completed`
      - `settings` `object` **required**
        - `maxConcurrentCalls` `integer` default `1` minimum 1 maximum 1000
        - `maxCallDurationSeconds` `integer` default `240` minimum 60 maximum 3600
        - `maxRetries` `integer` default `3` minimum 0 maximum 10
        - `runsPerPersona` `integer` default `1` minimum 1 maximum 50
      - `metrics` `object|null`
        - `totalRuns` `integer` default `0` minimum 0
        - `passedRuns` `integer` default `0` minimum 0
        - `failedRuns` `integer` default `0` minimum 0
        - `averageLatencyMs` `number|null` default `null` minimum 0
        - `averageDurationSeconds` `number|null` default `null` minimum 0
        - `agentSpeakingPercent` `number|null` default `null` minimum 0 maximum 1
      - `latestPassRate` `number|null` minimum 0 maximum 1
      - `personaCount` `integer` minimum 0: Number of personas linked to the simulation
      - `createdBy` `string|null`
      - `updatedBy` `string|null`
      - `createdAt` `string` **required**
      - `updatedAt` `string` **required**

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

### Response 404: Simulation not found


### Response 409: Simulation is not a draft or has no pending iteration


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## POST `/simulations/{simulationId}/rerun`

**Rerun simulation**

Triggers a new run of the simulation, creating a new iteration.

### Parameters

- `simulationId` `path` `string` **required**

### Response 200: Simulation rerun started

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `success` `boolean` **required**
    - `iteration` `object`
      - `id` `string` **required**
      - `simulationId` `string` **required**
      - `iterationIndex` `integer` **required**
      - `label` `string|null` **required**
      - `status` `string` **required**
    - `runsStarted` `integer` minimum 0

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

### Response 404: Simulation not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 
