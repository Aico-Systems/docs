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
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Sonstiges" --no-livekit

# Test "Nein" path - should transfer to mailbox and end
bun scripts/test-flow.ts reit-hauptflow --inputs "Nein" --no-livekit
```

### 2. Damage Report Flow - Self Fault

```bash
# Complete damage report with inspection scheduling
bun scripts/test-flow.ts reit-hauptflow --inputs \
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
bun scripts/test-flow.ts reit-hauptflow --inputs \
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
bun scripts/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Statusabfrage" \
  "WN-AE 2309 Escher" \
  "Nein danke" \
  --no-livekit --show-vars
```

### 5. Status Query with Delivery Service

```bash
# Test delivery scheduling path
bun scripts/test-flow.ts reit-hauptflow --inputs \
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
bun scripts/test-flow.ts reit-hauptflow --inputs \
  "Ja" \
  "Terminvereinbarung" \
  "WN-AE 2309" \
  "Montag den 27. Januar 2026" \
  --no-livekit --show-vars
```

### 7. Billing/Invoice Flow

```bash
# Transfer to accounting
bun scripts/test-flow.ts reit-hauptflow --inputs \
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
bun scripts/test-flow.ts reit-hauptflow --inputs "Nein" --no-livekit

echo -e "\n=== Test 2: Schadensmeldung (selbst schuld) ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Schadensmeldung" "Parkschaden" "VW Golf M-AB-123" "Selbst schuld" "Ja verkehrssicher" "Allianz" "Ja 12345" "München App" "2026-01-10 um 10 Uhr" --no-livekit

echo -e "\n=== Test 3: Schadensmeldung (andere schuld) ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Schadensmeldung" "Unfall" "BMW 3er B-AB-789" "Andere Partei schuld" --no-livekit

echo -e "\n=== Test 4: Statusabfrage ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Statusabfrage" "WN-AE 2309 Escher" "Nein" --no-livekit

echo -e "\n=== Test 5: Terminvereinbarung ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Terminvereinbarung" "WN-AE 2309" "2026-01-27" --no-livekit

echo -e "\n=== Test 6: Rechnung ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Rechnung" "WN-AE 2309" --no-livekit

echo -e "\n=== Test 7: Sonstiges ==="
bun scripts/test-flow.ts reit-hauptflow --inputs "Ja" "Sonstiges" --no-livekit

echo -e "\n=== All tests complete ==="
EOF

chmod +x /tmp/reit-test-suite.sh
/tmp/reit-test-suite.sh
```

## Tips

1. **Use `--show-vars`** to see variable state
2. **Check backend logs**: `make backend-logs-list`
3. **Use realistic dates**: "2026-01-20" not "tomorrow"
4. **Test error paths**: Invalid data to verify error handling
5. **Use real license plates**: Query PlanSO API first

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
