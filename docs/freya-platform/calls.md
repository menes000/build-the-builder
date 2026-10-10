# Calls

Generated from Freya's platform OpenAPI (`https://staging-app.freyavoice.ai/api/openapi.json`), the source behind https://docs.freyavoice.ai.
Paths are relative to `/api/v2` (base URL `https://staging-app.freyavoice.ai`). Responses are wrapped in `{success, data: {message, result}}`; the response fields below are the full body as the spec states it.
Where this page and the kit's `docs/api.md` disagree, the kit was tested against the event's staging platform; prefer it.

## GET `/call/{callId}`

**Get call details**

Returns detailed call information including transcript, messages, tags, and feedbacks.

### Parameters

- `callId` `path` `string` **required**: Call ID
- `workspaceId` `query` `string` **required**: Workspace ID

### Response 200: Call details

- `success` `boolean` **required** one of `True`
- `data` `object` **required**
  - `message` `string` **required**
  - `result` `object` **required**
    - `call` `object` **required**
      - `id` `string` **required**
      - `externalCallId` `string|null`
      - `assistantId` `string|null` format uuid
      - `assistantName` `string|null`
      - `assistantEntityType` `string|null` one of `workflow`, `None`
      - `assistantWorkflowId` `string|null` format uuid
      - `workspaceId` `string` **required**
      - `phoneNumberId` `string|null`
      - `phoneNumber` `string|null`
      - `simulationId` `string|null` format uuid
      - `campaign` `object|null`
        - `id` `string` **required**
        - `assistantId` `string|null` format uuid
        - `phoneNumberId` `string|null`
        - `name` `string` **required**
        - `description` `string|null`
      - `customerNumber` `string|null`
      - `customerLabel` `string|null`
      - `startedAt` `string|null`
      - `endedAt` `string|null`
      - `duration` `number|null`
      - `status` `string|null`
      - `type` `string|null`
      - `modality` `string|null` one of `voice`, `text`, `None`
      - `channel` `string|null` one of `whatsapp`, `api`, `None`
      - `endedReason` `string|null`
      - `transcript` `string|null`
      - `messages` `array|null`
      - `summary` `string|null`
      - `cost` `number|null`
      - `turnLatencyStats` `object|null`
        - `p50` `number` **required**
        - `p75` `number` **required**
        - `p90` `number`
        - `p95` `number` **required**
        - `p99` `number` **required**
        - `avg` `number|null`
        - `count` `number`
      - `recordingUrl` `string|null`
      - `tags` `array`
        - each item:
          - `tag` `string` **required**
          - `source` `string` **required**
          - `value` `number`
          - `confidence` `number|null` minimum 0 maximum 1
          - `metadata` `object|null`
      - `customer` `object`
        - `number` `string|null`
        - `identity` `object`
          - `firstName` `string`
          - `lastName` `string`
          - `email` `string`
      - `unresolvedFeedbacksCount` `number`
      - `resolvedFeedbacksCount` `number`
      - `unresolvedAiFeedbacksCount` `number`
      - `unresolvedUserFeedbacksCount` `number`
      - `reviewStatus` `string|null`
      - `reviewTag` `string|null`
      - `reviewNotes` `string|null`
      - `reviewNotesTruncated` `boolean`
      - `reviewAssignees` `array|null`
      - `isArchived` `boolean` default `false`
      - `isImported` `boolean` default `false`
      - `originCallId` `string|null` format uuid
      - `isShared` `boolean`
      - `assertionsSummary` `object|null`
        - `passed` `number` **required**
        - `failed` `number` **required**
        - `total` `number` **required**
      - `unitTestsCount` `number`
      - `insights` `object`
      - `searchScore` `number`
      - `searchSnippet` `string`
      - `entityVersionId` `string|null` format uuid
      - `entityVersionNumber` `number|null`
      - `updatedAt` `string|null`
      - `sipCallId` `string|null`
      - `analysis` 
      - `createdAt` `string|null`
      - `artifact` 
      - `problems` `array`
        - each item:
          - `id` `string`
          - `workspaceId` `string|null`
          - `callId` `string|null` format uuid
          - `agentId` `string|null` format uuid
          - `title` `string` **required** minLength 1
          - `description` `string|null`
          - `proposedSolution` `string|null`
          - `solutionNote` `string|null`
          - `type` `string|null` one of `workflow`, `decision-llm`, `stt`, `tts`, `vad-nc`, `latency`, `platform`, `ui`, `general`, `None`
          - `severity` `number` default `0.5` minimum 0 maximum 1
          - `status` `string` default `"open"`
          - `assignedTo` `string|null`
          - `createdBy` `string` default `"ai"`
          - `messageId` `string|null`
          - `resolved` `boolean` default `false`
          - `resolvedAt` `string|null`
          - `resolvedBy` `string|null`
          - `solutionId` `string|null` format uuid
          - `resolvedByVersionId` `string|null` format uuid
          - `number` `integer|null`
          - `createdAt` `string`
          - `updatedAt` `string`
          - `callStartedAt` `string|null`
          - `customerNumber` `string|null`
          - `entityVersionId` `string|null` format uuid
          - `versionNumber` `integer|null`
          - `callReviewTag` `string|null`
          - `callReviewNotes` `string|null`
          - `webCallerName` `string|null`
          - `webCallerUserId` `string|null`
          - `hasExternalReference` `boolean`
          - `externalReferences` `array`
            - each item:
          - `agentName` `string|null`
          - `agentEntityType` `string|null`
          - `agentWorkflowId` `string|null`
          - `resolvedByName` `string|null`
          - `assignees` `array`
            - each item:
          - `commentsCount` `number`
          - `openSolutions` `array`
            - each item:
          - `solutionCommits` `array`
            - each item:
          - `isArchived` `boolean` default `false`
      - `assertionResults` `array`
        - each item:
          - `id` `string`
          - `name` `string`
          - `assertion` `string`
          - `success` `boolean|null`
          - `reason` `string|null`
          - `relevantMessages` `object`
          - `timeTaken` `number|null`
          - `metadata` `object`
      - `successCriteriaResult` `object`
        - `id` `string`
        - `name` `string`
        - `assertion` `string`
        - `success` `boolean|null`
        - `reason` `string|null`
        - `relevantMessages` `object`
        - `timeTaken` `number|null`
        - `metadata` `object`
      - `piiRedactions` `array`: PII the voice agent tokenized in this call before storage
        - each item:
          - `token` `string` **required**
          - `label` `string` **required**
          - `value` `string`: Original value; only returned with the calls:pii permission

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
