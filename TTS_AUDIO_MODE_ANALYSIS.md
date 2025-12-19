# TTS Audio Mode Issue - Root Cause Analysis

**Date**: 2025-12-19  
**Status**: CRITICAL BUG - Audio mode TTS only speaks first message

## Problem Summary

In audio mode, TTS only speaks the **first welcome message** from the `start` node, but subsequent messages from `elicitation` nodes are **never spoken**. Chat mode works perfectly fine.

### Observed Behavior

**Frontend Logs Show:**
- Session: `audio-test-1766175012146-n9lt1a`
- Only 2 messages in conversation (should have more)
- Node timeline shows: `start` → `name_erfassen` → `problem_erfassen` (WAITING)
- Variable `kunde_name` was set to "hallo" (user input)
- Only 1 assistant message visible: "Willkommen beim Kundenservice! Ich helfe Ihnen gerne weiter."
- Missing: "Wie lautet Ihr vollständiger Name?" and "Wie kann ich Ihnen heute helfen?"

**Backend Logs Show:**
- ✅ Backend correctly queues TTS messages
- ✅ Backend emits `agent_message` events via LiveKit data channel
- ✅ All nodes execute successfully (start → name_erfassen → problem_erfassen)
- ✅ TTS messages are queued for BOTH elicitation nodes

## Root Cause Analysis

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (TypeScript)                        │
│                                                                  │
│  FlowExecutor                                                    │
│    ├─> NodeOutputHandler                                        │
│    │     └─> emitTTSMessage()                                   │
│    │           └─> livekitDataChannelService.sendEventToRoom()  │
│    │                 └─> Sends "agent_message" event            │
│    │                                                             │
│    └─> /api/flows/:flowId/process endpoint                      │
│          └─> Returns { response, streaming, completed }         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ LiveKit Data Channel
                              │ Topic: "flow-events"
                              │ Event: "agent_message"
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AGENT WORKER (Python)                          │
│                                                                  │
│  agent.py::AICOAgent                                            │
│    └─> on_user_turn_completed()                                │
│          ├─> flow_executor.process_user_input()  [HTTP call]   │
│          │     └─> POST /api/flows/:flowId/process             │
│          │           └─> Returns response + streaming flag      │
│          │                                                       │
│          └─> PROBLEM: Only uses HTTP response, NOT data channel │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Critical Issue

**TWO SEPARATE MESSAGE CHANNELS:**

1. **LiveKit Data Channel** (`agent_message` events)
   - Backend sends TTS messages via `livekitDataChannelService.sendEventToRoom()`
   - Events go to topic: `"flow-events"`
   - Contains: `{ type: "agent_message", data: { content, nodeId, ... } }`
   - ✅ ALL messages are sent this way (start, elicitation, etc.)

2. **HTTP Response** (from `/api/flows/:flowId/process`)
   - Agent worker calls this endpoint
   - Backend returns: `{ response, streaming, completed }`
   - `response` field contains ONLY NEW assistant messages from conversation history
   - ❌ This is what the agent worker uses to speak

**The Race Condition:**

```python
# In agent.py::on_user_turn_completed()

# 1. Agent calls backend
response, is_streaming = await flow_exec.process_user_input(user_text)

# 2. Backend executes nodes and emits agent_message events via data channel
#    (happens DURING the HTTP request)

# 3. HTTP response returns with response field
#    BUT: response is built from conversation.slice(conversationLengthBefore)
#    For non-LLM nodes (elicitation), NO conversation messages are added!

# 4. Agent checks if response exists
if not is_streaming:
    if response and response.strip():
        await self.agent_session.say(response)  # ❌ response is None/empty!
    else:
        logger.debug("No response to speak from non-streaming node")  # ❌ Logs this
```

### Why Chat Mode Works

In chat mode, the flow executor works differently:
- Chat mode doesn't rely on the `response` field from HTTP
- Frontend listens to LiveKit data channel events directly
- When `agent_message` event arrives, frontend displays it immediately
- No dependency on HTTP response content

### Why Audio Mode Fails

In audio mode:
- Agent worker ignores LiveKit data channel `agent_message` events
- Agent worker only speaks what's in HTTP `response` field  
- For non-LLM nodes (start, elicitation), backend doesn't add to conversation
- Backend ONLY queues TTS messages via data channel
- Result: No `response` → no speech

### Why First Message Works

The first message (start node greeting) works because:
1. `start_flow()` is called with empty input
2. Backend executes Start node
3. Start node emits TTS message via data channel
4. **AND** adds greeting to HTTP response as `initialGreeting`
5. Agent speaks the `initialGreeting` before entering main loop

## Evidence from Logs

### Backend Correctly Emits All TTS Messages

```
8:10:13 PM ℹ 📢 TTS output detected { nodeId: 'start', contentLength: 60 }
8:10:13 PM ℹ 📡 LiveKit sendEventToRoom called { eventType: 'agent_message' }

8:10:13 PM ℹ 📢 TTS output detected { nodeId: 'name_erfassen', contentLength: 34 }
8:10:13 PM ℹ 📡 LiveKit sendEventToRoom called { eventType: 'agent_message' }

8:10:24 PM ℹ 📢 TTS output detected { nodeId: 'problem_erfassen', contentLength: 68 }
8:10:13 PM ℹ 📡 LiveKit sendEventToRoom called { eventType: 'agent_message' }
```

All three messages sent via data channel! ✅

### Backend HTTP Response is Empty

```
8:10:24 PM ℹ 📤 Flow response built {
  hasResponse: false,  // ❌ No response!
  responseLength: 0,
  streaming: false,
  newMessagesCount: 0  // ❌ No new messages!
}
```

### Agent Worker Logs Missing Messages

```python
# Agent logs show:
logger.info(f"Backend response received: has_response={response is not None}, is_streaming={is_streaming}")
# Output: has_response=False, is_streaming=False

logger.info("🚀 Non-streaming node detected - speaking response immediately")
if response and response.strip():
    await self.agent_session.say(response)  # ❌ Never called because response is None
else:
    logger.debug("No response to speak from non-streaming node")  # ✅ This is logged
```

## The Architectural Problem

### Current Flow (BROKEN)

```
Node Executes
  └─> NodeOutputHandler.handleNodeResult()
        ├─> Stores output in nodeOutputs map
        ├─> Emits TTS via data channel (agent_message)  ← Agent IGNORES this
        └─> DOESN'T add to conversation (for non-LLM nodes)
                  
FlowExecutor.processUserInput() completes
  └─> Returns HTTP response
        └─> response = conversation.slice(before).filter(assistant)  ← EMPTY!
        
Agent Worker receives HTTP response
  └─> if response: speak(response)  ← response is None, never speaks!
```

### Why This Design is Flawed

1. **Dual Message Channels**: Backend uses BOTH data channel AND HTTP response
   - Data channel: Real-time events (used by frontend)
   - HTTP response: Batch response (used by agent)
   - These are NOT synchronized!

2. **Conversation History Only Tracks LLM**: Non-LLM nodes don't add to conversation
   - Start, Elicitation, SetVariable nodes emit TTS
   - But don't add to `context.conversation`
   - HTTP response is built from conversation → empty for these nodes

3. **Agent Worker Deaf to Data Channel**: Agent only listens to HTTP response
   - Data channel listener exists ONLY for LLM streaming tokens
   - `agent_message` events are sent but never processed
   - Agent has no way to receive non-LLM TTS messages

## Solution Design

### Option 1: Make Agent Listen to Data Channel (RECOMMENDED)

**Pros:**
- Centralized message delivery (all messages via data channel)
- Real-time message delivery (no HTTP roundtrip delay)
- Consistent with frontend architecture
- Scales better (less HTTP traffic)

**Cons:**
- Requires agent worker changes
- Need to handle message ordering/deduplication

**Implementation:**
```python
# In agent.py::on_user_turn_completed()

# Set up data channel listener for ALL agent_message events
async def handle_agent_message(data_payload: Any):
    event = json.loads(payload_bytes.decode('utf-8'))
    
    if event.get("type") == "agent_message" and event.get("sessionId") == session_id:
        message_content = event["data"]["content"]
        node_id = event["data"]["nodeId"]
        
        # Speak immediately when message arrives
        await self.agent_session.say(message_content, add_to_chat_ctx=True)

@room.on("data_received")
def on_data(data, topic=""):
    if topic == "flow-events":
        asyncio.create_task(handle_agent_message(data))

# Still call backend to advance flow state
response, is_streaming = await flow_exec.process_user_input(user_text)

# But don't rely on response field for speaking
# (already handled by data channel listener above)
```

### Option 2: Make Backend Include TTS in HTTP Response

**Pros:**
- Minimal agent worker changes
- Simpler message delivery (single channel)

**Cons:**
- Duplicates message delivery logic
- Loses real-time streaming benefits
- HTTP response becomes bloated

**Implementation:**
```typescript
// In flowRoutes.ts::POST /api/flows/:flowId/process

// Collect TTS messages from executor
const ttsMessages = executor.getContext().ttsQueue || [];

return successResponse({
  sessionId: state.sessionId,
  status: state.status,
  response: response,
  ttsMessages: ttsMessages.map(msg => msg.content),  // NEW: Include TTS queue
  streaming,
  completed: state.status === "completed"
});
```

```python
# In flow_executor.py::process_user_input()

data = response.json()
message = data.get("response")
tts_messages = data.get("ttsMessages", [])  # NEW: Get TTS queue

# Return all TTS messages
return ("\n\n".join(tts_messages), streaming)
```

### Option 3: Hybrid Approach (BEST)

Use data channel for real-time delivery, fallback to HTTP response:

```python
# Collect messages from both sources
messages_spoken = []

# 1. Listen to data channel for real-time messages
@room.on("data_received")
def on_agent_message(data):
    if event["type"] == "agent_message":
        messages_spoken.append(event["data"]["content"])
        await session.say(event["data"]["content"])

# 2. Trigger backend execution
response, streaming = await flow_exec.process_user_input(input)

# 3. If data channel failed, fallback to HTTP response
if not messages_spoken and response:
    await session.say(response)
```

## Recommended Fix

**Implement Option 1** (Data Channel Listener)

### Phase 1: Agent Worker Changes

1. Add global data channel listener in `entrypoint()` function
2. Listen for `agent_message` events on topic `"flow-events"`
3. Speak messages immediately when received
4. Remove dependency on HTTP `response` field

### Phase 2: Clean Up Architecture

1. Remove `response` field from HTTP response (deprecated)
2. Document that TTS delivery is ONLY via data channel
3. Update flow executor to NOT build conversation-based responses
4. Add message deduplication/ordering in agent

### Phase 3: Testing

1. Test audio mode with multiple elicitation nodes
2. Test streaming LLM nodes (ensure token streaming still works)
3. Test chat mode (should be unaffected)
4. Test rapid user input (ensure no message loss)

## Implementation Priority

**CRITICAL** - This breaks core functionality in audio mode
- Users cannot use voice flows at all
- Only workaround is chat mode (not acceptable for phone calls)

**Complexity**: Medium
- Agent worker changes: ~100 lines
- Backend changes: None needed (already working)
- Testing: 2-3 hours

**Risk**: Low
- Data channel already works (proven by chat mode)
- Can implement with fallback to HTTP response
- Easy to rollback if issues occur

---

## Next Steps

1. ✅ Analyze architecture and identify root cause
2. ⬜ Implement data channel listener in agent worker
3. ⬜ Test with demo-flow in audio mode
4. ⬜ Verify all node types work (start, elicitation, LLM, etc.)
5. ⬜ Deploy and monitor production
