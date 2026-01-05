# REIT Flow Testing Guide

## What is `--no-livekit`?

The `--no-livekit` flag **disables the LiveKit WebSocket connection** when testing flows.

### Without `--no-livekit` (default):

- Connects to LiveKit room via WebSocket
- Listens for real-time voice/audio events
- Receives `agent_message` events as they stream
- Shows AI responses in real-time
- Requires LiveKit credentials

### With `--no-livekit`:

- Skips LiveKit connection entirely
- Relies only on HTTP API responses
- Faster execution (no network overhead)
- No real-time event streaming
- Simpler debugging

### Why use it?

1. **Automated testing**: Predefined inputs don't need voice/audio
2. **Faster iteration**: No WebSocket connection overhead
3. **Simpler debugging**: Focus on flow logic, not LiveKit events
4. **CI/CD pipelines**: Easier to run in automated environments
5. **No credentials needed**: Works without LiveKit API keys

In production, you'd use LiveKit for real voice calls. For testing flow logic with predefined inputs, `--no-livekit` is perfect.

## Test Commands

### 1. Consent Flow Tests

```bash
# Test "Ja" path - should proceed to intent identification
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Sonstiges" --no-livekit

# Test "Nein" path - should transfer to mailbox and end
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Nein" --no-livekit
```

### 2. Damage Report Flow - Self Fault

```bash
# Complete damage report with inspection scheduling
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Schadensmeldung" \
  "Parkschaden" \
  "VW Golf M-AB-123" \
  "Ich bin selbst schuld" \
  "Ja das Fahrzeug ist verkehrssicher" \
  "Allianz" \
  "Ja Schadennummer 12345" \
  "München, gerne per App" \
  "2026-01-10 um 10 Uhr" \
  --no-livekit --show-vars
```

### 3. Damage Report Flow - Other Fault

```bash
# Should route to employee transfer
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Schadensmeldung" \
  "Unfall" \
  "BMW 3er B-AB-789" \
  "Der andere Fahrer ist schuld" \
  --no-livekit
```

### 4. Status Query Flow

```bash
# Test with existing vehicle (use real license plate from PlanSO)
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Statusabfrage" \
  "WN-AE 2309 Escher" \
  "Nein danke" \
  --no-livekit --show-vars
```

### 5. Status Query with Delivery Service

```bash
# Test delivery scheduling path
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Statusabfrage" \
  "WN-AE 2309 Escher" \
  "Nein" \
  "Lieferservice bitte" \
  "Morgen zwischen 10 und 13 Uhr, Musterstraße 1 München" \
  --no-livekit --show-vars
```

### 6. Repair Appointment Flow

```bash
# Must use Monday/Tuesday with 14 days advance
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Terminvereinbarung" \
  "WN-AE 2309" \
  "Montag den 27. Januar 2026" \
  --no-livekit --show-vars
```

### 7. Billing/Invoice Flow

```bash
# Transfer to accounting
bun scripts/flow/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Rechnung" \
  "Kennzeichen WN-AE 2309" \
  --no-livekit --show-vars
```

## Full Test Suite

Run all major paths in one script:

```bash
cat > /tmp/reit-test-suite.sh << 'EOF'
#!/bin/bash
cd /home/nikita/Projects/AICO

echo "=== Test 1: Consent Nein ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Nein" --no-livekit

echo -e "\n=== Test 2: Schadensmeldung (selbst schuld) ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Schadensmeldung" "Parkschaden" "VW Golf M-AB-123" "Selbst schuld" "Ja verkehrssicher" "Allianz" "Ja 12345" "München App" "2026-01-10 um 10 Uhr" --no-livekit

echo -e "\n=== Test 3: Schadensmeldung (andere schuld) ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Schadensmeldung" "Unfall" "BMW 3er B-AB-789" "Andere Partei schuld" --no-livekit

echo -e "\n=== Test 4: Statusabfrage ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Statusabfrage" "WN-AE 2309 Escher" "Nein" --no-livekit

echo -e "\n=== Test 5: Terminvereinbarung ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Terminvereinbarung" "WN-AE 2309" "2026-01-27" --no-livekit

echo -e "\n=== Test 6: Rechnung ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Rechnung" "WN-AE 2309" --no-livekit

echo -e "\n=== Test 7: Sonstiges ==="
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Sonstiges" --no-livekit

echo -e "\n=== All tests complete ==="
EOF

chmod +x /tmp/reit-test-suite.sh
/tmp/reit-test-suite.sh
```

## Flow Development Workflow

When modifying the REIT flow, follow this workflow to ensure changes are valid and deployed correctly:

### 1. Validate Flow Changes

Before deploying, validate your flow changes using the schema validator:

```bash
# Validate the flow JSON against the schema
cd backend/flow-schema
bun validate-cli.ts ../../src/seeds/data/flows/reit-hauptflow.json

# Check for common issues like missing nodes, invalid connections, etc.
```

### 2. Update Flow in Database

After validation, update the flow in the development database:

```bash
# Update the flow (works for all orgs when organizationId is "_default")
bun scripts/flow/update-flow.ts backend/src/seeds/data/flows/reit-hauptflow.json

# The script will:
# - Validate the flow structure
# - Update existing flows or create new ones
# - Invalidate flow caches automatically
```

### 3. Test Your Changes

Run the appropriate test commands to verify your changes work:

```bash
# Test specific scenarios
bun scripts/flow/test-flow.ts reit-hauptflow --inputs "Ja" "Statusabfrage" --no-livekit --show-vars

# Run the full test suite
/tmp/reit-test-suite.sh
```

### 4. Debug Issues

If tests fail:

- Check backend logs: `make backend-logs-list`
- Use `--show-vars` to inspect variable state
- Clear test memory if needed: `bun scripts/flow/manage-memory.ts clear test-user-default`

## Tips

1. **Use `--show-vars`** to see variable state
2. **Check backend logs**: `make backend-logs-list`
3. **Use realistic dates**: "2026-01-20" not "tomorrow"
4. **Test error paths**: Invalid data to verify error handling
5. **Use real license plates**: Query PlanSO API first
6. **Validate before updating**: Always run `validate-cli.ts` before `update-flow.ts`
7. **Clear memory between tests**: Use `manage-memory.ts` for consistent test results

## Memory Management for Testing

The REIT Hauptflow uses memory to store and retrieve customer information across conversations. During testing, you may need to inspect or clear memory to ensure consistent test results or to simulate new customers.

### Memory Components

The flow stores:

- **Episodic Memory**: Conversation history and previous interactions
- **Semantic Memory**: Customer entities (name, phone, vehicle info)
- **Preferences**: Customer preferences and consent status
- **Relationships**: Connections between entities (e.g., customer-vehicle relationships)

### Using the Memory Management Script

The `scripts/flow/manage-memory.ts` script helps manage memory for testing:

```bash
# List all phone numbers with memory
bun scripts/flow/manage-memory.ts list

# Inspect memory for a specific user (phone number or user ID)
bun scripts/flow/manage-memory.ts inspect +1234567890
bun scripts/flow/manage-memory.ts inspect test-user-default

# Clear all memory for a user
bun scripts/flow/manage-memory.ts clear +1234567890
bun scripts/flow/manage-memory.ts clear test-user-default

# Clear specific memory types
bun scripts/flow/manage-memory.ts clear +1234567890 chunks    # Only episodic memory
bun scripts/flow/manage-memory.ts clear +1234567890 entities  # Only semantic entities
```

### When to Use Memory Management

1. **Between Test Runs**: Clear memory to start fresh for each test scenario
2. **Debugging Memory Issues**: Inspect memory to see what information is stored
3. **Testing Memory Retrieval**: Ensure the flow correctly retrieves previous customer data
4. **Consent Testing**: Clear consent status to test consent flows

### Default Test User

The test commands use `test-user-default` as the default user ID. Clear this user's memory between major test suites:

```bash
bun scripts/flow/manage-memory.ts clear test-user-default
```

### Memory Identity

- **Phone Numbers**: Start with `+` or are numeric (e.g., `+491234567890`)
- **User IDs**: Any other identifier (e.g., `test-user-default`)
- Memory is scoped per organization ID (automatically fetched)

## Real Vehicle Data

Query actual vehicles from PlanSO:

```bash
# List all vehicles
curl "https://reit.connectors.aicoflow.com/api/orders?limit=10"

# Search by plate
curl "https://reit.connectors.aicoflow.com/api/orders?plate=WN-AE"

# Get specific order details
curl "https://reit.connectors.aicoflow.com/api/orders/20773"
```

Use these license plates in your tests to get real data instead of mocked responses.
