# Agent Instructions: AICO System (Beta)

**CRITICAL CONTEXT**: This system is in active BETA. Nothing is sacred.

- **Incomplete State**: Expect broken schemas, missing features, or buggy executors.
- **Authority**: You are expected to MODIFY backend code, schemas (`agentFlow.ts`), and executors if functionality is missing or broken. Do not just blindly follow errors; fix the underlying system.

**RECENT IMPROVEMENTS**:

- Test-flow script now has `--trace` flag for execution path visualization with timing
- Test-flow script now has `--show-vars` flag with clear separation of working vs semantic memory
- Interactive commands `vars` and `trace` available during testing
- See Section 5 for detailed usage

## 1. Flow Management

### Locations & Resources

- **Definitions**: `backend/src/seeds/data/flows/*.json`
- **Schema**: `backend/src/types/agentFlow.ts` (The Source of Truth)
- **Validators**: `backend/flow-schema/validate-cli.ts`

### Workflow

1. **Create/Edit**: Modify JSON files in `backend/src/seeds/data/flows/`.
2. **Validate**:
   ```bash
   bun backend/flow-schema/validate-cli.ts <path-to-json>
   ```
   _Note: Validator checks strict schema. If it fails but code looks right, check `agentFlow.ts` and update the validator or schema._
3. **Deploy (Hot Reload)**:
   ```bash
   bun scripts/flow/update-flow.ts <path-to-json>
   ```
   _Uses `/dev/flows/upsert` (no auth required in dev)._
4. **Test**:

   ```bash
   # Clear memory first for clean state
   bun scripts/flow/manage-memory.ts clear test-user-default

   # Run interactive test with debug logs
   bun scripts/flow/test-flow.ts <flow-slug> --inputs "Arg1" "Arg2" --verbose --show-vars
   ```

## 2. Tool Management

### Locations & Resources

- **Definitions**: `backend/src/seeds/data/tools/*.json`
- **Execution Logic**: `backend/src/core/tool-executor/`
- **Registration Script**: `scripts/flow/update-tool.ts`

### Workflow

1. **Create/Edit**: Modify JSON files in `backend/src/seeds/data/tools/`.
   - _Tip: Use `isBuiltIn: false` to allow API updates._
2. **Deploy**:
   ```bash
   bun scripts/flow/update-tool.ts <path-to-json>
   ```
   _Uses `/dev/api/tools` (bypasses auth)._
3. **Debug**: Use `test-flow.ts --verbose` to see tool input/output packets.

## 3. Executors & Latency

- **Node Executors**: `backend/src/core/flow-executor/executors/`
- **Latency Optimization**:
  - Set `maxTokens` (e.g., 100-150) in `AgenticLLM` nodes.
  - Use `silent: true` for internal planner nodes.
  - Use `wait` nodes with `message: "..."` and `speakMessage: true` for fillers.

## 4. Key Tools Checksheet

| Task              | Script/Tool                           |
| :---------------- | :------------------------------------ |
| **Validate Flow** | `backend/flow-schema/validate-cli.ts` |
| **Push Flow**     | `scripts/flow/update-flow.ts`         |
| **Push Tool**     | `scripts/flow/update-tool.ts`         |
| **Test Flow**     | `scripts/flow/test-flow.ts`           |
| **Reset Memory**  | `scripts/flow/manage-memory.ts`       |

## 5. Test Flow Script Usage

The `test-flow.ts` script provides comprehensive flow testing capabilities:

**Basic Usage:**

```bash
# Interactive mode
bun scripts/flow/test-flow.ts <flow-slug>

# With predefined inputs
bun scripts/flow/test-flow.ts <flow-slug> --inputs "Input 1" "Input 2"

# With debugging flags
bun scripts/flow/test-flow.ts <flow-slug> --trace --show-vars --verbose
```

**Flags:**

- `--trace` - Shows execution path with timing for each node
- `--show-vars` - Displays working memory (session) and semantic memory (persistent) after each step
- `--verbose` - Shows debug logs and detailed output including node outputs
- `--no-livekit` - Uses polling instead of LiveKit (useful for debugging)

**Interactive Commands:**

- `vars` - Display current memory state (working + semantic)
- `trace` - Display execution path with timing
- `quit` / `exit` - Exit the test session

**Memory Visualization:**
The script now clearly separates:

- **Working Memory** (session variables extracted during current conversation)
- **Semantic Memory** (persistent knowledge stored across sessions)

**Execution Trace Features:**

- Shows each node executed with type, ID, and duration
- Color-coded status (green=completed, red=error, yellow=waiting)
- Total execution time summary
- Optional detailed output display with `--verbose`

## 6. "The Loop" (How to work effectively)

The core philosophy is **Iterative Debugging**.

1. **Analyze**: Look at the goal (e.g., `docs/reference/Flow.mermaid`) and the current JSON.
2. **Execute**: Run `test-flow.ts` with `--verbose`.
3. **Identify Failure**:
   - Is it a schema error? -> Update Validator or JSON.
   - Is it a logic error? -> Update Executor code or JSON.
   - Is it a missing feature? -> Implement the Executor.
4. **Fix & Validate**: Fix it, run `validate-cli.ts`, then hot-reload.
5. **Repeat**: Until the flow works perfectly.

## 7. Advanced Debugging & Logging

- **Backend Logs**: Run `make backend-logs-list` to see system logs.
- **Log Configuration**: `backend/src/seeds/data/logging/logging.json` allows enabling/disabling module logs.
- **Validator**: The validator (`validate-cli.ts`) is NOT infallible. If it complains about valid code, **fix the validator**.

**Final Rule**: If the system says "Not Implemented" or behaves oddly, open the corresponding Executor file in `backend/src/core/flow-executor/executors/` and **implement it yourself**.

## 8. Test-Flow Script Best Practices

### 8.1 Always Clear Memory for Clean Tests

Before testing flows with memory features, clear the test user's memory:

```bash
bun scripts/flow/manage-memory.ts clear test-user-default
```

This ensures you're testing the flow from a fresh state without interference from previous runs.

### 8.2 Use Trace for Performance Analysis

The `--trace` flag is essential for understanding flow performance:

```bash
bun scripts/flow/test-flow.ts reit-hauptflow --trace
```

This shows:

- Which nodes are slow (LLM calls, tool executions)
- Where optimization is needed (reduce `maxTokens`, add parallel execution)
- Execution order and routing logic

### 8.3 Use Vars for Memory Debugging

The `--show-vars` flag helps debug memory-related issues:

```bash
bun scripts/flow/test-flow.ts reit-hauptflow --show-vars
```

This clarifies:

- What's in working memory (current session variables)
- What's in semantic memory (persistent cross-session data)
- Why elicitation nodes skip or don't skip

### 8.4 Combine Flags for Comprehensive Debugging

For complex flow debugging, combine all flags:

```bash
bun scripts/flow/test-flow.ts reit-hauptflow --trace --show-vars --verbose
```

This provides complete visibility into:

- Execution path and timing
- Memory state changes
- Node outputs and internal decisions
- Debug logs from executors

### 8.5 Interactive Commands for Live Debugging

In interactive mode, use commands to inspect state without restarting:

- Type `vars` to check current memory
- Type `trace` to see execution path so far
- Test different conversation paths dynamically

## Additional Resources

- [Audio/TTS Optimization](AUDIO_OPTIMIZATION.md)
- [Memory-Aware Flow Design](MEMORY_DESIGN.md)
- [Flow Design Patterns](FLOW_DESIGN_PATTERNS.md)
- [Variable Handling](VARIABLE_HANDLING.md)
- [Token Optimization](TOKEN_OPTIMIZATION.md)
