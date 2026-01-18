# Agent Instructions: AICO System (Beta)

**CRITICAL CONTEXT**: This system is in active BETA. Nothing is sacred.

- **Incomplete State**: Expect broken schemas, missing features, or buggy executors.
- **Authority**: You are expected to MODIFY backend code, schemas (`agentFlow.ts`), and executors if functionality is missing or broken. Do not just blindly follow errors; fix the underlying system.
- **Hot Reloading**: Everything runs in Docker containers with hot reloading, so we never need to restart anything.

**RECENT IMPROVEMENTS**:

- Test-flow script now has `--clear-memory` flag to auto-clear memory before testing
- Test-flow script now has `--unique-user` flag for isolated test sessions
- Memory management has `clear-test` command for instant test user reset (no 3s wait)
- ToolExecutor formatter now uses actual LLM calls instead of raw template output
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
   # Quick test with auto memory clear
   bun scripts/flow/test-flow.ts <flow-slug> --clear-memory --inputs "Ja" "Statusabfrage"

   # Or use unique user for completely isolated test
   bun scripts/flow/test-flow.ts <flow-slug> --unique-user --inputs "Ja" "Statusabfrage"

   # Full debugging
   bun scripts/flow/test-flow.ts <flow-slug> --clear-memory --trace --show-vars --verbose
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

| Task                   | Script/Tool                                |
| :--------------------- | :----------------------------------------- |
| **Validate Flow**      | `backend/flow-schema/validate-cli.ts`      |
| **Push Flow**          | `scripts/flow/update-flow.ts`              |
| **Push Tool**          | `scripts/flow/update-tool.ts`              |
| **Test Flow**          | `scripts/flow/test-flow.ts`                |
| **Reset Memory**       | `scripts/flow/manage-memory.ts`            |
| **Quick Memory Clear** | `scripts/flow/manage-memory.ts clear-test` |

## 5. Test Flow Script Usage

The `test-flow.ts` script provides comprehensive flow testing capabilities:

**Basic Usage:**

```bash
# Interactive mode
bun scripts/flow/test-flow.ts <flow-slug>

# With predefined inputs
bun scripts/flow/test-flow.ts <flow-slug> --inputs "Input 1" "Input 2"

# With memory clearing and debugging
bun scripts/flow/test-flow.ts <flow-slug> --clear-memory --trace --show-vars --verbose
```

**Flags:**

| Flag                     | Description                                                               |
| :----------------------- | :------------------------------------------------------------------------ |
| `--inputs <i1> <i2> ...` | Predefined inputs for non-interactive mode                                |
| `--file <path>`          | Read inputs from file (one per line)                                      |
| `--clear-memory`         | Clear test user memory before starting (recommended for repeatable tests) |
| `--unique-user`          | Use unique user ID for completely isolated test session                   |
| `--trace`                | Shows execution path with timing for each node                            |
| `--show-vars`            | Displays working memory and semantic memory after each step               |
| `--verbose`              | Shows debug logs and detailed output                                      |
| `--api <url>`            | Override backend API URL                                                  |

**Interactive Commands:**

- `vars` - Display current memory state (working + semantic)
- `trace` - Display execution path with timing
- `quit` / `exit` - Exit the test session

**Memory Visualization:**
The script clearly separates:

- **Working Memory** (session variables extracted during current conversation)
- **Semantic Memory** (persistent knowledge stored across sessions)

**Execution Trace Features:**

- Shows each node executed with type, ID, and duration
- Color-coded status (green=completed, red=error, yellow=waiting)
- Total execution time summary
- Optional detailed output display with `--verbose`

## 6. Memory Management Script Usage

The `manage-memory.ts` script helps inspect and clear user memory:

**Commands:**

```bash
# List all users with memory data
bun scripts/flow/manage-memory.ts list

# Inspect memory for a specific user
bun scripts/flow/manage-memory.ts inspect test-user-default
bun scripts/flow/manage-memory.ts inspect +1234567890

# Clear all memory for a user (3-second safety delay)
bun scripts/flow/manage-memory.ts clear test-user-default

# Clear specific memory type
bun scripts/flow/manage-memory.ts clear test-user-default chunks
bun scripts/flow/manage-memory.ts clear test-user-default entities

# QUICK: Clear test user instantly (no delay) - best for iteration
bun scripts/flow/manage-memory.ts clear-test
```

**Clear Types:**

- `all` - Clear all memory (default)
- `chunks` - Clear episodic memory chunks only
- `entities` - Clear semantic entities only
- `preferences` - Clear preferences only

## 7. "The Loop" (How to work effectively)

The core philosophy is **Iterative Debugging**.

1. **Analyze**: Look at the goal (e.g., `docs/reference/Flow.mermaid`) and the current JSON.
2. **Execute**: Run `test-flow.ts` with `--clear-memory --verbose`.
3. **Identify Failure**:
   - Is it a schema error? -> Update Validator or JSON.
   - Is it a logic error? -> Update Executor code or JSON.
   - Is it a missing feature? -> Implement the Executor.
   - Is memory causing issues? -> Use `--unique-user` or `clear-test`.
4. **Fix & Validate**: Fix it, run `validate-cli.ts`, then hot-reload.
5. **Repeat**: Until the flow works perfectly.

**Quick Iteration Cycle:**

```bash
# 1. Edit flow JSON
# 2. Validate
bun backend/flow-schema/validate-cli.ts backend/src/seeds/data/flows/my-flow.json

# 3. Deploy (hot reload)
bun scripts/flow/update-flow.ts backend/src/seeds/data/flows/my-flow.json

# 4. Test with fresh memory
bun scripts/flow/test-flow.ts my-flow --clear-memory --inputs "Ja" "Test input"

# Repeat steps 1-4
```

## 8. Advanced Debugging & Logging

- **Backend Logs**: Run `make backend-logs-list` to see system logs.
- **Docker Logs**: `docker logs aico-backend --tail 100` for recent backend logs
- **Log Configuration**: `backend/src/seeds/data/logging/logging.json` allows enabling/disabling module logs.
- **Validator**: The validator (`validate-cli.ts`) is NOT infallible. If it complains about valid code, **fix the validator**.

**Final Rule**: If the system says "Not Implemented" or behaves oddly, open the corresponding Executor file in `backend/src/core/flow-executor/executors/` and **implement it yourself**.

## 9. Test-Flow Script Best Practices

### 9.1 Use --clear-memory for Repeatable Tests

Always use `--clear-memory` when iterating on flow changes:

```bash
bun scripts/flow/test-flow.ts my-flow --clear-memory --inputs "Ja" "Statusabfrage"
```

This ensures each test run starts from a clean state, making results reproducible.

### 9.2 Use --unique-user for Completely Isolated Tests

When you need guaranteed isolation (e.g., testing consent flows):

```bash
bun scripts/flow/test-flow.ts my-flow --unique-user --inputs "Ja" "Test"
```

This creates a new user ID for each run, ensuring no memory interference.

### 9.3 Use clear-test for Quick Memory Resets

During rapid iteration, use the quick clear command:

```bash
bun scripts/flow/manage-memory.ts clear-test
bun scripts/flow/test-flow.ts my-flow --inputs "Ja" "Test"
```

This clears `test-user-default` memory instantly without the 3-second safety delay.

### 9.4 Use Trace for Performance Analysis

The `--trace` flag is essential for understanding flow performance:

```bash
bun scripts/flow/test-flow.ts my-flow --trace
```

This shows:

- Which nodes are slow (LLM calls, tool executions)
- Where optimization is needed (reduce `maxTokens`, add parallel execution)
- Execution order and routing logic

### 9.5 Use Vars for Memory Debugging

The `--show-vars` flag helps debug memory-related issues:

```bash
bun scripts/flow/test-flow.ts my-flow --show-vars
```

This clarifies:

- What's in working memory (current session variables)
- What's in semantic memory (persistent cross-session data)
- Why elicitation nodes skip or don't skip (autoRetrieveMemory)

### 9.6 Combine Flags for Comprehensive Debugging

For complex flow debugging, combine all flags:

```bash
bun scripts/flow/test-flow.ts my-flow --clear-memory --trace --show-vars --verbose
```

This provides complete visibility into:

- Execution path and timing
- Memory state changes
- Node outputs and internal decisions
- Debug logs from executors

### 9.7 Interactive Commands for Live Debugging

In interactive mode, use commands to inspect state without restarting:

- Type `vars` to check current memory
- Type `trace` to see execution path so far
- Test different conversation paths dynamically

## 10. Common Flow Issues & Fixes

### 10.1 Memory Skipping Elicitation Unexpectedly

**Symptom**: Elicitation node skips without asking the user.

**Cause**: `autoRetrieveMemory: true` (or global config) and value exists in memory.

**Fix**: Either:

- Clear memory: `bun scripts/flow/manage-memory.ts clear-test`
- Set `autoRetrieveMemory: false` on the node
- Use `--unique-user` for testing

### 10.2 Double Messages/Greetings

**Symptom**: Agent says greeting twice or outputs duplicate messages.

**Cause**: AgenticLLM outputs response AND routes to another node that also outputs.

**Fix**: Update system instructions to:

- Only greet on first interaction (check conversation history)
- Set `response: ""` when routing to action-specific nodes
- Use `silent: true` for internal routing nodes

### 10.3 Wrong Routing After User Declines

**Symptom**: User says "Nein" to transfer, flow goes to wrong node.

**Cause**: The "Nein" gets processed by the next node as new intent.

**Fix**: Add intermediate elicitation node that:

- Asks for alternative intent
- Uses `intent_classification` to route properly
- Has explicit edges for each possible intent

### 10.4 Raw Instructions Shown to User

**Symptom**: User sees LLM instructions like "Erklaere den Status verstaendlich..."

**Cause**: ToolExecutor formatter's `responseTemplate` being output directly.

**Fix**: The formatter now uses actual LLM calls. If still happening:

- Check `formatter.addToConversation` setting
- Ensure LLM provider is configured correctly
- Check backend logs for formatter errors

## Additional Resources

- [Audio/TTS Optimization](AUDIO_OPTIMIZATION.md)
- [Memory-Aware Flow Design](MEMORY_DESIGN.md)
- [Flow Design Patterns](FLOW_DESIGN_PATTERNS.md)
- [Variable Handling](VARIABLE_HANDLING.md)
- [Token Optimization](TOKEN_OPTIMIZATION.md)
