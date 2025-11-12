# Agent Flow Architecture

## Overview

This document describes the comprehensive, extensible architecture for building complex agent flows in the AICO LiveKit system. The architecture is designed to be **DRY** (Don't Repeat Yourself), **clean** (clear separation of concerns), and **highly extensible** (easy to add new functionality).

## Table of Contents

1. [Architecture Principles](#architecture-principles)
2. [Core Components](#core-components)
3. [Type System](#type-system)
4. [Node Types](#node-types)
5. [Execution Engine](#execution-engine)
6. [Instruction System](#instruction-system)
7. [Tool Registry](#tool-registry)
8. [Frontend Integration](#frontend-integration)
9. [Python Agent Worker Integration](#python-agent-worker-integration)
10. [Example Flows](#example-flows)
11. [Extending the System](#extending-the-system)

---

## Architecture Principles

### 1. Separation of Concerns

The architecture is divided into clear layers:

- **Type System** (`types/agentFlow.ts`): TypeScript type definitions for all flow components
- **Services** (`services/`): Business logic for instruction compilation, tool registry, and flow execution
- **Database** (`db/schema.ts`): Data persistence with Drizzle ORM
- **Frontend** (`frontend/src/lib/components/flow/`): Visual flow builder with XYFlow
- **Agent Worker** (`agent-worker/flow_executor.py`): Python integration with LiveKit agents

### 2. Extensibility by Design

- **Node Types**: Easy to add new node types by extending the discriminated union
- **Tools**: Dynamic tool registration at runtime
- **Instructions**: Hierarchical instruction system (global → flow → node)
- **Execution Engine**: Event-driven architecture for real-time updates

### 3. Type Safety

- Full TypeScript types for compile-time safety
- Discriminated unions for node types
- Generic interfaces for extensibility

### 4. LiveKit & XYFlow Integration

- **LiveKit**: Full integration with AgentSession, tools, and realtime communication
- **XYFlow**: Custom node components, visual editing, and flow validation

---

## Core Components

### 1. Type System (`backend/src/types/agentFlow.ts`)

Comprehensive type definitions for:

- **Flow Structure**: `AgentFlowDefinition`, `FlowNode`, `FlowEdge`
- **Node Types**: 9 node types (start, elicitation, decision, tool, llm, transfer, end, wait, parallel, merge)
- **Execution State**: `FlowExecutionState`, `ExecutionContext`, `ExecutionStatus`
- **Tools**: `ToolDefinition`, `ToolExecutionContext`, `ToolExecutionResult`
- **Instructions**: `InstructionSet`, `CompiledInstructions`
- **Configuration**: `FlowConfiguration`, `ErrorHandlingStrategy`

**Key Features**:
- Discriminated unions for type-safe node handling
- Extensible metadata fields
- Parameter definition system for tools
- Validation rules for user input

### 2. Instruction Service (`backend/src/services/instructionService.ts`)

Hierarchical instruction system with three levels:

1. **Global Instructions**: System-wide defaults
2. **Flow Instructions**: Specific to a flow
3. **Node Instructions**: Highest priority, specific to a node

**Key Features**:
- Instruction composition and inheritance
- Variable interpolation (`{{variable}}` syntax)
- Template validation
- Predefined templates (customer service, sales, technical support, etc.)
- Context-aware compilation

**Example**:
```typescript
const compiled = InstructionService.compileInstructions(
  { global, flow, node },
  executionContext,
  currentNode
);
// Returns: { system, context, history }
```

### 3. Tool Registry (`backend/src/services/toolRegistry.ts`)

Extensible tool registration and execution system.

**Key Features**:
- Dynamic tool registration at runtime
- Type-safe parameter validation
- Automatic OpenAI function calling format export
- Built-in tools (echo, get_current_time, store_variable, calculate)
- Tool discovery by category and tags
- Execution timing and error handling

**Example**:
```typescript
import { ToolRegistry, createTool } from './toolRegistry';

const registry = ToolRegistry.getInstance();

// Register a custom tool
registry.register(
  {
    name: 'lookup_weather',
    description: 'Get weather for a location',
    category: 'api',
    parameters: {
      location: {
        type: 'string',
        description: 'City name',
        required: true
      }
    }
  },
  async (context, params) => {
    // Tool implementation
    const weather = await fetchWeather(params.location);
    return {
      success: true,
      output: weather
    };
  }
);

// Execute tool
const result = await registry.execute('lookup_weather', context, { location: 'Berlin' });
```

### 4. Flow Executor (`backend/src/services/flowExecutor.ts`)

Core execution engine that interprets and runs flows.

**Key Features**:
- State machine for node execution
- Event-driven architecture (extends EventEmitter)
- Context management and variable storage
- Condition evaluation for decision nodes
- Tool execution integration
- User input handling
- Error handling and recovery
- Real-time event emission

**Example**:
```typescript
import { FlowExecutor } from './flowExecutor';

const executor = new FlowExecutor(
  flowDefinition,
  { organizationId: 'org123', variables: {} },
  { global: 'You are a helpful assistant' }
);

// Listen to events
executor.on('node.entered', (event) => {
  console.log('Entered node:', event.data);
});

// Start execution
await executor.start();

// Process user input
await executor.processUserInput('Hello!');

// Get current state
const state = executor.getState();
```

### 5. Database Schema (`backend/src/db/schema.ts`)

Three main tables for agent flows:

1. **agentFlows**: Flow definitions
   - `id`, `organizationId`, `name`, `slug`, `description`
   - `definition` (JSONB): Flow nodes, edges, viewport
   - `configuration` (JSONB): FlowConfiguration
   - `metadata` (JSONB): Additional data

2. **flowExecutionSessions**: Execution state
   - `id`, `sessionId`, `organizationId`, `flowId`, `roomName`, `userId`
   - `currentNodeId`, `status`
   - `context` (JSONB): ExecutionContext
   - `history` (JSONB): ExecutionHistoryEntry[]
   - Timestamps: `startedAt`, `lastActivityAt`, `endedAt`

3. **toolDefinitions**: Registered tools
   - `id`, `organizationId`, `name`, `description`, `category`
   - `parameters` (JSONB): ParameterDefinition[]
   - `handler`, `isBuiltIn`, `isEnabled`
   - `metadata` (JSONB)

---

## Node Types

### 1. Start Node
**Purpose**: Entry point for the flow

**Configuration**:
- `greeting`: Optional greeting message
- `variables`: Initial context variables

**Behavior**: Initializes context and transitions to next node

---

### 2. Elicitation Node
**Purpose**: Gather information from user

**Configuration**:
- `prompt`: Question to ask (supports variable interpolation)
- `variable`: Variable name to store answer
- `validations`: Optional validation rules (regex, length, range)
- `retryPrompt`: Message on validation failure
- `maxRetries`: Maximum retry attempts
- `required`: Whether answer is required

**Behavior**:
1. Sends prompt to user
2. Waits for response
3. Validates input
4. Stores in variable
5. Transitions to next node

**Example**:
```json
{
  "type": "elicitation",
  "data": {
    "prompt": "What is your name?",
    "variable": "user_name",
    "required": true,
    "validations": [
      {
        "type": "length",
        "value": { "min": 2, "max": 50 },
        "message": "Name must be 2-50 characters"
      }
    ]
  }
}
```

---

### 3. Decision Node
**Purpose**: Branching logic based on conditions

**Configuration**:
- `conditions`: Array of condition objects
  - `expression`: Condition to evaluate (supports variable interpolation)
  - `targetEdge`: Edge ID to follow if true
  - `description`: Human-readable description
- `defaultBranch`: Edge ID to follow if no condition matches

**Behavior**:
1. Evaluates conditions in order
2. Follows first matching condition
3. Falls back to default branch if no match

**Example**:
```json
{
  "type": "decision",
  "data": {
    "conditions": [
      {
        "id": "happy_path",
        "expression": "{{mood}} === 'happy'",
        "targetEdge": "edge_to_celebration",
        "description": "User is happy"
      },
      {
        "id": "sad_path",
        "expression": "{{mood}} === 'sad'",
        "targetEdge": "edge_to_support",
        "description": "User needs support"
      }
    ],
    "defaultBranch": "edge_to_neutral"
  }
}
```

---

### 4. Tool Node
**Purpose**: Execute a tool/function

**Configuration**:
- `toolName`: Name of registered tool
- `parameters`: Parameter definitions
  - `source`: 'context' | 'user' | 'literal'
  - `value`: Value or variable reference
- `outputVariable`: Variable to store result
- `continueOnError`: Continue flow if tool fails
- `errorHandler`: Edge ID to follow on error

**Behavior**:
1. Resolves parameters from context
2. Executes tool via registry
3. Stores output if specified
4. Handles errors based on configuration

**Example**:
```json
{
  "type": "tool",
  "data": {
    "toolName": "lookup_weather",
    "parameters": {
      "location": {
        "source": "context",
        "value": "user_location"
      }
    },
    "outputVariable": "weather_data",
    "continueOnError": false
  }
}
```

---

### 5. LLM Node
**Purpose**: Call LLM with specific instructions

**Configuration**:
- `prompt`: Prompt template (supports variable interpolation)
- `model`: Override default model
- `temperature`: Override default temperature
- `maxTokens`: Max tokens for response
- `outputVariable`: Variable to store LLM response
- `systemInstructions`: Override system instructions
- `tools`: Available tools for this LLM call

**Behavior**:
1. Compiles instructions
2. Interpolates prompt with variables
3. Calls LLM via backend API
4. Stores response if specified

**Example**:
```json
{
  "type": "llm",
  "data": {
    "prompt": "Analyze the user's mood based on: {{user_message}}",
    "outputVariable": "mood_analysis",
    "temperature": 0.7,
    "systemInstructions": "You are a mood analysis expert."
  }
}
```

---

### 6. Transfer Node
**Purpose**: Hand off to another agent or flow

**Configuration**:
- `targetAgent`: Agent name/ID to transfer to
- `targetFlow`: Flow name/ID to transfer to
- `transferMessage`: Message to user during transfer
- `context`: Context to pass to new agent
- `returnOnComplete`: Return to this flow after completion

**Behavior**:
1. Sends transfer message if specified
2. Emits transfer event
3. Initiates handoff to target

---

### 7. End Node
**Purpose**: Terminal node

**Configuration**:
- `message`: Final message to user
- `reason`: 'success' | 'error' | 'timeout' | 'user_exit'
- `collectFeedback`: Ask for feedback before ending
- `feedbackPrompt`: Custom feedback prompt

**Behavior**:
1. Sends final message if specified
2. Marks flow as completed
3. Emits completion event

---

### 8. Wait Node
**Purpose**: Wait for external event

**Configuration**:
- `eventType`: Type of event to wait for
- `timeout`: Timeout in milliseconds
- `timeoutBranch`: Edge ID to follow on timeout

---

### 9. Parallel Node
**Purpose**: Execute multiple branches simultaneously

**Configuration**:
- `branches`: Array of edge IDs to execute in parallel
- `waitForAll`: Wait for all branches or continue on first

---

### 10. Merge Node
**Purpose**: Merge parallel branches

**Configuration**:
- `mergeStrategy`: 'first' | 'all' | 'custom'

---

## Execution Engine

### State Machine

The flow executor maintains execution state and transitions between nodes.

**States**:
- `pending`: Waiting to start
- `running`: Currently executing
- `waiting`: Waiting for user input or event
- `paused`: Paused by system or user
- `completed`: Successfully completed
- `failed`: Failed with error
- `cancelled`: Cancelled by user or system
- `timeout`: Timed out

### Event System

The executor emits events for real-time updates:

- `flow.started`: Flow execution started
- `flow.completed`: Flow execution completed
- `flow.failed`: Flow execution failed
- `node.entered`: Entered a node
- `node.exited`: Exited a node
- `node.error`: Node execution error
- `tool.called`: Tool called
- `tool.completed`: Tool completed
- `user.input`: User provided input
- `agent.response`: Agent responded
- `transfer.initiated`: Transfer initiated
- `transfer.completed`: Transfer completed

---

## Frontend Integration

### Custom XYFlow Nodes

Located in `frontend/src/lib/components/flow/nodes/`:

- **BaseNode.svelte**: Reusable base component for all nodes
- **ElicitationNode.svelte**: Displays elicitation configuration
- **ToolNode.svelte**: Displays tool configuration
- **DecisionNode.svelte**: Displays branching conditions

**Features**:
- Consistent styling
- Theme support (light/dark)
- Visual indicators (required, validation, error)
- Custom handles for decision branches
- Truncation for long text

### Node Type Registry

```typescript
import { nodeTypes } from './components/flow/nodes';

// Use in XYFlow
<SvelteFlow {nodes} {edges} {nodeTypes} />
```

### Flow Builder Integration

Update `FlowBuilderPage.svelte` to use custom node types:

```svelte
<script>
  import { SvelteFlow } from '@xyflow/svelte';
  import { nodeTypes } from '$lib/components/flow/nodes';

  let nodes = $state([...]);
  let edges = $state([...]);
</script>

<SvelteFlow
  {nodes}
  {edges}
  {nodeTypes}
  fitView
/>
```

---

## Python Agent Worker Integration

### Flow Executor (`agent-worker/flow_executor.py`)

Python class that integrates with LiveKit agents:

**Key Methods**:
- `load_flow(flow_id, organization_id)`: Load flow from backend
- `start_execution(...)`: Start flow execution
- `process_user_input(input_text)`: Process user input
- `get_latest_assistant_message()`: Get latest agent response

**Example Integration**:

```python
# In agent.py

from flow_executor import FlowExecutor

async def entrypoint(ctx: JobContext):
    # Extract metadata
    flow_id = ctx.job.metadata.get('flowId')
    org_id = ctx.job.metadata.get('organizationId')

    # Initialize flow executor
    flow_executor = FlowExecutor(
        backend_url=AICO_BACKEND_URL,
        api_key=AICO_INTERNAL_API_KEY
    )

    if flow_id:
        # Load and start flow
        await flow_executor.load_flow(flow_id, org_id)
        await flow_executor.start_execution(
            organization_id=org_id,
            room_name=ctx.room.name
        )

        # Get initial greeting if any
        greeting = flow_executor.get_latest_assistant_message()
        if greeting:
            # Send greeting to user via TTS
            await tts.say(greeting)

    # Set up AgentSession
    session = AgentSession(...)

    # Handle user speech
    @session.on("user_speech")
    async def on_user_speech(speech_text: str):
        if flow_executor.state and flow_executor.state.status == ExecutionStatus.WAITING:
            # Process input through flow
            response = await flow_executor.process_user_input(speech_text)
            if response:
                await tts.say(response)
        else:
            # Default LLM handling
            response = await get_llm_response(speech_text)
            await tts.say(response)
```

---

## Example Flows

### Example 1: Customer Support Flow

```json
{
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "position": { "x": 250, "y": 0 },
      "data": {
        "greeting": "Hello! How can I help you today?",
        "variables": {}
      }
    },
    {
      "id": "ask_issue",
      "type": "elicitation",
      "position": { "x": 250, "y": 100 },
      "data": {
        "label": "Ask for Issue",
        "prompt": "Can you describe the issue you're experiencing?",
        "variable": "user_issue",
        "required": true
      }
    },
    {
      "id": "analyze_sentiment",
      "type": "llm",
      "position": { "x": 250, "y": 200 },
      "data": {
        "label": "Analyze Sentiment",
        "prompt": "Analyze the sentiment of: {{user_issue}}. Respond with 'urgent', 'normal', or 'low'.",
        "outputVariable": "issue_priority",
        "systemInstructions": "You are a sentiment analyzer for customer support."
      }
    },
    {
      "id": "priority_check",
      "type": "decision",
      "position": { "x": 250, "y": 300 },
      "data": {
        "label": "Check Priority",
        "conditions": [
          {
            "id": "urgent",
            "expression": "{{issue_priority}} === 'urgent'",
            "targetEdge": "edge_to_escalate"
          },
          {
            "id": "normal",
            "expression": "{{issue_priority}} === 'normal'",
            "targetEdge": "edge_to_standard"
          }
        ],
        "defaultBranch": "edge_to_low"
      }
    },
    {
      "id": "escalate",
      "type": "transfer",
      "position": { "x": 100, "y": 400 },
      "data": {
        "label": "Escalate to Human",
        "transferMessage": "I'm transferring you to a human agent who can help with your urgent issue.",
        "targetAgent": "human_support"
      }
    },
    {
      "id": "standard_support",
      "type": "llm",
      "position": { "x": 250, "y": 400 },
      "data": {
        "label": "Provide Standard Support",
        "prompt": "Provide helpful support for: {{user_issue}}",
        "outputVariable": "support_response"
      }
    },
    {
      "id": "end",
      "type": "end",
      "position": { "x": 250, "y": 500 },
      "data": {
        "message": "Is there anything else I can help you with?",
        "collectFeedback": true
      }
    }
  ],
  "edges": [
    { "id": "e1", "source": "start", "target": "ask_issue" },
    { "id": "e2", "source": "ask_issue", "target": "analyze_sentiment" },
    { "id": "e3", "source": "analyze_sentiment", "target": "priority_check" },
    { "id": "edge_to_escalate", "source": "priority_check", "target": "escalate" },
    { "id": "edge_to_standard", "source": "priority_check", "target": "standard_support" },
    { "id": "e6", "source": "standard_support", "target": "end" }
  ]
}
```

### Example 2: Appointment Booking Flow

```json
{
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "data": {
        "greeting": "I can help you book an appointment. Let's get started!"
      }
    },
    {
      "id": "ask_name",
      "type": "elicitation",
      "data": {
        "prompt": "What's your name?",
        "variable": "customer_name",
        "required": true
      }
    },
    {
      "id": "ask_date",
      "type": "elicitation",
      "data": {
        "prompt": "What date would you like to book? (e.g., 2024-03-15)",
        "variable": "preferred_date",
        "required": true,
        "validations": [
          {
            "type": "regex",
            "value": "\\d{4}-\\d{2}-\\d{2}",
            "message": "Please use YYYY-MM-DD format"
          }
        ]
      }
    },
    {
      "id": "check_availability",
      "type": "tool",
      "data": {
        "label": "Check Availability",
        "toolName": "check_calendar_availability",
        "parameters": {
          "date": {
            "source": "context",
            "value": "preferred_date"
          }
        },
        "outputVariable": "available_slots"
      }
    },
    {
      "id": "slots_available",
      "type": "decision",
      "data": {
        "conditions": [
          {
            "id": "has_slots",
            "expression": "{{available_slots}}.length > 0",
            "targetEdge": "edge_to_book"
          }
        ],
        "defaultBranch": "edge_to_no_slots"
      }
    },
    {
      "id": "book_appointment",
      "type": "tool",
      "data": {
        "toolName": "book_appointment",
        "parameters": {
          "name": { "source": "context", "value": "customer_name" },
          "date": { "source": "context", "value": "preferred_date" },
          "slot": { "source": "context", "value": "selected_slot" }
        },
        "outputVariable": "booking_confirmation"
      }
    },
    {
      "id": "confirm",
      "type": "end",
      "data": {
        "message": "Great! Your appointment is confirmed for {{preferred_date}}. Confirmation number: {{booking_confirmation}}"
      }
    }
  ],
  "edges": [...]
}
```

---

## Extending the System

### Adding a New Node Type

1. **Define Type** in `types/agentFlow.ts`:
```typescript
export interface CustomNode extends BaseFlowNode {
  type: 'custom';
  data: NodeData & {
    customField: string;
    // ... other fields
  };
}

// Add to discriminated union
export type FlowNode =
  | StartNode
  | ElicitationNode
  | CustomNode  // Add here
  | ...
```

2. **Add Execution Logic** in `services/flowExecutor.ts`:
```typescript
private async executeCurrentNode(): Promise<void> {
  switch (node.type) {
    // ... existing cases
    case 'custom':
      output = await this.executeCustomNode(node);
      break;
  }
}

private async executeCustomNode(node: CustomNode): Promise<unknown> {
  // Implementation
}
```

3. **Create Frontend Component** `CustomNode.svelte`:
```svelte
<script lang="ts">
  import BaseNode from './BaseNode.svelte';
  // ... props
</script>

<BaseNode data={nodeData} {selected}>
  <!-- Custom UI -->
</BaseNode>
```

4. **Register in Node Types**:
```typescript
export const nodeTypes = {
  // ... existing
  custom: CustomNode,
};
```

### Adding a New Tool

```typescript
import { ToolRegistry } from './toolRegistry';

const registry = ToolRegistry.getInstance();

registry.register(
  {
    name: 'my_custom_tool',
    description: 'Does something custom',
    category: 'custom',
    parameters: {
      param1: {
        type: 'string',
        description: 'First parameter',
        required: true
      }
    }
  },
  async (context, params) => {
    // Tool implementation
    const result = await doSomething(params.param1);
    return {
      success: true,
      output: result
    };
  }
);
```

### Adding Custom Instructions

```typescript
import { InstructionService } from './instructionService';

const customInstructions = `
You are a specialized assistant for [specific domain].

Key behaviors:
- [Behavior 1]
- [Behavior 2]
- [Behavior 3]
`;

const compiled = InstructionService.compileInstructions(
  { global: customInstructions },
  context,
  node
);
```

---

## Best Practices

### 1. Flow Design

- **Keep flows focused**: Each flow should have a clear purpose
- **Use descriptive labels**: Make nodes easy to understand
- **Add descriptions**: Help future maintainers understand intent
- **Test branching logic**: Ensure all paths are reachable
- **Handle errors gracefully**: Use `continueOnError` when appropriate

### 2. Variable Naming

- Use clear, descriptive names: `user_name` not `un`
- Follow consistent conventions: snake_case for variables
- Namespace related variables: `order_id`, `order_total`, `order_status`

### 3. Instruction Writing

- Be specific about expected behavior
- Use examples when helpful
- Keep instructions concise
- Layer instructions (global → flow → node) for flexibility

### 4. Tool Development

- Make tools single-purpose
- Provide clear descriptions
- Validate parameters thoroughly
- Handle errors gracefully
- Return structured data

### 5. Testing

- Test individual nodes in isolation
- Test complete flow paths
- Test error conditions
- Test with real LiveKit sessions
- Monitor execution events

---

## Conclusion

This architecture provides a solid foundation for building complex, extensible agent flows. The separation of concerns, type safety, and clean abstractions make it easy to:

- Add new node types
- Register custom tools
- Customize instructions
- Extend execution logic
- Build rich UIs
- Integrate with LiveKit

The system is production-ready and can scale to handle sophisticated agent behaviors while remaining maintainable and extensible.

For questions or contributions, refer to the codebase documentation and examples.
