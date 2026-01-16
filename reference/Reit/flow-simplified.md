# Reit Hauptflow - Simplified Architecture (v4)

> **Status**: Validated and ready for testing
> **File**: `backend/src/seeds/data/flows/reit-hauptflow-v4.json`
> **Reduction**: 50+ nodes → 21 nodes | 80+ edges → 34 edges

## Problems with Current Flow

| Issue                                   | Current State                         | Impact                                         |
| --------------------------------------- | ------------------------------------- | ---------------------------------------------- |
| **Excessive Condition Nodes**           | 10+ nodes checking "is variable set?" | Redundant - elicitation auto-skips from memory |
| **Wait Nodes Before Tools**             | 8 wait nodes                          | Unnecessary latency and clutter                |
| **Sequential Single-Field Elicitation** | 7 separate nodes for damage report    | Could be 2-3 using slot_filling                |
| **Manual Routing Logic**                | Complex edge conditions               | AgenticLLM can route by intent directly        |
| **Node Count**                          | 50+ nodes, 80+ edges                  | Should be ~20 nodes, ~30 edges                 |

## Simplified Flow Design

```
                    ┌─────────────────┐
                    │     START       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  consent_check  │ elicitation (intent: ja/nein)
                    └────────┬────────┘
                        ja/  \nein
                          /    \
            ┌────────────▼┐    ┌▼─────────────┐
            │ smart_entry │    │ mailbox_xfer │
            │ (AgenticLLM)│    └──────────────┘
            └──────┬──────┘
                   │
     ┌─────────────┼─────────────┬─────────────┬──────────────┐
     │             │             │             │              │
┌────▼────┐  ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐  ┌─────▼─────┐
│ SCHADEN │  │  STATUS   │ │  TERMIN   │ │ RECHNUNG  │  │ SONSTIGES │
└────┬────┘  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  └─────┬─────┘
     │             │             │             │              │
     ▼             ▼             ▼             ▼              ▼
  (subflow)    (subflow)     (subflow)   (quick xfer)   (quick xfer)
```

## Branch Details

### 1. Schadensmeldung (Damage Report)

**BEFORE: 15 nodes**

```
check_schadensart → elicit_schadensart → check_fahrzeug → elicit_fahrzeug →
check_schuldfrage → elicit_schuldfrage → elicit_verkehrssicherheit →
wait → check_roadworthiness → elicit_versicherung → elicit_schadennummer →
elicit_standort → wait → create_report → schedule_inspection → wait → book → confirm
```

**AFTER: 6 nodes**

```
elicit_damage_info (slot_filling: schadensart, kennzeichen)
    ↓
elicit_schuldfrage (intent: selbst_schuld/andere_schuld)
    ↓ selbst_schuld                    ↓ andere_schuld
elicit_details (slot: beschreibung)    transfer_mitarbeiter
    ↓
elicit_versicherung_info (slots: versicherung, schadennummer, standort)
    ↓
create_report_book_termin (tool + formatter: creates report AND books inspection)
    ↓
end_success
```

**Key Simplifications:**

- Remove ALL `check_has_*` condition nodes → elicitation auto-skips
- Combine `schadensart` + `fahrzeug` into one slot_filling node
- Combine `versicherung` + `schadennummer` + `standort` into one slot_filling node
- Remove wait nodes → ToolExecutor has built-in formatter
- `schuldfrage` uses intent_classification with direct edge routing

### 2. Statusabfrage (Status Query)

**BEFORE: 12 nodes**

```
identify_vehicle → wait → search → check_found → wait → get_status →
format → check_parts → ask_transfer → ask_delivery → pickup/delivery → confirm
```

**AFTER: 4 nodes**

```
elicit_identifikation (slot_filling: kennzeichen, name) [auto-skip if known]
    ↓
lookup_and_status (tool: search + status, formatter builds response)
    ↓
handle_result (AgenticLLM: decides transfer/pickup/delivery based on result)
    ↓
end_or_transfer
```

### 3. Terminvereinbarung (Repair Appointment)

**BEFORE: 9 nodes**

```
get_kennzeichen → wait → lookup → check_found → request_date → wait → book → confirm
```

**AFTER: 3 nodes**

```
elicit_kennzeichen [auto-skip if known]
    ↓
lookup_and_book (tool: lookup + book, AgenticLLM handles date negotiation)
    ↓
end_success
```

### 4. Rechnung & Sonstiges

Already simple - just elicit info → transfer. Keep as-is but remove redundancy.

## Node Specifications

### smart_entry (AgenticLLM)

```json
{
	"type": "agenticLLM",
	"data": {
		"prompt": "Wie kann ich Ihnen helfen?",
		"systemInstructions": "Extract intent and any mentioned info. Route to appropriate branch.",
		"memoryExtractionFields": ["schadensart", "kennzeichen", "kunde_name"]
	}
}
```

**Edges:** schadensmeldung, statusabfrage, terminvereinbarung, rechnung, sonstiges, respond

### elicit_damage_info (Elicitation - Slot Filling)

```json
{
	"type": "elicitation",
	"data": {
		"prompt": "Was für ein Schaden ist es, und wie lautet Ihr Kennzeichen?",
		"validationMode": "slot_filling",
		"slots": [
			{ "name": "schadensart", "type": "string", "required": true },
			{ "name": "kennzeichen", "type": "string", "required": true }
		],
		"autoRetrieveMemory": true,
		"autoStoreMemory": true
	}
}
```

### elicit_schuldfrage (Elicitation - Intent Classification)

```json
{
	"type": "elicitation",
	"data": {
		"prompt": "Waren Sie selbst schuld am Schaden?",
		"validationMode": "intent_classification",
		"outputVariable": "schuldfrage"
	}
}
```

**Edges:** selbst_schuld → continue, andere_schuld → transfer

## Edge Count Comparison

| Branch             | Before | After  |
| ------------------ | ------ | ------ |
| Entry              | 5      | 3      |
| Schadensmeldung    | 25     | 8      |
| Statusabfrage      | 20     | 6      |
| Terminvereinbarung | 15     | 5      |
| Rechnung           | 4      | 3      |
| Sonstiges          | 3      | 2      |
| Error handling     | 8      | 3      |
| **TOTAL**          | **80** | **30** |

## Implementation Notes

1. **Memory Auto-Skip**: Set `autoRetrieveMemory: true` on all elicitations → no manual condition nodes
2. **Slot Filling**: Combine related fields into single elicitation
3. **Tool Formatters**: Use `formatter` config on ToolExecutor → no wait + LLM response nodes
4. **Intent Edges**: Connect elicitation directly to targets via intent-named edges
5. **AgenticLLM for Complex Logic**: Use for decisions that need context (parts availability, delivery vs pickup)

## Migration Path

1. Create new `reit-hauptflow-v4.json` with simplified architecture
2. Test each branch independently with `test-flow.ts`
3. Compare latency and UX with old flow
4. Replace old flow once validated

## Testing Commands

```bash
# Clear memory for clean test
bun scripts/flow/manage-memory.ts clear test-user-default

# Deploy the new flow
bun scripts/flow/update-flow.ts backend/src/seeds/data/flows/reit-hauptflow-v4.json

# Test with trace and variable visibility
bun scripts/flow/test-flow.ts reit-hauptflow-v4 --trace --show-vars --verbose
```

## Validation Results

```
File: reit-hauptflow-v4.json
Valid: true
Statistics:
  Total Nodes: 22
  Total Edges: 36
  Node Types: start(1), condition(2), elicitation(8), transfer(4), agenticLLM(3), toolExecutor(3), end(2)
  Errors: 0
  Warnings: 7 (all expected - dynamic port generation)
```

## Test Results (2026-01-16)

### Consent Fix

- **Issue**: Consent was being auto-skipped from memory, leaving user with no context
- **Fix**: Set `autoRetrieveMemory: false` on consent node - GDPR requires consent each call

### Working Memory Skip

- **Issue**: `smart_entry` extracts schadensart+kennzeichen to working memory, but `elicit_damage_info` still asked for them
- **Fix**: Added `check_basis_complete` condition node that skips elicitation when data exists

### Performance

| Path                           | Duration | User Inputs |
| ------------------------------ | -------- | ----------- |
| Fast (all info in one message) | 8.04s    | 2           |
| Step-by-step                   | 9.63s    | 5           |

## Key Architectural Decisions

### 1. AgenticLLM for Smart Entry

The `smart_entry` node uses `agenticLLM` with `memoryExtractionFields` to:

- Understand intent in natural language
- Extract mentioned info (schadensart, kennzeichen, name) in one pass
- Route via dynamic action edges (schadensmeldung, statusabfrage, etc.)

### 2. Slot-Filling for Multi-Field Collection

Instead of sequential single-field elicitations:

- `elicit_damage_info`: schadensart + kennzeichen
- `elicit_status_id`: kennzeichen + name
- `elicit_versicherung_komplett`: versicherung + schadennummer

### 3. Tool Formatters Replace Wait + LLM Nodes

Every `toolExecutor` has a `formatter` config that generates natural responses without separate wait or LLM nodes.

### 4. Intent Classification for Binary Decisions

- `consent_check`: ja/nein with direct edge routing
- `elicit_schuldfrage`: selbst_schuld/andere_schuld with direct edge routing

### 5. Memory Auto-Skip

All elicitation nodes have `autoRetrieveMemory: true` - no manual condition checks needed.
