# LLM→TTS Streaming Implementation Guide

## ✅ Completed

### 1. PiperTTS Streaming (agent-worker/plugins/piper_tts.py)
- **Enabled**: `stream=True` in output_emitter.initialize()
- **Capability**: `streaming=True` in TTSCapabilities
- **Chunk size**: Reduced to 4KB for ~90ms latency (down from 8KB)
- **Result**: Audio streams to user in real-time chunks

### 2. Sentence Buffer (agent-worker/streaming_buffer.py)
- **Created**: `SentenceStreamBuffer` class
- **Features**:
  - Detects sentence boundaries (. ! ? followed by space/newline)
  - Handles paragraph breaks (double newlines)
  - Minimum sentence length to avoid splitting abbreviations
  - Configurable min_sentence_length (default: 20 chars)
- **Helper**: `stream_with_sentences()` async function for easy integration

## 🚧 TODO: Backend LLM Streaming

Currently, LLM responses are buffered completely before being sent to the agent. For true low-latency streaming, we need:

### Phase 1: Emit Streaming Tokens

**File**: `backend/src/core/flow-executor/executors/LLMNodeExecutor.ts`

**Current** (lines 167-186):
```typescript
const llmResponse = await llmClient.streamChat(
  messages,
  async (chunk) => {
    // TODO: Emit streaming tokens via LiveKit data channels
    // Currently tokens are only available in final response
  },
  { temperature, maxTokens }
);
```

**Needed**:
```typescript
const llmResponse = await llmClient.streamChat(
  messages,
  async (chunk) => {
    // Emit token to FlowExecutor event bus
    this.emitStreamingToken(chunk.content);
  },
  { temperature, maxTokens }
);
```

### Phase 2: Pass Event Emitter to Executors

**File**: `backend/src/services/flowExecutor.ts`

Modify `executeNode()` to pass event emitter:
```typescript
result = await nodeRegistry.executeNode(
  node,
  this.context,
  edges,
  this.emitEvent.bind(this)  // Pass event emitter
);
```

### Phase 3: Create Streaming API Endpoint

**File**: `backend/src/routes/flowRoutes.ts`

Add SSE (Server-Sent Events) endpoint:
```typescript
{
  method: 'GET',
  url: '/api/flows/:flowId/stream/:sessionId',
  handler: async (request, reply) => {
    reply.raw.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    });

    const executor = getExecutor(sessionId);

    executor.on('llm.token', (token) => {
      reply.raw.write(`data: ${JSON.stringify({ type: 'token', content: token })}\\n\\n`);
    });

    executor.on('llm.done', (response) => {
      reply.raw.write(`data: ${JSON.stringify({ type: 'done', content: response })}\\n\\n`);
      reply.raw.end();
    });
  }
}
```

### Phase 4: Agent Streaming Client

**File**: `agent-worker/flow_executor.py`

Modify to use SSE endpoint:
```python
async def process_user_input_streaming(self, user_input: str) -> AsyncIterator[str]:
    """Process user input with streaming token support."""
    async with self.http_client.stream(
        "GET",
        f"{self.backend_url}/api/flows/{self.flow_id}/stream/{self.session_id}",
        params={"input": user_input}
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data["type"] == "token":
                    yield data["content"]
                elif data["type"] == "done":
                    break
```

### Phase 5: Integrate Sentence Buffer in Agent

**File**: `agent-worker/agent.py`

Replace buffered response with streaming:
```python
from streaming_buffer import stream_with_sentences

# Inside on_new_message handler:
if self.using_flow and self.flow_executor:
    async def speak_sentence(sentence: str):
        await cast(AgentSession, self.agent_session).say(
            sentence,
            allow_interruptions=True,
            add_to_chat_ctx=False  # Add to context after all sentences
        )

    full_response = await stream_with_sentences(
        flow_exec.process_user_input_streaming(user_text),
        speak_sentence,
        min_sentence_length=20
    )

    # Add complete response to chat context
    turn_ctx.add_message(content=full_response, role="assistant")
```

## Performance Improvements

### Current Architecture (Buffered)
```
User speaks → STT → Agent → Backend LLM (3-5s) → Complete response → TTS (2-3s) → Audio
Total latency: ~5-8 seconds
```

### With Streaming (Target)
```
User speaks → STT → Agent → Backend LLM streams tokens →
                                ↓ (100ms per token)
                          Sentence buffer →
                                ↓ (every 10-20 tokens)
                          TTS streams audio →
                                ↓ (90ms chunks)
                          User hears response
First words latency: ~1-2 seconds
```

**Latency Reduction**: ~70-80% for first words spoken
**User Experience**: Feels more natural and conversational

## Alternative: Use OpenAI Streaming API Directly

For even faster implementation, bypass backend flow streaming and use OpenAI's streaming API directly in the agent:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

async with client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": user_text}],
    stream=True
) as stream:
    async for sentence in stream_with_sentences(
        (chunk.choices[0].delta.content async for chunk in stream),
        speak_sentence
    ):
        pass  # speaking handled in callback
```

This works but bypasses the flow system entirely. Good for prototyping.

## Recommendations

1. **Short term**: Current implementation with Piper streaming enabled is good
2. **Medium term**: Implement backend SSE streaming (Phases 1-5 above)
3. **Long term**: Consider switching to streaming TTS provider (ElevenLabs, Azure)

## Testing Streaming

To verify Piper streaming is working:
```bash
# Check agent logs for reduced latency
tail -f logs/agent.log | grep "TTS"

# Should see audio chunks being sent in real-time, not all at once
```
