# Flow Execution Architecture

## Overview

This document describes the clean, DRY flow execution architecture where **all flow logic executes on the backend** and the agent worker is a thin LiveKit integration layer.

## Architecture Principles

1. **Single Source of Truth**: All flow execution logic lives in the backend (TypeScript)
2. **DRY**: No code duplication between backend and agent worker
3. **Language Agnostic**: No JavaScript/Python impedance mismatch
4. **Scalable**: Backend can handle millions of concurrent sessions
5. **Consistent**: Same flow code for testing and production calls

## Component Responsibilities

### Backend (TypeScript)
**Location**: `backend/src/`

**Responsibilities**:
- Execute ALL flow nodes (start, elicitation, LLM, decision, tool, transfer, end)
- Evaluate decision conditions using JavaScript expressions
- Manage session state in database
- Store conversation history and variables
- Handle organization/tenant context
- Process user input through flows

**Key Files**:
- `src/services/flowExecutor.ts` - Flow orchestration engine
- `src/core/flow-executor/` - Node executor implementations
- `src/core/flow-executor/ExecutionContext.ts` - Condition evaluation
- `src/routes/flowRoutes.ts` - Flow execution API endpoints
- `src/services/flowExecutionSessionService.ts` - Session persistence

**API Endpoints**:
```
POST /api/flows/:flowId/process
  - Called by the LiveKit agent worker on every user turn
  - Creates a session automatically on the first request (roomName + flowId)
  - Returns: sessionId, status, assistant response

POST /api/flows/:flowId/test-audio
POST /api/flows/:flowId/test-chat
  - Mint LiveKit rooms/tokens for browser-based testing
  - Persist a pending session record so the agent worker joins the right flow

GET /api/flows/sessions/:sessionId
  - Read-only session inspection (used by the FlowTestPanel dashboard)
  - Returns: session metadata, context, history, test metadata
```

### Agent Worker (Python)
**Location**: `agent-worker/`

**Responsibilities**:
- Connect to LiveKit room
- Capture audio from user (STT)
- Send text to backend for processing
- Speak responses (TTS)
- Handle audio I/O ONLY

**Key Files**:
- `agent.py` - LiveKit agent implementation
- `flow_executor.py` - Thin wrapper around backend API (NO local execution)

**Architecture**:
```python
class FlowExecutor:
    """Thin wrapper - delegates everything to backend"""

    async def start_flow(flow_id, org_id) -> dict:
        # Store metadata so first process_user_input call can bootstrap the session
        return {"flowId": flow_id, "organizationId": org_id}

    async def process_user_input(user_input) -> str:
        # POST /api/flows/:flowId/process
        return message_to_user
```

## Data Flow

### 1. Flow Bootstrap (exactly three entrypoints)

```
Phone Call (Telnyx SIP) ─┐
Browser Audio Test  ─────┼─→ LiveKit room + metadata
Browser Chat Test   ─────┘

POST /api/flows/:flowId/test-audio  ← FlowTestPanel
POST /api/flows/:flowId/test-chat   ← FlowTestPanel
SIP dispatch rule                   ← Telnyx ↔ LiveKit
```

All three paths converge on the same outcome:

1. A LiveKit room is created/selected and the agent worker receives metadata `{ organizationId, agentId?, flowId, roomName }`.
2. A `flowExecutionSessions` row is created in `pending` status so observability/debugging works before the first user utterance.
3. No flow nodes are executed yet—the backend waits for the agent worker to send the first `process` call.

### 2. User Input Processing (single POST endpoint)

```
User speaks
→ STT (Speech-to-Text)
→ Agent Worker receives text
→ POST /api/flows/:flowId/process {
     roomName,
     userInput,
     variables (only on first turn)
   }
→ Backend:
  - Stores user message in conversation
  - Executes current node (elicitation, LLM, decision, etc.)
  - Evaluates JavaScript conditions if decision node
  - Transitions to next node
  - Returns response
→ Agent Worker speaks response
→ Repeat (same endpoint continues the session automatically)
```

### 3. Decision Node Example

**Flow Definition** (JavaScript expression):
```json
{
  "id": "decision-1",
  "type": "decision",
  "data": {
    "conditions": [
      {
        "expression": "issueCategory.toLowerCase().includes('technical')",
        "id": "cond-technical"
      }
    ]
  }
}
```

**Backend Evaluation** (TypeScript):
```typescript
// ExecutionContext.ts
export function evaluateCondition(expression: string, context: ExecutionContext): boolean {
  const varNames = Object.keys(context.variables);
  const varValues = Object.values(context.variables);

  // Create function with variables in scope
  const func = new Function(...varNames, `return ${expression};`);
  return Boolean(func(...varValues));
}
```

This correctly evaluates JavaScript expressions like `.toLowerCase().includes()`.

## Flow → Agent → Number Mapping

```
Organization
  ├─ Flows (flow definitions)
  ├─ Agents (behavior + flow reference)
  │    ├─ customer-support-agent → customer-support-assistant-flow
  │    ├─ sales-agent → sales-flow
  │    └─ tech-support-agent → tech-support-flow
  └─ Phone Numbers
       ├─ +1-555-0100 → customer-support-agent
       ├─ +1-555-0200 → sales-agent
       └─ +1-555-0300 → tech-support-agent
```

When a call comes in:
1. Phone number → Agent lookup
2. Agent → Flow lookup
3. Start flow execution session
4. Process conversation through flow nodes

## Testing vs Production

**Same code path for both!**

### Chat Testing
```bash
POST /api/flows/:flowId/test-chat
  → Creates LiveKit room
  → Starts flow execution
  → Returns token for browser client
  → Uses same flow executor as production
```

### Audio Testing
```bash
POST /api/flows/:flowId/test-audio
  → Creates LiveKit room
  → Starts flow execution
  → Returns token for browser client
  → Uses same STT/TTS/Flow pipeline as production
```

### Production Call
```bash
SIP Call → Phone Number → Agent → Flow
  → Same flow executor
  → Same nodes
  → Same execution logic
```

## Migration from Old Architecture

### Before (Problematic)
- Flow execution logic in BOTH TypeScript and Python
- Python tried to evaluate JavaScript expressions with eval()
- Conditions like `issueCategory.toLowerCase().includes('technical')` failed
- Code duplication and maintenance burden

### After (Clean)
- Flow execution ONLY in TypeScript backend
- Python agent worker is thin API wrapper
- All expressions evaluated correctly
- DRY, scalable, consistent

## Example Session Flow

```json
// 1. Start chat test session from the dashboard
POST /api/flows/abc123/test-chat
Response:
{
  "sessionId": "session_1234567890_xyz",
  "roomName": "chat-test-001",
  "token": "lk1...",
  "identity": "test-user-1700",
  "serverUrl": "wss://livekit.local",
  "flowName": "customer-support"
}

// 2. LiveKit agent worker relays user speech
POST /api/flows/abc123/process
{
  "roomName": "chat-test-001",
  "userId": "test-user-1700",
  "userInput": "My computer won't start"
}
Response:
{
  "sessionId": "session_1234567890_xyz",
  "status": "waiting",
  "response": "I understand you're having a technical issue. Let me check our system status...",
  "completed": false
}

// 3. FlowTestPanel polls session state for observability
GET /api/flows/sessions/session_1234567890_xyz
Response:
{
  "session": {
    "sessionId": "session_1234567890_xyz",
    "status": "waiting",
    "currentNodeId": "tool-1",
    "context": {
      "variables": {
        "customerIssue": "My computer won't start",
        "issueCategory": "technical"
      },
      "conversation": [
        { "role": "assistant", "content": "Hello!" },
        { "role": "user", "content": "My computer won't start" }
      ]
    },
    "testMetadata": {
      "testMode": "chat",
      "identity": "test-user-1700",
      "roomName": "chat-test-001"
    }
  }
}
```

## Benefits

### For Development
- ✅ Single codebase for flow execution
- ✅ TypeScript type safety
- ✅ Easier testing and debugging
- ✅ No language translation issues

### For Operations
- ✅ Centralized session management
- ✅ Database persistence
- ✅ Audit trail in execution logs
- ✅ Easy to monitor and debug

### For Scaling
- ✅ Backend scales horizontally
- ✅ Agent workers are stateless
- ✅ Session state in database
- ✅ Can handle millions of concurrent sessions

### For Maintenance
- ✅ No duplicate logic to maintain
- ✅ Flow changes only in backend
- ✅ Agent worker changes only affect audio I/O
- ✅ Clear separation of concerns

## Error Handling

If backend API fails:
```python
# Agent worker falls back to simple LLM
try:
    response = await flow_executor.process_user_input(text)
except httpx.HTTPError:
    logger.error("Flow execution failed, using simple LLM fallback")
    response = await simple_llm_response(text)
```

## Conclusion

This architecture provides:
- **Clean separation**: Backend = business logic, Agent worker = audio I/O
- **DRY principle**: One flow executor, not two
- **Correctness**: JavaScript expressions evaluated by JavaScript engine
- **Scalability**: Backend handles all sessions, stateless workers
- **Consistency**: Same code for testing and production
