# LiveKit SIP Call Control Implementation

## Overview

We have successfully implemented **full call control** using LiveKit SIP, eliminating the need for Telnyx Call Control API. This provides a cleaner, more reliable architecture while maintaining complete control over calls.

## What We Built

### 1. LiveKit SIP Service (`livekitSipService.ts`)

A comprehensive service that manages:

- **SIP Trunks**: Create/manage inbound trunks for phone numbers
- **Dispatch Rules**: Route incoming calls to agents automatically
- **SIP Participants**: Create outbound calls, manage call state
- **Call Control**: Transfer, end, and monitor calls in real-time

### 2. SIP Control API (`sipControlRoutes.ts`)

REST API endpoints for call control operations:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sip/transfer` | POST | Transfer call to another number |
| `/api/sip/end-call` | POST | End call by removing participant |
| `/api/sip/call-status/:roomName/:identity` | GET | Get real-time call status |
| `/api/sip/call-attributes/:roomName/:identity` | GET | Get all SIP attributes |
| `/api/sip/outbound-call` | POST | Make outbound call with DTMF |
| `/api/sip/participants/:roomName` | GET | List all participants in room |
| `/api/sip/trunk` | POST | Create/update inbound trunk |
| `/api/sip/dispatch-rule` | POST | Create/update dispatch rule |
| `/api/sip/trunk/:trunkId` | DELETE | Delete trunk |
| `/api/sip/dispatch-rule/:ruleId` | DELETE | Delete dispatch rule |

## Call Control Capabilities

### ✅ Transfer Calls

Transfer SIP participants to any phone number or SIP endpoint:

```typescript
// Transfer to phone number
await livekitSipService.transferCall(
  'sip-participant-identity',
  'room-name',
  'tel:+15105550200'
);

// Transfer to SIP URI
await livekitSipService.transferCall(
  'sip-participant-identity',
  'room-name',
  'sip:support@company.com'
);
```

### ✅ End Calls

Disconnect SIP participants (ends the call):

```typescript
await livekitSipService.endCall('room-name', 'sip-participant-identity');
```

### ✅ Monitor Calls

Get real-time call status and attributes:

```typescript
// Get call status
const status = await livekitSipService.getCallStatus(
  'room-name',
  'sip-participant-identity'
);
// Returns: 'active', 'dialing', 'ringing', 'hangup', 'automation'

// Get all SIP attributes
const attrs = await livekitSipService.getCallAttributes(
  'room-name',
  'sip-participant-identity'
);
/*
{
  'sip.callID': 'unique-call-id',
  'sip.callStatus': 'active',
  'sip.phoneNumber': '+15105550100',
  'sip.trunkID': 'trunk-abc123',
  'sip.trunkPhoneNumber': '+15105550200'
}
*/
```

### ✅ DTMF / Extension Codes

Send DTMF tones when making outbound calls:

```typescript
await livekitSipService.createOutboundCall(
  'outbound-trunk-id',
  '+15105550100',
  'room-name',
  {
    dtmf: '*123#ww456', // * # and digits, w = 0.5s delay
    playDialtone: true,
    waitUntilAnswered: true
  }
);
```

## Architecture Comparison

### ❌ Old Architecture (Broken)

```
Inbound Call
  ↓
Telnyx Call Control API
  ↓
Answer Call (manual)
  ↓
Create Room + Poll for Agent
  ↓
Dial SIP URI (manual)
  ↓
Bridge Calls (manual, fragile)
  ↓
LiveKit Room
```

Problems:
- Manual bridging with race conditions
- Duplicate call sessions
- Complex clientState passing
- No proper SIP abstraction
- Polling for agent readiness

### ✅ New Architecture (Correct)

```
Inbound Call
  ↓
Telnyx SIP Trunk
  ↓
LiveKit SIP Service
  ↓
Dispatch Rule (automatic)
  ↓
Creates SIP Participant in Room
  ↓
Agent Joins via participant_joined Event
```

Benefits:
- LiveKit handles all SIP signaling
- No manual bridging
- Single call session
- Standard LiveKit events
- Automatic agent dispatch

## Webhook Events

LiveKit provides these events for call tracking:

```typescript
// Call started
{
  event: 'participant_joined',
  room: { name: 'call-...', ... },
  participant: {
    identity: 'sip-caller',
    kind: 'SIP',
    attributes: {
      'sip.phoneNumber': '+15105550100',
      'sip.callStatus': 'active',
      'sip.trunkID': '...'
    }
  }
}

// Call ended
{
  event: 'participant_left',
  room: { name: 'call-...', ... },
  participant: { identity: 'sip-caller', kind: 'SIP' }
}
```

## Migration Steps

### Phase 1: Setup (✅ DONE)
- ✅ Created `livekitSipService.ts`
- ✅ Created `sipControlRoutes.ts`
- ✅ Full call control API ready

### Phase 2: Configure Telnyx
1. Switch from "Call Control Application" to "SIP Connection" in Telnyx portal
2. Point SIP connection to LiveKit SIP domain
3. Configure authentication if needed

### Phase 3: Create Trunks & Dispatch Rules

For each phone number:

```typescript
// Create inbound trunk
const trunk = await livekitSipService.ensureInboundTrunk(
  '+15105550100',
  'My Phone Number Trunk'
);

// Create dispatch rule to route to agent
const rule = await livekitSipService.ensureDispatchRule(
  '+15105550100',
  'agent-id',
  'organization-id',
  [trunk.sipTrunkId]
);
```

### Phase 4: Update Agent Code

Modify `agent-worker/agent.py`:

```python
from livekit import rtc

@ctx.on("participant_connected")
async def on_participant_connected(participant: rtc.Participant):
    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        # This is our SIP caller
        phone_number = participant.attributes.get('sip.phoneNumber')
        logger.info(f"SIP call from {phone_number}")
        
        # Start agent session
        await session.start()
```

### Phase 5: Switch to LiveKit Webhooks

Replace Telnyx webhook handler:

```typescript
// Track call sessions via LiveKit events
webhook.on('participant_joined', async (event) => {
  if (event.participant.kind === 'SIP') {
    await callSessionService.create({
      roomName: event.room.name,
      participantIdentity: event.participant.identity,
      phoneNumber: event.participant.attributes['sip.phoneNumber'],
      status: 'active'
    });
  }
});

webhook.on('participant_left', async (event) => {
  if (event.participant.kind === 'SIP') {
    await callSessionService.end(event.participant.identity);
  }
});
```

### Phase 6: Remove Old Code

Delete/deprecate:
- `telnyxWebhookService.ts` (manual call control logic)
- `callControlService.answer/dial/bridge` functions
- Manual room creation
- `waitForAgent()` polling

## Testing

### 1. Test Call Flow
```bash
# Make a test call to your Telnyx number
# Verify in logs:
# - LiveKit SIP receives INVITE
# - Dispatch rule creates room
# - SIP participant joins
# - Agent connects
```

### 2. Test Call Transfer
```bash
curl -X POST http://localhost:3000/api/sip/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "roomName": "call-12345",
    "participantIdentity": "sip-caller",
    "transferTo": "tel:+15105550200"
  }'
```

### 3. Test End Call
```bash
curl -X POST http://localhost:3000/api/sip/end-call \
  -H "Content-Type: application/json" \
  -d '{
    "roomName": "call-12345",
    "participantIdentity": "sip-caller"
  }'
```

### 4. Monitor Call Status
```bash
curl http://localhost:3000/api/sip/call-status/call-12345/sip-caller
```

## Next Steps

1. **Add routes to router**: Import `sipControlRoutes` in `router.ts`
2. **Configure Telnyx**: Switch to SIP trunking
3. **Setup trunks**: Call `ensureInboundTrunk()` for each phone number
4. **Setup dispatch rules**: Call `ensureDispatchRule()` for routing
5. **Update agent**: Handle SIP participants via events
6. **Switch webhooks**: Use LiveKit webhooks instead of Telnyx
7. **Remove old code**: Clean up manual call control logic

## Benefits Summary

✅ **Full call control maintained**
- Transfer calls to any number
- End calls programmatically
- Monitor call status in real-time
- Send DTMF tones

✅ **Simpler, more reliable**
- No manual bridging
- No race conditions
- Standard LiveKit patterns
- Automatic agent dispatch

✅ **Better performance**
- Direct SIP to WebRTC
- No extra hop through Telnyx Call Control
- Lower latency

✅ **Easier to debug**
- Standard LiveKit logs
- SIP participant attributes
- LiveKit webhooks
- Room-based tracking

## Questions?

See:
- `docs/TELEPHONY_FIX_PLAN.md` - Complete fix plan
- `backend/src/services/livekitSipService.ts` - Service implementation
- `backend/src/routes/sipControlRoutes.ts` - API endpoints
- LiveKit SIP docs: https://docs.livekit.io/sip/
