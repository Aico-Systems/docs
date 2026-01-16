<file_path>
AICO/docs/prompts/FLOW_DESIGN_PATTERNS.md
</file_path>

<edit_description>
Create FLOW_DESIGN_PATTERNS.md with breakout, fillers, error handling
</edit_description>

# Flow Design Patterns

## Intelligent Breakout Handling

Use AgenticLLM nodes for smart entry points that extract information from natural language.

### Smart Entry Pattern

Replace rigid elicitation chains with an AgenticLLM node that:

1. Extracts all mentioned information into `memoryExtractionFields`
2. Routes to the appropriate intent via edge labels as actions
3. Loops back on `respond` if clarification needed

```json
{
	"type": "agenticLLM",
	"data": {
		"memoryExtractionFields": [
			"schadensart",
			"kennzeichen",
			"fahrzeug_hersteller"
		],
		"systemInstructions": "Extract all mentioned info. Route to intent."
	}
}
```

### Dynamic Intent Routing

AgenticLLM nodes use edge `sourceHandle` values as valid actions:

- Edge with `sourceHandle: "schadensmeldung"` → LLM can choose action `schadensmeldung`
- Edge with `sourceHandle: "respond"` → Loop back for clarification

The validator may warn about "invalid ports" - this is expected for dynamic routing.

## Filler Messages for Latency

Tool calls cause silent pauses. Add wait nodes with filler messages before slow operations.

### Filler Wait Pattern

```json
{
	"id": "wait_search",
	"type": "wait",
	"data": {
		"message": "Einen Moment, ich schaue in unserem System nach.",
		"timeout": 100,
		"eventType": "timeout",
		"speakMessage": true
	}
}
```

### Filler Message Variations

Vary filler messages to sound natural:

- "Einen Moment bitte, ich schaue nach."
- "Ich prüfe das kurz für Sie."
- "Einen kleinen Moment, ich suche die Daten."
- "Ich schaue gerade in unserem System."

### Note on Parallel Execution

True parallel execution (filler during tool) is NOT currently supported for routing nodes. The wait node completes before the tool node starts, but the message still plays to reduce perceived latency.

## Error Handling

Always provide graceful degradation for tool errors.

### Error Handler Node

Create a shared error handler AgenticLLM node:

```json
{
	"id": "handle_tool_error",
	"type": "agenticLLM",
	"data": {
		"prompt": "Ein technischer Fehler ist aufgetreten. Entschuldige dich und leite weiter.",
		"maxTokens": 100
	}
}
```

### Route Tool Errors

Connect all tool `error` ports to the error handler, then to transfer:

```
tool_node --[error]--> handle_tool_error --[respond]--> transfer_to_employee
```

This gives users context before the transfer instead of silent failures.
