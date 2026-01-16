## 14. Proposed New Node Types for Better DX

Based on patterns discovered during optimization, these new node types would significantly improve flow-builder experience:

### 14.1 `smartElicitation` - Combined Check + Elicit + Memory

**Problem**: Currently need 3 nodes (condition → elicitation → next) to handle "skip if variable exists" pattern.

**Proposal**: Single node that:

1. Checks working memory variable first
2. Checks semantic memory second
3. Only asks if both are empty
4. Auto-stores response in both memories

```json
{
	"type": "smartElicitation",
	"data": {
		"variableName": "schadensart",
		"prompt": "Was für ein Schaden ist entstanden?",
		"skipIfKnown": true,
		"checkWorkingMemory": true,
		"checkSemanticMemory": true
	}
}
```

**Output Ports**: `response`, `from_working`, `from_semantic`, `error`

### 14.2 `variableGate` - Simple Variable Existence Check

**Problem**: Condition nodes require writing JavaScript expressions for simple "does variable exist" checks.

**Proposal**: Simplified variable check node:

```json
{
	"type": "variableGate",
	"data": {
		"variables": ["kennzeichen", "fahrzeug_modell"],
		"mode": "all" // or "any"
	}
}
```

**Output Ports**: `pass` (all/any exist), `fail` (missing), plus individual variable ports

### 14.3 `fillerTool` - Tool Execution with Automatic Filler

**Problem**: Need wait node → tool node → edges for every tool that needs filler messages.

**Proposal**: Tool node with built-in filler:

```json
{
  "type": "fillerTool",
  "data": {
    "toolName": "reit_fahrzeug_suche",
    "fillerMessage": "Ich schaue kurz in unserem System nach.",
    "parameters": {...}
  }
}
```

Automatically speaks filler, executes tool, returns result.

### 14.4 `intentRouter` - LLM Classification with Preset Intents

**Problem**: AgenticLLM is powerful but overkill for simple "classify intent and route" use cases.

**Proposal**: Lightweight intent classifier:

```json
{
	"type": "intentRouter",
	"data": {
		"prompt": "Was möchten Sie tun?",
		"intents": {
			"schadensmeldung": ["Schaden", "Unfall", "Parkschaden", "melden"],
			"statusabfrage": ["Status", "wie weit", "fertig", "abfragen"],
			"terminvereinbarung": ["Termin", "abholen", "bringen"]
		},
		"fallback": "sonstiges"
	}
}
```

Uses keyword matching + lightweight LLM for classification. Output ports match intent keys.

### 14.5 `memoryLookup` - Fetch and Condition on Memory

**Problem**: No way to check semantic memory and branch without an elicitation.

**Proposal**: Memory lookup node:

```json
{
	"type": "memoryLookup",
	"data": {
		"entityType": "customer",
		"attributes": ["name", "kennzeichen", "letzte_reparatur"],
		"outputVariable": "customer_data"
	}
}
```

**Output Ports**: `found` (all attributes exist), `partial` (some exist), `not_found`

### 14.6 `conversationSummarizer` - Context Management

**Problem**: Long conversations exceed context limits; no automatic summarization.

**Proposal**: Node that summarizes conversation and compacts history:

```json
{
	"type": "conversationSummarizer",
	"data": {
		"triggerTokenCount": 3000,
		"summaryStyle": "key_facts",
		"preserveLastN": 3
	}
}
```

Runs automatically when context grows too large.
