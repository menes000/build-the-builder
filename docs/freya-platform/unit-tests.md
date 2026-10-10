# Unit tests

Generated from Freya's platform OpenAPI (`https://staging-app.freyavoice.ai/api/openapi.json`), the source behind https://docs.freyavoice.ai.
Paths are relative to `/api/v2` (base URL `https://staging-app.freyavoice.ai`). Responses are wrapped in `{success, data: {message, result}}`; the response fields below are the full body as the spec states it.
Where this page and the kit's `docs/api.md` disagree, the kit was tested against the event's staging platform; prefer it.

## GET `/unit-tests/version-runs`

**List unit-test version runs**

Returns one summary per entity version that has at least one non-stale run, with run-level outcome counts folded in a single GROUP BY (no per-test fan-out), ordered newest-activity-first and paged. Backs the runs-oriented list. Requires agents:read or workflows:read.

### Parameters

- `workspaceId` `query` `string` **required**
- `entityType` `query` `string` **required** one of `agent`, `workflow`
- `entityId` `query` `string` **required**
- `limit` `query` `integer` default `50`
- `offset` `query` `['integer', 'null']` default `0`

### Response 200: Per-version run summaries

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `versionRuns` `array` **required**
      - each item:
        - `entityVersionId` `string` **required** format uuid
        - `versionNumber` `integer` **required**
        - `versionName` `string|null` **required**
        - `branchId` `string|null` **required** format uuid
        - `branchName` `string|null` **required**
        - `isBranchHead` `boolean` **required**
        - `passCount` `integer` **required** minimum 0
        - `failCount` `integer` **required** minimum 0
        - `errorCount` `integer` **required** minimum 0
        - `runningCount` `integer` **required** minimum 0
        - `simPassCount` `integer` **required** minimum 0
        - `simFailCount` `integer` **required** minimum 0
        - `simRunningCount` `integer` **required** minimum 0
        - `simPendingCount` `integer` default `0` minimum 0
        - `latestRunAt` `string` **required**
    - `total` `integer` **required** minimum 0
    - `limit` `integer` **required**
    - `offset` `integer` **required** minimum 0

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

## GET `/unit-tests/overview`

**Unit tests overview**

Returns the workspace's non-archived unit tests grouped by entity, a page at a time (`limit` default 200, max 500; `total` counts every test), with each test's latest run aggregated against its entity's mainline head version. Rows omit `input`, `assertions` and `judgeContext`; get a single unit test for those. Requires agents:read or workflows:read.

### Parameters

- `workspaceId` `query` `string` **required**
- `limit` `query` `integer` default `200`
- `offset` `query` `['integer', 'null']` default `0`

### Response 200: Unit tests grouped by entity with head-version aggregates

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `entities` `array` **required**
      - each item:
        - `entityType` `string` **required** one of `agent`, `workflow`
        - `entityId` `string` **required**
        - `entityName` `string|null` **required**
        - `workflowId` `string|null` **required** format uuid
        - `headVersionId` `string|null` **required** format uuid
        - `headVersionNumber` `integer|null` **required**
        - `tests` `array` **required**
          - each item:
    - `aggregates` `array` **required**
      - each item:
        - `unitTestId` `string` **required** format uuid
        - `entityVersionId` `string` **required** format uuid
        - `passCount` `integer` **required** minimum 0
        - `failCount` `integer` **required** minimum 0
        - `errorCount` `integer` **required** minimum 0
        - `runningCount` `integer` **required** minimum 0
        - `latestRunId` `string|null` **required** format uuid
        - `latestOutcome` `string|null` **required** one of `queued`, `running`, `pass`, `fail`, `error`, `None`
        - `latestVerdictReason` `string|null` **required**
        - `latestCompletedAt` `string|null` **required**
        - `latestJudgeModel` `string|null` **required**
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

## GET `/unit-tests`

**List unit tests**

Returns the unit tests for an agent or workflow a page at a time (`limit` default 200, max 500; `total` counts every match), plus the latest run per (test, version) pair. Rows omit `input`, `assertions` and `judgeContext`; get a single unit test for those.

### Parameters

- `workspaceId` `query` `string` **required**
- `entityType` `query` `string` **required** one of `agent`, `workflow`
- `entityId` `query` `string` **required**
- `includeArchived` `query` ``
- `entityVersionId` `query` `string`
- `limit` `query` `integer` default `200`
- `offset` `query` `['integer', 'null']` default `0`

### Response 200: Unit test list with latest-run summaries

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `tests` `array` **required**
      - each item:
        - `id` `string` **required** format uuid
        - `workspaceId` `string` **required** format uuid
        - `entityType` `string` **required** one of `agent`, `workflow`
        - `entityId` `string` **required**
        - `name` `string` **required**
        - `expectation` `string` **required**
        - `tags` `array` **required**
        - `seedCallId` `string|null` **required** format uuid
        - `seedMessageId` `string|null` **required**
        - `ordinal` `integer` **required**
        - `isArchived` `boolean` **required**
        - `createdBy` `string|null` **required** format uuid
        - `updatedBy` `string|null` **required** format uuid
        - `createdAt` `string` **required**
        - `updatedAt` `string` **required**
    - `total` `integer` **required** minimum 0
    - `aggregates` `array` **required**
      - each item:
        - `unitTestId` `string` **required** format uuid
        - `entityVersionId` `string` **required** format uuid
        - `passCount` `integer` **required** minimum 0
        - `failCount` `integer` **required** minimum 0
        - `errorCount` `integer` **required** minimum 0
        - `runningCount` `integer` **required** minimum 0
        - `latestRunId` `string|null` **required** format uuid
        - `latestOutcome` `string|null` **required** one of `queued`, `running`, `pass`, `fail`, `error`, `None`
        - `latestVerdictReason` `string|null` **required**
        - `latestCompletedAt` `string|null` **required**
        - `latestJudgeModel` `string|null` **required**

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

## POST `/unit-tests`

**Create unit test**

Creates a new unit test against an agent or workflow snapshot.

### Request body (`application/json`)

- `workspaceId` `string` **required** format uuid
- `entityType` `string` **required** one of `agent`, `workflow`
- `entityId` `string` **required** minLength 1
- `name` `string` minLength 1 maxLength 180
- `expectation` `string` maxLength 50000
- `assertions` `array` default `[]`
  - each item:
    - variant 1:
      - `type` `string` **required** one of `routing`
      - `signal` `string` one of `node_entered`, `route_target` default `"node_entered"`
      - `target` `string` **required** minLength 1
      - `negate` `boolean` default `false`
    - variant 2:
      - `type` `string` **required** one of `extraction`
      - `name` `string` **required** minLength 1
      - `match` `string` one of `exists`, `equals`, `contains`, `regex`, `absent` default `"exists"`
      - `value` 
      - `minConfidence` `number` minimum 0 maximum 1
    - variant 3:
      - `type` `string` **required** one of `tool_call`
      - `tool` `string` **required** minLength 1
      - `args` `object`
      - `argsMatch` `string` one of `subset`, `exact` default `"subset"`
      - `negate` `boolean` default `false`
- `input` `object` **required**
  - `schemaVersion` `number` **required** one of `1`
  - `callType` `string` **required** one of `web`, `voice`
  - `messages` `array` **required**
    - each item:
      - `role` `string` **required** minLength 1
      - `message` `string`
      - `content` `string`
      - `messageId` `string`
      - `nodeId` `string|null`
      - `secondsFromStart` `number`
      - `duration` `number`
      - `timestamp` `string`
      - `endTime` `number`
      - `wasBlocked` `boolean`
      - `was_blocked` `boolean`
      - `blockedContent` `string`
      - `blocked_content` `string`
      - `workflowSnapshot` 
  - `customerVariables` `object`
  - `authoredAgainstVersionId` `string` format uuid
- `judgeContext` `object|null`
  - `includeRoutingEvents` `boolean`
  - `includeExtractionEvents` `boolean`
  - `includeToolCalls` `boolean`
  - `includeOtherEvents` `boolean`
- `seedCallId` `string` format uuid
- `seedMessageId` `string`
- `tags` `array` default `[]`

### Response 201: Unit test created

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `id` `string` **required** format uuid
    - `workspaceId` `string` **required** format uuid
    - `entityType` `string` **required** one of `agent`, `workflow`
    - `entityId` `string` **required**
    - `name` `string` **required**
    - `expectation` `string` **required**
    - `assertions` `array` **required**
      - each item:
        - variant 1:
          - `type` `string` **required** one of `routing`
          - `signal` `string` one of `node_entered`, `route_target` default `"node_entered"`
          - `target` `string` **required** minLength 1
          - `negate` `boolean` default `false`
        - variant 2:
          - `type` `string` **required** one of `extraction`
          - `name` `string` **required** minLength 1
          - `match` `string` one of `exists`, `equals`, `contains`, `regex`, `absent` default `"exists"`
          - `value` 
          - `minConfidence` `number` minimum 0 maximum 1
        - variant 3:
          - `type` `string` **required** one of `tool_call`
          - `tool` `string` **required** minLength 1
          - `args` `object`
          - `argsMatch` `string` one of `subset`, `exact` default `"subset"`
          - `negate` `boolean` default `false`
    - `tags` `array` **required**
    - `input` `object` **required**
      - `schemaVersion` `number` **required** one of `1`
      - `callType` `string` **required** one of `web`, `voice`
      - `messages` `array` **required**
        - each item:
          - `role` `string` **required** minLength 1
          - `message` `string`
          - `content` `string`
          - `messageId` `string`
          - `nodeId` `string|null`
          - `secondsFromStart` `number`
          - `duration` `number`
          - `timestamp` `string`
          - `endTime` `number`
          - `wasBlocked` `boolean`
          - `was_blocked` `boolean`
          - `blockedContent` `string`
          - `blocked_content` `string`
          - `workflowSnapshot` 
      - `customerVariables` `object`
      - `authoredAgainstVersionId` `string` format uuid
    - `judgeContext` `object|null`
      - `includeRoutingEvents` `boolean`
      - `includeExtractionEvents` `boolean`
      - `includeToolCalls` `boolean`
      - `includeOtherEvents` `boolean`
    - `seedCallId` `string|null` **required** format uuid
    - `seedMessageId` `string|null` **required**
    - `ordinal` `integer` **required**
    - `isArchived` `boolean` **required**
    - `createdBy` `string|null` **required** format uuid
    - `updatedBy` `string|null` **required** format uuid
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

## GET `/unit-tests/{unitTestId}`

**Get unit test**

Returns a single unit test by ID.

### Parameters

- `unitTestId` `path` `string` **required**

### Response 200: Unit test details

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `id` `string` **required** format uuid
    - `workspaceId` `string` **required** format uuid
    - `entityType` `string` **required** one of `agent`, `workflow`
    - `entityId` `string` **required**
    - `name` `string` **required**
    - `expectation` `string` **required**
    - `assertions` `array` **required**
      - each item:
        - variant 1:
          - `type` `string` **required** one of `routing`
          - `signal` `string` one of `node_entered`, `route_target` default `"node_entered"`
          - `target` `string` **required** minLength 1
          - `negate` `boolean` default `false`
        - variant 2:
          - `type` `string` **required** one of `extraction`
          - `name` `string` **required** minLength 1
          - `match` `string` one of `exists`, `equals`, `contains`, `regex`, `absent` default `"exists"`
          - `value` 
          - `minConfidence` `number` minimum 0 maximum 1
        - variant 3:
          - `type` `string` **required** one of `tool_call`
          - `tool` `string` **required** minLength 1
          - `args` `object`
          - `argsMatch` `string` one of `subset`, `exact` default `"subset"`
          - `negate` `boolean` default `false`
    - `tags` `array` **required**
    - `input` `object` **required**
      - `schemaVersion` `number` **required** one of `1`
      - `callType` `string` **required** one of `web`, `voice`
      - `messages` `array` **required**
        - each item:
          - `role` `string` **required** minLength 1
          - `message` `string`
          - `content` `string`
          - `messageId` `string`
          - `nodeId` `string|null`
          - `secondsFromStart` `number`
          - `duration` `number`
          - `timestamp` `string`
          - `endTime` `number`
          - `wasBlocked` `boolean`
          - `was_blocked` `boolean`
          - `blockedContent` `string`
          - `blocked_content` `string`
          - `workflowSnapshot` 
      - `customerVariables` `object`
      - `authoredAgainstVersionId` `string` format uuid
    - `judgeContext` `object|null`
      - `includeRoutingEvents` `boolean`
      - `includeExtractionEvents` `boolean`
      - `includeToolCalls` `boolean`
      - `includeOtherEvents` `boolean`
    - `seedCallId` `string|null` **required** format uuid
    - `seedMessageId` `string|null` **required**
    - `ordinal` `integer` **required**
    - `isArchived` `boolean` **required**
    - `createdBy` `string|null` **required** format uuid
    - `updatedBy` `string|null` **required** format uuid
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

### Response 404: Unit test not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## PATCH `/unit-tests/{unitTestId}`

**Update unit test**

Updates a unit test's name, expectation, input snapshot, ordinal, or archived flag.

### Parameters

- `unitTestId` `path` `string` **required**

### Request body (`application/json`)

- `name` `string` minLength 1 maxLength 180
- `expectation` `string` maxLength 50000
- `assertions` `array`
  - each item:
    - variant 1:
      - `type` `string` **required** one of `routing`
      - `signal` `string` one of `node_entered`, `route_target` default `"node_entered"`
      - `target` `string` **required** minLength 1
      - `negate` `boolean` default `false`
    - variant 2:
      - `type` `string` **required** one of `extraction`
      - `name` `string` **required** minLength 1
      - `match` `string` one of `exists`, `equals`, `contains`, `regex`, `absent` default `"exists"`
      - `value` 
      - `minConfidence` `number` minimum 0 maximum 1
    - variant 3:
      - `type` `string` **required** one of `tool_call`
      - `tool` `string` **required** minLength 1
      - `args` `object`
      - `argsMatch` `string` one of `subset`, `exact` default `"subset"`
      - `negate` `boolean` default `false`
- `input` `object`
  - `schemaVersion` `number` **required** one of `1`
  - `callType` `string` **required** one of `web`, `voice`
  - `messages` `array` **required**
    - each item:
      - `role` `string` **required** minLength 1
      - `message` `string`
      - `content` `string`
      - `messageId` `string`
      - `nodeId` `string|null`
      - `secondsFromStart` `number`
      - `duration` `number`
      - `timestamp` `string`
      - `endTime` `number`
      - `wasBlocked` `boolean`
      - `was_blocked` `boolean`
      - `blockedContent` `string`
      - `blocked_content` `string`
      - `workflowSnapshot` 
  - `customerVariables` `object`
  - `authoredAgainstVersionId` `string` format uuid
- `judgeContext` `object|null`
  - `includeRoutingEvents` `boolean`
  - `includeExtractionEvents` `boolean`
  - `includeToolCalls` `boolean`
  - `includeOtherEvents` `boolean`
- `ordinal` `integer`
- `isArchived` `boolean`
- `tags` `array`

### Response 200: Unit test updated

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `id` `string` **required** format uuid
    - `workspaceId` `string` **required** format uuid
    - `entityType` `string` **required** one of `agent`, `workflow`
    - `entityId` `string` **required**
    - `name` `string` **required**
    - `expectation` `string` **required**
    - `assertions` `array` **required**
      - each item:
        - variant 1:
          - `type` `string` **required** one of `routing`
          - `signal` `string` one of `node_entered`, `route_target` default `"node_entered"`
          - `target` `string` **required** minLength 1
          - `negate` `boolean` default `false`
        - variant 2:
          - `type` `string` **required** one of `extraction`
          - `name` `string` **required** minLength 1
          - `match` `string` one of `exists`, `equals`, `contains`, `regex`, `absent` default `"exists"`
          - `value` 
          - `minConfidence` `number` minimum 0 maximum 1
        - variant 3:
          - `type` `string` **required** one of `tool_call`
          - `tool` `string` **required** minLength 1
          - `args` `object`
          - `argsMatch` `string` one of `subset`, `exact` default `"subset"`
          - `negate` `boolean` default `false`
    - `tags` `array` **required**
    - `input` `object` **required**
      - `schemaVersion` `number` **required** one of `1`
      - `callType` `string` **required** one of `web`, `voice`
      - `messages` `array` **required**
        - each item:
          - `role` `string` **required** minLength 1
          - `message` `string`
          - `content` `string`
          - `messageId` `string`
          - `nodeId` `string|null`
          - `secondsFromStart` `number`
          - `duration` `number`
          - `timestamp` `string`
          - `endTime` `number`
          - `wasBlocked` `boolean`
          - `was_blocked` `boolean`
          - `blockedContent` `string`
          - `blocked_content` `string`
          - `workflowSnapshot` 
      - `customerVariables` `object`
      - `authoredAgainstVersionId` `string` format uuid
    - `judgeContext` `object|null`
      - `includeRoutingEvents` `boolean`
      - `includeExtractionEvents` `boolean`
      - `includeToolCalls` `boolean`
      - `includeOtherEvents` `boolean`
    - `seedCallId` `string|null` **required** format uuid
    - `seedMessageId` `string|null` **required**
    - `ordinal` `integer` **required**
    - `isArchived` `boolean` **required**
    - `createdBy` `string|null` **required** format uuid
    - `updatedBy` `string|null` **required** format uuid
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

### Response 404: Unit test not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## DELETE `/unit-tests/{unitTestId}`

**Archive unit test**

Soft-deletes a unit test by setting is_archived = true; historical runs stay queryable.

### Parameters

- `unitTestId` `path` `string` **required**

### Response 200: Unit test archived

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `success` `boolean` **required** one of `True`

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

### Response 404: Unit test not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## POST `/unit-tests/run-all`

**Run all unit tests**

Enqueues a run for every active unit test on an agent or workflow, deduping against pending jobs.

### Request body (`application/json`)

- `workspaceId` `string` **required** format uuid
- `entityType` `string` **required** one of `agent`, `workflow`
- `entityId` `string` **required** format uuid
- `entityVersionId` `string` format uuid
- `unitTestIds` `array`
- `onlyFailed` `boolean`
- `mockToolResults` `object`
- `judgeLlmOverride` `object`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
- `assistantLlmOverride` `object`
  - `provider` `string` **required** maxLength 100
  - `model` `string` **required** maxLength 200
- `repeat` `integer` default `1` minimum 1 maximum 20

### Response 202: Runs enqueued

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `enqueued` `array` **required**
      - each item:
        - `unitTestId` `string` **required** format uuid
        - `runIds` `array` **required**
        - `jobIds` `array` **required**
    - `skipped` `array` **required**

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

## GET `/unit-tests/runs/{runId}`

**Get unit-test run**

Returns a single unit-test run, including its verdict and metrics.

### Parameters

- `runId` `path` `string` **required**

### Response 200: Unit-test run details

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `id` `string` **required** format uuid
    - `workspaceId` `string` **required** format uuid
    - `unitTestId` `string` **required** format uuid
    - `entityVersionId` `string` **required** format uuid
    - `unitTestJobId` `string|null` **required** format uuid
    - `outcome` `string` **required** one of `queued`, `running`, `pass`, `fail`, `error`
    - `verdictReason` `string|null` **required**
    - `agentResponse` `string|null` **required**
    - `agentResponseMessageId` `string|null` **required**
    - `latencyMs` `integer|null` **required**
    - `judgeLatencyMs` `integer|null` **required**
    - `judgeModel` `string|null` **required**
    - `messages` `array|null` **required**
    - `assertionResults` `array|null` **required**
    - `metadata` `object` **required**
    - `isStale` `boolean` **required**
    - `startedAt` `string|null` **required**
    - `completedAt` `string|null` **required**
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

### Response 404: Run not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 

## GET `/unit-tests/{unitTestId}/runs`

**List unit-test runs**

Returns the non-stale runs for a unit test on a specific entity version (the run drill-down list), newest first, a page at a time (`limit` default 100, max 500; `total` counts every run). Requires agents:read or workflows:read.

### Parameters

- `unitTestId` `path` `string` **required**
- `workspaceId` `query` `string` **required**
- `entityVersionId` `query` `string` **required**
- `limit` `query` `integer` default `100`
- `offset` `query` `['integer', 'null']` default `0`

### Response 200: Unit-test runs for the (test, version)

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `runs` `array` **required**
      - each item:
        - `id` `string` **required** format uuid
        - `outcome` `string` **required** one of `queued`, `running`, `pass`, `fail`, `error`
        - `verdictReason` `string|null` **required**
        - `judgeModel` `string|null` **required**
        - `latencyMs` `integer|null` **required**
        - `judgeLatencyMs` `integer|null` **required**
        - `completedAt` `string|null` **required**
        - `createdAt` `string` **required**
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

### Response 404: Unit test not found


### Response 500: Server error

- `success` `boolean` **required** one of `False`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` 
