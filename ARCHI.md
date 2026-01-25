# Architecture Findings (Flow Executors + Memory)

This document captures a focused review of flow executors and memory logic, plus how the observed failures in AICO logs map back to architectural issues.

## Scope Reviewed

- Flow executors: `backend/src/core/flow-executor/executors/*.ts`
- Executor base classes: `backend/src/core/flow-executor/executors/base/*.ts`
- Flow orchestration and output handling: `backend/src/core/flow-executor/FlowExecutor.ts`, `backend/src/core/flow-executor/helpers/NodeOutputHandler.ts`
- Memory utilities and config: `backend/src/core/flow-executor/utils/memoryUtils.ts`, `backend/src/core/flow-executor/utils/flowConfigUtils.ts`
- Memory layers: `backend/src/core/memory/MemoryPool.ts`, `backend/src/core/memory/EpisodicMemory.ts`, `backend/src/core/memory/SemanticMemory.ts`

## High-Level Assessment

The current architecture functions but is not DRY: control flow, speech emission, memory policy, and retry state are each implemented in multiple places with subtle incompatibilities. This leads to non-deterministic behavior when configs or ports are even slightly mismatched.

The strongest theme is **implicit behavior**: routing and side effects happen through fallbacks and defaults instead of a single explicit contract. That is why small config mistakes (wrong port name, missing edge) can silently bypass nodes or terminate flows.

## Concrete Findings

### 1) Routing Contract Is Inconsistent

- Some executors return `nextNodeId` explicitly (e.g., `ElicitationNodeExecutor`, `ToolExecutorNodeExecutor`, `AgenticLLMNodeExecutor`), while others rely on `FlowExecutor`'s auto-transition based on a "primary port".
- Several executors emit outputs with port names that do **not** match their schema-defined ports:
  - `ElicitationNodeExecutor` emits `validated` and `retryPrompt` outputs, while the schema ports are `response`, `from_memory`, `default`.
  - This mismatch means the output ports cannot be used consistently for routing, and routing depends on defaults/fallbacks in `FlowExecutor`.
- When edges are missing or use incorrect `sourceHandle`s, `FlowExecutor` may auto-transition to the wrong node or end the flow without errors.

### 2) Side-Effects (TTS + Conversation History) Are Duplicated

- Nodes emit responses through **three channels**: `outputs` with `tts: true`, `actions` (speak), and `conversationDeltas`.
- `NodeOutputHandler` emits TTS from `outputs`, while the agent executes `actions` for the same message.
- Some nodes also append to conversation history even when `addToConversation` is false (or vice versa), causing inconsistent chat state.
- Result: duplicated or missing spoken text depending on which path is consumed by the test harness/agent worker.

### 3) Memory Policy Is Scattered

Memory behavior is implemented in multiple places with different rules and defaults:

- `ElicitationNodeExecutor` auto-retrieve/auto-store (semantic memory only).
- `MemoryNodeExecutor` uses `MemoryPool` for explicit store/retrieve/check.
- `AgenticLLMNodeExecutor` can extract and write memory updates.
- `EndNodeExecutor` archives transcript to episodic memory.
  There is no single memory policy entry point, so flow behavior changes depending on which node types are used.

### 4) Retry State Is Not Persisted

- `ElicitationNodeExecutor` uses `context.retryCount` for retries, but `retryCount` is not persisted via state manager.
- Retries reset on each input, causing loops (e.g., repeated "Haben Sie das Kennzeichen..." without ever hitting max retries).

### 5) Entity Type Mismatch in Memory

- Flows store entities as `customer` or `vehicle` while `SemanticMemory` only supports entity types `person`, `place`, `thing`, `concept`.
- `ElicitationNodeExecutor` memory lookup queries `semantic.queryEntities` with arbitrary types. If the stored type does not exist, it will always miss and silently fall back to prompting.

### 6) Executor Responsibilities Are Bloated

`ElicitationNodeExecutor` mixes:

- prompt emission
- memory auto-retrieve/store
- slot filling and accumulation
- intent classification
- smart-entry prefill based on context
- retry logic

This makes the node behavior hard to reason about and difficult to test in isolation.

## Log Mapping (Observed Failures)

The following are recurring behaviors in the Reit logs and their architectural causes:

### A) Tool results skipped, flow ends early

- Observed: `lookup_status` succeeded, but `handle_status_result` never ran; flow went to `end_success` immediately.
- Cause: routing depends on matching port names + edges; if success edge is missing or mislabeled, `FlowExecutor` auto-transitions to default.
- The mismatch between executor output ports and schema ports makes this failure silent.

### B) Infinite retry loops

- Observed: `elicit_rechnung_info` repeats same retry prompt with retryCount stuck at `1`.
- Cause: retry count stored on `context` but never persisted; every user input is treated as retry 1.

### C) Ping-pong between transfer confirmation and alternative intent

- Observed: after a not-found status, user tries to give another plate, but flow oscillates between `confirm_transfer` and `ask_alternative`.
- Cause: narrow intent schema + no robust escape hatch + routing defaults when confidence is low.

### D) Bad slot extraction (e.g., "Lachs" as license plate)

- Observed: slot filling accepts invalid plate strings and continues.
- Cause: no validation constraints on slots, and LLM extraction is trusted without format checks.

### E) Double goodbye

- Observed: final confirmation text spoken, then `end_success` also speaks another goodbye.
- Cause: both `agenticLLM` node and `end` node emit TTS for the closing.

## Architectural Root Cause

The primary architectural problem is **implicit control flow and side-effect emission**:

- Routing relies on a combination of `nextNodeId` and `FlowExecutor` fallbacks, without a single enforced port contract.
- Speech and conversation updates happen via multiple pathways without a single source of truth.
- Memory policy is fragmented across executors and nodes, leading to inconsistent behavior across flows.

In practice, this means a small config error (wrong edge label or missing port) can skip core logic and still produce "successful" runs with incorrect behavior.

## Recommendations (High-Level)

1. **Unify routing**:
   - One routing mechanism only (either explicit `nextNodeId` or strict port-to-edge mapping).
   - Enforce that executor outputs map to schema ports; fail fast if they do not.
2. **Single speech path**:
   - Choose one path for TTS (actions or outputs), not both.
   - Make conversation history updates explicit and consistent per node.
3. **Centralize memory policy**:
   - One entry point for memory read/write rules; node-level overrides should be minimal.
4. **Persist retry state**:
   - Store retry counts in state manager, not on ephemeral context.
5. **Add validation to slot filling**:
   - Support regex or normalization for key slots (license plates, dates).
