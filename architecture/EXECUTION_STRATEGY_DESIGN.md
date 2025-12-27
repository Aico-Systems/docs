# Flow Execution Strategy - Future-Proof Design

## Problem Statement

The current FlowExecutor has two execution modes that conflict:

1. **DAG/Parallel Mode** (default) - Executes ALL branches in parallel
2. **Sequential Mode** - Follows one path but has edge routing bugs

**Critical Issue**: Voice agent flows with conditional branching (e.g., "if damage report → path A, if status inquiry → path B") execute ALL paths simultaneously in DAG mode, breaking the flow logic.

## Industry Analysis

### Temporal.io Approach
```typescript
// Explicit primitives
workflow.sequence([step1, step2]);
workflow.parallel([stepA, stepB]);
workflow.choice(condition, pathA, pathB);
```
✅ Clear intent  
❌ Verbose, code-heavy

### AWS Step Functions Approach
```json
{
  "Type": "Choice",
  "Choices": [{
    "Variable": "$.type",
    "StringEquals": "damage",
    "Next": "DamagePath"
  }]
}
```
✅ Declarative  
✅ Explicit state types  
❌ Requires different node types for routing

### n8n / Node-RED Approach
- Regular nodes → all outgoing edges execute
- Switch/Router nodes → ONE outgoing edge executes
- Edge priority determines order

✅ Visual, intuitive  
✅ Works with existing graph structure  
❌ Implicit behavior

## Our Solution: Hybrid Strategy with Edge Routing Protocol

### Core Principles

1. **Explicit Intent via Edge Types** - Edges declare their routing behavior
2. **Intelligent Default Behavior** - Sane defaults based on node type
3. **Backward Compatible** - Existing flows work with sensible defaults
4. **Future Extensible** - Easy to add new routing strategies

### Edge Routing Protocol

```typescript
interface FlowEdge {
    id: string;
    source: string;
    target: string;
    type?: "default" | "conditional" | "exclusive" | "parallel" | "error" | "timeout";
    label?: string;
    data?: {
        condition?: string;
        priority?: number;
        exclusive?: boolean;  // NEW: Part of exclusive group
        metadata?: Record<string, unknown>;
    };
}
```

**Edge Type Semantics:**

- **`default`** - Standard edge, follows node's routing behavior
- **`conditional`** - Evaluated conditionally (ALL matching conditions execute)
- **`exclusive`** - Part of an exclusive group (ONLY ONE executes)
- **`parallel`** - Always execute in parallel (explicit parallelization)
- **`error`** - Only follows on error
- **`timeout`** - Only follows on timeout

### Node Routing Behaviors

Each node type defines its **default edge routing strategy**:

```typescript
type EdgeRoutingStrategy = 
    | "single"      // Follow exactly ONE edge (exclusive branching)
    | "all"         // Follow ALL edges (parallel execution)
    | "conditional" // Evaluate conditions, follow matching edges
    | "none";       // Terminal node, no edges

const NODE_ROUTING_STRATEGIES: Record<FlowNodeType, EdgeRoutingStrategy> = {
    // Exclusive branching (decision/routing nodes)
    "agenticLLM": "single",       // LLM decides ONE path via action
    "elicitation": "single",      // After collecting input, one path
    "wait": "single",             // After event, one path
    "memory": "single",           // After operation, one path
    "setVariable": "single",      // After setting, one path
    "toolExecutor": "single",     // After tool, one path (success/error)
    
    // Terminal nodes
    "end": "none",
    "transfer": "none",
    
    // Special cases
    "start": "all",               // Start can trigger multiple parallel paths
    "hold": "single",             // Continue after hold
};
```

### Execution Strategy Selection

```typescript
interface FlowExecutionStrategy {
    mode: "sequential" | "dag" | "hybrid";
    
    // Sequential mode options
    sequential?: {
        respectNodeRouting: boolean;  // Use node's nextNodeId
        fallbackToFirstEdge: boolean; // If no routing, use first edge
    };
    
    // DAG mode options
    dag?: {
        enableParallelization: boolean;
        respectExclusiveEdges: boolean; // Don't parallelize exclusive edges
        maxConcurrency?: number;
    };
    
    // Hybrid mode (RECOMMENDED)
    hybrid?: {
        defaultStrategy: "sequential" | "dag";
        overrideByNodeType?: Record<FlowNodeType, "sequential" | "dag">;
    };
}
```

**Flow Metadata Example:**

```json
{
    "metadata": {
        "executionStrategy": {
            "mode": "hybrid",
            "hybrid": {
                "defaultStrategy": "sequential",
                "overrideByNodeType": {
                    "start": "dag"  // Start node can parallelize
                }
            },
            "sequential": {
                "respectNodeRouting": true,
                "fallbackToFirstEdge": true
            },
            "dag": {
                "enableParallelization": true,
                "respectExclusiveEdges": true
            }
        }
    }
}
```

### Exclusive Edge Groups

When AgenticLLM or similar nodes have multiple outgoing edges with labels, they form an **exclusive group**:

```json
{
    "edges": [
        {
            "source": "identify-caller",
            "target": "damage-path",
            "label": "neue_schadensmeldung",
            "type": "exclusive"
        },
        {
            "source": "identify-caller", 
            "target": "status-path",
            "label": "statusabfrage",
            "type": "exclusive"
        }
    ]
}
```

**DAG Scheduler Behavior:**
- Detects exclusive edge group (same source, type="exclusive" or labeled edges from routing node)
- Treats group as ONE parallelization point (not N points)
- Waits for node to provide `nextNodeId` before continuing
- Only executes the selected branch

### Implementation Phases

#### Phase 1: Fix Critical Routing Bugs (IMMEDIATE)
1. ✅ Make sequential mode respect `result.nextNodeId` from AgenticLLM
2. ✅ Fix auto-transition to not override explicit routing
3. ✅ Add execution strategy to flow metadata
4. ✅ Default voice flows to sequential mode

#### Phase 2: Edge Type System (NEXT)
1. ✅ Add `type: "exclusive"` to edge interface
2. ✅ Update DAG scheduler to detect exclusive groups
3. ✅ Prevent parallelization of exclusive branches
4. ✅ Auto-detect exclusive groups from labeled edges

#### Phase 3: Hybrid Execution (FUTURE)
1. ✅ Implement hybrid mode
2. ✅ Per-node routing strategy configuration
3. ✅ Intelligent parallelization (safe paths only)
4. ✅ Visual indicators in flow editor

#### Phase 4: Advanced Features (LONG-TERM)
1. Dynamic parallelization based on runtime analysis
2. Edge priority/ordering for deterministic selection
3. Conditional edge evaluation
4. Loop detection and handling

## Decision: Hybrid Mode as Default

**For Voice Agent Flows:**
```json
{
    "metadata": {
        "executionStrategy": "sequential"  // Simple declaration
    }
}
```

**For Data Processing Pipelines:**
```json
{
    "metadata": {
        "executionStrategy": "dag"
    }
}
```

**No Metadata (Backward Compatibility):**
- Detect flow type from node composition
- If has AgenticLLM/Elicitation/Transfer → sequential
- If pure toolExecutor/setVariable chains → DAG
- Default to sequential (safer)

## Migration Path

### Existing Flows
1. Analyze flow structure
2. Auto-detect execution strategy
3. Add metadata on first save
4. Gradual migration to explicit edge types

### New Flows
1. Flow template includes execution strategy
2. Editor suggests strategy based on node types
3. Visual warnings for mixed patterns

## Code Changes Required

### 1. Update Edge Type Definition
**File**: `/backend/src/types/agentFlow.ts`

```typescript
export interface FlowEdge {
    type?: "default" | "conditional" | "exclusive" | "parallel" | "error" | "timeout";
    data?: EdgeData & {
        exclusive?: boolean;  // Part of exclusive routing group
    };
}
```

### 2. Update Flow Metadata
**File**: `/backend/src/types/agentFlow.ts`

```typescript
export interface FlowMetadata {
    executionStrategy?: "sequential" | "dag" | "hybrid" | FlowExecutionStrategy;
}
```

### 3. Fix AgenticLLM Routing
**File**: `/backend/src/core/flow-executor/executors/AgenticLLMNodeExecutor.ts`

Ensure `routeByAction()` properly sets and returns `nextNodeId` in result.

### 4. Fix FlowExecutor Auto-Transition
**File**: `/backend/src/core/flow-executor/FlowExecutor.ts`

```typescript
// Line 485-500: executeSequential()
if (this.context.currentNodeId === currentNode.id) {
    const edges = this.edgeMap.get(currentNode.id) || [];
    
    if (edges.length === 0) {
        // No edges, flow ends
        this.state.status = "completed";
        this.flowStateManager.markEnded();
        break;
    }
    
    // REMOVED: const nextEdge = edges[0];
    // Now: Only transition if node didn't explicitly route
    // (If result.nextNodeId was set, it already changed currentNodeId)
}
```

### 5. Add Strategy Selection
**File**: `/backend/src/core/flow-executor/FlowExecutor.ts`

```typescript
private async executeLoop(): Promise<void> {
    const strategy = this.selectExecutionStrategy();
    
    if (strategy === "sequential") {
        await this.executeSequential();
    } else if (strategy === "dag") {
        await this.executePlanBased();
    } else {
        await this.executeHybrid();
    }
}

private selectExecutionStrategy(): "sequential" | "dag" | "hybrid" {
    // 1. Check flow metadata
    if (this.flow.metadata?.executionStrategy) {
        return this.flow.metadata.executionStrategy;
    }
    
    // 2. Auto-detect from node types
    const hasRoutingNodes = this.flow.nodes.some(n => 
        ["agenticLLM", "elicitation", "wait"].includes(n.type)
    );
    
    // 3. Default to sequential for safety
    return hasRoutingNodes ? "sequential" : "dag";
}
```

### 6. Update DAG Scheduler for Exclusive Edges
**File**: `/backend/src/core/flow-executor/scheduling/DAGScheduler.ts`

```typescript
// Detect exclusive edge groups
const exclusiveGroups = this.detectExclusiveEdgeGroups(edges);

// Don't parallelize exclusive branches
for (const group of exclusiveGroups) {
    // Treat entire group as single execution point
    // Wait for runtime routing decision
}
```

## Testing Strategy

### Unit Tests
1. ✅ Sequential mode with explicit routing
2. ✅ Sequential mode with fallback edges
3. ✅ DAG mode with exclusive edges
4. ✅ Hybrid mode transitions
5. ✅ Strategy auto-detection

### Integration Tests
1. ✅ Reit flow with AgenticLLM routing
2. ✅ Parallel data processing flow
3. ✅ Mixed flow with both patterns
4. ✅ Error handling and timeout edges

### Regression Tests
1. ✅ Existing flows without metadata
2. ✅ Backward compatibility
3. ✅ Migration scenarios

## Success Metrics

✅ **Correctness**: Voice flows execute ONE path, not all  
✅ **Performance**: DAG flows still parallelize where safe  
✅ **Clarity**: Execution behavior is explicit and predictable  
✅ **Extensibility**: Easy to add new routing strategies  
✅ **Migration**: Zero breaking changes to existing flows  

## Timeline

- **Phase 1** (Critical): 1-2 days - Fix routing bugs, add sequential mode
- **Phase 2** (Important): 3-5 days - Edge type system, exclusive groups
- **Phase 3** (Enhancement): 1-2 weeks - Hybrid mode, auto-detection
- **Phase 4** (Future): Ongoing - Advanced features

## Conclusion

This design provides:
1. **Immediate fix** for broken voice flows
2. **Clear semantics** via edge types
3. **Best of both worlds** - sequential + parallel
4. **Future-proof** - extensible, maintainable
5. **Industry-aligned** - follows AWS/Temporal patterns

The hybrid approach with explicit edge types is the most future-proof solution that balances power, correctness, and usability.
