# AICO Flow Executor Architecture - Deep Analysis & Refactoring Proposal

## Executive Summary

After thorough analysis, the AICO flow executor system has **significant architectural issues** that lead to:
1. **Overcomplicated flows** (50+ nodes when 15 would suffice)
2. **Poor DX** for flow builders
3. **Inconsistent behavior** between executors
4. **Difficult debugging** due to scattered logic

This document proposes a **cleaner, more powerful architecture** that will enable simpler flows.

---

## Current Architecture Problems

### 1. Scattered Slot-Filling Logic

**Problem**: Slot-filling doesn't accumulate across turns properly.

**Current behavior** (ElicitationNodeExecutor.ts):
```
Turn 1: User says "Nikita" → LLM extracts {name: "Nikita", kennzeichen: missing}
Turn 2: User says "EICP234" → LLM extracts {kennzeichen: "EICP234", name: missing}
        ❌ Previous "name" is LOST because each turn is independent!
```

**Root cause**: Line 620-640 in ElicitationNodeExecutor - the slot-filling LLM call only sees the CURRENT message, not accumulated slot values.

**Fix needed**: Inject previous partial slots into the LLM prompt:
```typescript
// Before LLM call:
const existingSlots = getVariable(context, node.data.outputVariable) || {};
systemPrompt += `\nAlready collected: ${JSON.stringify(existingSlots)}`;
```

### 2. AgenticLLM Does Too Much

**Problem**: The `smart_entry` AgenticLLM node tries to:
- Greet the user
- Extract intent
- Extract 8+ memory fields
- Route to 5+ different paths
- Handle context switches
- Ask clarifying questions

**This is impossible to configure correctly.** The LLM gets confused.

**Current flow requires**:
```
smart_entry (agenticLLM) 
  → check_schaden_complete (condition)
  → check_basis_complete (condition)
  → elicit_damage_info (elicitation)
  → elicit_schuldfrage (elicitation)
  → elicit_schaden_details (elicitation)
  → ...
```

**Better approach**: One node per concern:
```
intent_router (simple intent classification)
  → status_flow (sub-flow)
  → damage_flow (sub-flow)
  → appointment_flow (sub-flow)
```

### 3. Memory Auto-Retrieve/Store is Unreliable

**Problem**: Memory operations happen in 3 different places with 3 different patterns:

| Executor | Retrieve Method | Store Method | Config Location |
|----------|----------------|--------------|-----------------|
| ElicitationNode | `memoryPool.semantic.queryEntities()` | `memoryPool.semantic.upsertEntity()` | Node + Flow config |
| AgenticLLMNode | `memoryPool.retrieve()` | `memoryPool.semantic.storeExtractedInfo()` | Only flow config |
| MemoryNode | `memoryPool.semantic.*` | `memoryPool.semantic.*` | Node config only |

**Result**: Flow builders can't predict when memory will be used.

### 4. Condition Nodes Check Wrong Variables

**Problem**: Condition expressions like `schadensart && kennzeichen` check for variables that:
- May not exist (AgenticLLM extracts to `memoryUpdates`, not direct variables)
- May be nested (ElicitationNode stores to `outputVariable.slotName`)
- Have different formats depending on which node set them

**Example**:
```javascript
// Condition checks:
schadensart && kennzeichen

// But actual variables are:
schaden_basis.schadensart  // From elicit_damage_info
kennzeichen                 // From smart_entry memoryExtraction (maybe?)
```

### 5. Port-Based Routing is Undocumented

**Problem**: Different nodes have different port schemes:

| Node Type | Ports | Routing Logic |
|-----------|-------|---------------|
| elicitation (intent) | `ja`, `nein`, custom intents | Edge label = intent name |
| elicitation (slot) | `response`, `from_memory` | Fixed ports |
| agenticLLM | `respond`, `schadensmeldung`, etc. | Edge label = action name |
| condition | `true`, `false`, `error` | Expression result |
| toolExecutor | `success`, `error` | Tool result |

Flow builders don't know which ports to connect!

---

## Proposed Architecture Changes

### Phase 1: Fix Slot-Filling Accumulation (Quick Win)

**File**: `ElicitationNodeExecutor.ts`

**Change**: Inject existing slots into LLM context before extraction.

```typescript
// Line ~595, inside validateWithLLM()
if (validationMode === "slot_filling") {
  // Get existing slot values from previous turns
  const existingSlots = getVariable(context, node.data.outputVariable) || {};
  
  systemPrompt = `Extract information from user input.
  
ALREADY COLLECTED (from previous turns):
${Object.entries(existingSlots)
  .filter(([_, v]) => v !== undefined && v !== null)
  .map(([k, v]) => `- ${k}: ${v}`)
  .join('\n') || '(none yet)'}

STILL NEEDED:
${slots.filter(s => !existingSlots[s.name]).map(s => `- ${s.name}: ${s.description}`).join('\n')}

Extract ONLY missing slots. Keep already collected values.`;
}
```

**Impact**: Slots will accumulate across turns without flow changes.

### Phase 2: Simplify AgenticLLM Purpose

**Problem**: `smart_entry` does greeting + intent + extraction + routing.

**Proposal**: Split into dedicated node types:

```
NEW: intentRouter (simplified)
- ONLY classifies intent
- NO memory extraction
- NO greeting logic
- Routes to intent-specific sub-flows

NEW: greeter (or use start node)  
- Handles greeting based on returning caller flag
- Single responsibility

KEEP: elicitation
- Does slot-filling with accumulation (fixed in Phase 1)
- Memory auto-store works per-field
```

**New flow structure**:
```
start → consent → greeter → intentRouter
                               ├→ status_subflow
                               ├→ damage_subflow  
                               ├→ appointment_subflow
                               └→ transfer
```

### Phase 3: Unified Memory Integration Service

**Create**: `MemoryIntegration.ts`

```typescript
class MemoryIntegration {
  // Single method for all memory operations
  async processNode(
    context: ExecutionContext,
    node: FlowNode,
    operation: 'before_execute' | 'after_execute',
    data?: any
  ): Promise<{
    shouldSkip: boolean;
    cachedValue?: any;
    storedSuccessfully?: boolean;
  }> {
    // Unified logic here
  }
  
  // Clear config precedence
  private getConfig(context: ExecutionContext, node: FlowNode) {
    // Node config > Flow config > Global config
    return {
      autoRetrieve: node.data.autoRetrieveMemory 
        ?? context.flowConfig?.memory?.autoRetrieve 
        ?? false,
      autoStore: node.data.autoStoreMemory
        ?? context.flowConfig?.memory?.autoStoreElicitation
        ?? false,
      // ...
    };
  }
}
```

**Impact**: All executors call one service, consistent behavior.

### Phase 4: Explicit Port Documentation

**Add to each node type's schema**:

```typescript
// In flow-schema package
const elicitationPorts = {
  slotFilling: {
    outputs: ['response', 'from_memory'],
    description: 'response = got user input, from_memory = value was cached'
  },
  intentClassification: {
    outputs: ['<dynamic: edge labels become ports>'],
    description: 'Create edges with sourceHandle matching expected intents'
  }
};
```

**Add visual helper in frontend**: Show available ports when connecting edges.

---

## Simplified Reit Flow Design

### Current: 35+ nodes

### Proposed: ~15 nodes

```
[start]
    ↓
[consent_check] (elicitation: intent_classification)
    ├─ ja → [greeter]
    ├─ from_memory → [greeter]  
    └─ nein → [transfer_mailbox] → [end_transfer]

[greeter] (setVariable or simple LLM)
    ↓
[intent_router] (elicitation: intent_classification)
    ├─ status → [collect_status_info] → [lookup_status] → [respond_status]
    ├─ schaden → [collect_damage_info] → [check_fault] → ...
    ├─ termin → [collect_termin_info] → [book_termin]
    ├─ rechnung → [collect_rechnung_info] → [transfer_buchhaltung]
    └─ sonstiges → [transfer_mitarbeiter]
```

### Key simplifications:

1. **No condition nodes for data checking** - Elicitation handles "all slots filled" automatically
2. **No AgenticLLM for routing** - Use simpler intent classification
3. **Memory auto-fills from previous interactions** - No manual from_memory edges needed
4. **Each path is self-contained** - No jumping between unrelated nodes

---

## Implementation Priority

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Fix slot accumulation | 2h | High - fixes 50% of test failures |
| 2 | Simplify smart_entry | 4h | High - clearer intent routing |
| 3 | Document port schemes | 2h | Medium - better DX |
| 4 | Create MemoryIntegration service | 8h | Medium - consistent behavior |
| 5 | Redesign flow structure | 4h | High - 50% fewer nodes |

---

## Next Steps

1. **Immediate**: Apply slot accumulation fix to ElicitationNodeExecutor
2. **Short-term**: Simplify the Reit flow to use the fixed executors
3. **Medium-term**: Refactor executor architecture per proposals above
4. **Long-term**: Create flow builder UI that understands port schemes
