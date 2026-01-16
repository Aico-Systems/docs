# Variable Handling

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

## Variable Syntax and Interpolation

### Standard Syntax: `@variable`

The system uses **`@variable` syntax** for all variable references:

```json
{
  "type": "toolExecutor",
  "data": {
    "toolName": "get_status",
    "toolParams": {
      "auftrag_id": "@fahrzeug_suche.output.auftraege[0].id"
    },
    "systemInstructions": "Format status for customer:\n- Current: @auftrag_status.output.status\n- ETA: @auftrag_status.output.eta"
  }
}
```

### Variable Interpolation Features

**Backend interpolation supports:**

- Simple variables: "Hello @name"
- Nested paths: "City: @user.address.city"
- Array indexing: "First item: @items[0].name"
- Objects are auto-JSONified for LLM context: "Status: @auftrag_status.output" => "Status: {\n  \"status\": \"in_progress\",\n  \"eta\": \"2024-01-15\"\n}"
