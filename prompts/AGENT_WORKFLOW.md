# Agent Instructions: AICO System (Beta)

**CRITICAL CONTEXT**: This system is in active BETA. Nothing is sacred.
- **Incomplete State**: Expect broken schemas, missing features, or buggy executors.
- **Authority**: You are expected to MODIFY backend code, schemas (`agentFlow.ts`), and executors if functionality is missing or broken. Do not just blindly follow errors; fix the underlying system.

## 1. Flow Management

### Locations & Resources
- **Definitions**: `backend/src/seeds/data/flows/*.json`
- **Schema**: `backend/src/types/agentFlow.ts` (The Source of Truth)
- **Validators**: `backend/flow-schema/validate-cli.ts`

### Workflow
1.  **Create/Edit**: Modify JSON files in `backend/src/seeds/data/flows/`.
2.  **Validate**:
    ```bash
    bun backend/flow-schema/validate-cli.ts <path-to-json>
    ```
    *Note: Validator checks strict schema. If it fails but code looks right, check `agentFlow.ts` and update the validator or schema.*
3.  **Deploy (Hot Reload)**:
    ```bash
    bun scripts/flow/update-flow.ts <path-to-json>
    ```
    *Uses `/dev/flows/upsert` (no auth required in dev).*
4.  **Test**:
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
1.  **Create/Edit**: Modify JSON files in `backend/src/seeds/data/tools/`.
    *   *Tip: Use `isBuiltIn: false` to allow API updates.*
2.  **Deploy**:
    ```bash
    bun scripts/flow/update-tool.ts <path-to-json>
    ```
    *Uses `/dev/api/tools` (bypasses auth).*
3.  **Debug**: Use `test-flow.ts --verbose` to see tool input/output packets.

## 3. Executors & Latency
- **Node Executors**: `backend/src/core/flow-executor/executors/`
- **Latency Optimization**:
    - Set `maxTokens` (e.g., 100-150) in `AgenticLLM` nodes.
    - Use `silent: true` for internal planner nodes.
    - Use `wait` nodes with `message: "..."` and `speakMessage: true` for fillers.

## 4. Key Tools Checksheet
| Task | Script/Tool |
| :--- | :--- |
| **Validate Flow** | `backend/flow-schema/validate-cli.ts` |
| **Push Flow** | `scripts/flow/update-flow.ts` |
| **Push Tool** | `scripts/flow/update-tool.ts` |
| **Test Flow** | `scripts/flow/test-flow.ts` |
| **Reset Memory** | `scripts/flow/manage-memory.ts` |

## 5. "The Loop" (How to work effectively)
The core philosophy is **Iterative Debugging**.
1.  **Analyze**: Look at the goal (e.g., `docs/reference/Flow.mermaid`) and the current JSON.
2.  **Execute**: Run `test-flow.ts` with `--verbose`.
3.  **Identify Failure**:
    *   Is it a schema error? -> Update Validator or JSON.
    *   Is it a logic error? -> Update Executor code or JSON.
    *   Is it a missing feature? -> Implement the Executor.
4.  **Fix & Validate**: Fix it, run `validate-cli.ts`, then hot-reload.
5.  **Repeat**: Until the flow works perfectly.

## 6. Advanced Debugging & Logging
- **Backend Logs**: Run `make backend-logs-list` to see system logs.
- **Log Configuration**: `backend/src/seeds/data/logging/logging.json` allows enabling/disabling module logs.
- **Validator**: The validator (`validate-cli.ts`) is NOT infallible. If it complains about valid code, **fix the validator**.

**Final Rule**: If the system says "Not Implemented" or behaves oddly, open the corresponding Executor file in `backend/src/core/flow-executor/executors/` and **implement it yourself**.
