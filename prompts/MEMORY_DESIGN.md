# Memory-Aware Flow Design

The system supports automatic memory retrieval and skip for returning users.

## Flow Configuration

Enable memory at flow level:

```json
"configuration": {
  "memory": {
    "persist": true,
    "autoRetrieve": true,
    "skipKnownQuestions": true,
    "autoStoreElicitation": true,
    "defaultEntityType": "customer"
  }
}
```

## Elicitation Node Memory Fields

```json
{
	"autoStoreMemory": true,
	"autoRetrieveMemory": true,
	"memoryEntityType": "vehicle",
	"memoryAttributeName": "kennzeichen"
}
```

## Memory Skip Routing

Add `from_memory` edges to handle when data comes from memory:

```json
{
	"id": "e-node-skip",
	"source": "elicit_name",
	"target": "next_step",
	"sourceHandle": "from_memory"
}
```

When memory has the answer, the elicitation node routes via `from_memory` port instead of asking the question.

## Within-Session Variable Routing

The memory system distinguishes between:

- **Semantic Memory**: Persistent across sessions (what elicitation `from_memory` checks)
- **Working Memory**: Session variables (extracted values during conversation)

### The Problem

Elicitation nodes only skip via `from_memory` when data exists in **semantic** (persistent) memory. They don't check working memory variables extracted during the current conversation.

### Solution: Condition Nodes for Variable Gates

Add condition nodes before elicitations to check if working variables already exist:

```json
{
	"id": "check_has_schadensart",
	"type": "condition",
	"data": {
		"expression": "schadensart !== undefined && schadensart !== null && schadensart !== ''"
	}
}
```

Routing:

- `true` → Skip to next step
- `false` → Run elicitation

### Multi-Branch Conditions

For routing based on variable VALUES (not just existence), use `branches`:

```json
{
	"type": "condition",
	"data": {
		"expression": "schuldfrage !== undefined && schuldfrage !== ''",
		"branches": [
			{
				"label": "selbst_schuld",
				"condition": "schuldfrage === 'selbst_schuld'"
			},
			{
				"label": "andere_schuld",
				"condition": "schuldfrage === 'andere_schuld'"
			}
		]
	}
}
```

The `expression` determines if any branch applies. If true, the first matching `branches[].condition` determines the output port.
