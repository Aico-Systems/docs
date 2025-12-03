# Telephony Connection Fix Plan

## Executive Summary

**GOOD NEWS**: We can maintain full call control with LiveKit SIP - no need for Telnyx Call Control API!

LiveKit SIP provides:
- ✅ **Call Transfer** via `TransferSIPParticipant` API
- ✅ **End Calls** via `RemoveParticipant` API  
- ✅ **Call Monitoring** via webhooks + SIP participant attributes (`sip.callStatus`, etc.)
- ✅ **DTMF Support** for extension codes
- ✅ **Full call state tracking** via participant attributes

## Critical Issues Identified

Looking at the logs, we are handling telephony connections **COMPLETELY WRONG**. Here's what's broken:

### 1. **NOT Using LiveKit SIP at All**
- We're trying to manually dial SIP endpoints using Telnyx Call Control
- **WRONG:** Telnyx → Answer → Dial SIP → Bridge → LiveKit Room
- **CORRECT:** Telnyx → LiveKit SIP Trunk → Auto-create SIP Participant → Agent joins room

### 2. **Creating Duplicate Call Sessions**
```
call.initiated → create session (748552bb... for inbound)
call.initiated → create session (07140b7b... for outbound SIP dial)
```
We shouldn't be creating an outbound call at all! LiveKit SIP should handle the SIP participant.

### 3. **Manual Call Bridging**
```typescript
await callControlService.bridge(originalCallControlId, sipCallControlId)
```
This is unnecessary complexity. LiveKit automatically bridges SIP participants to rooms.

### 4. **No LiveKit Dispatch Rules**
We should configure LiveKit dispatch rules to automatically:
- Create SIP participants for incoming calls
- Route them to the correct room
- Add metadata for agent dispatch

### 5. **Room/Agent Management Confusion**
```typescript
await ensureRoomExists(config, roomName, metadata)
await waitForAgent(config, payload.to, 2000)
```
We're manually managing rooms when LiveKit should do this via dispatch rules.

## Call Control Capabilities with LiveKit SIP

### 1. Transfer Calls
Use `TransferSIPParticipant` API to transfer calls to another number or SIP endpoint:
```typescript
await sipClient.transferSipParticipant(
  participantIdentity,
  roomName,
  'tel:+15105550100' // or 'sip:user@domain.com'
);
```

### 2. End Calls
Use standard `RemoveParticipant` API to disconnect SIP participants:
```typescript
await roomClient.removeParticipant(roomName, participantIdentity);
// The call ends immediately when SIP participant is removed
```

### 3. Monitor Calls

**Via LiveKit Webhooks:**
- `participant_joined` - SIP participant enters room (call connected)
- `participant_left` - SIP participant leaves (call ended)
- `track_published` / `track_unpublished` - media state changes

**Via SIP Participant Attributes:**
```typescript
participant.attributes = {
  'sip.callID': 'unique-call-id',
  'sip.callStatus': 'active', // active, dialing, ringing, hangup, automation
  'sip.phoneNumber': '+15105550100',
  'sip.trunkID': 'trunk-id',
  'sip.trunkPhoneNumber': '+15105550200'
}
```

Query call status in real-time:
```typescript
const participant = await roomClient.getParticipant(roomName, identity);
const callStatus = participant.attributes['sip.callStatus'];
```

### 4. DTMF / Extension Codes
Send DTMF tones when creating outbound SIP participant:
```typescript
await sipClient.createSipParticipant({
  sipTrunkId: trunkId,
  sipCallTo: phoneNumber,
  roomName: roomName,
  dtmf: '*123#ww456', // w = 0.5s delay
  participantIdentity: 'caller'
});
```

## The Correct Architecture (Per LiveKit Docs)

```
┌─────────────┐
│   Telnyx    │
│  (PSTN/SIP) │
└──────┬──────┘
       │
       │ SIP INVITE
       ▼
┌─────────────────────┐
│   LiveKit SIP       │
│   - Trunk Config    │
│   - Dispatch Rules  │
└──────┬──────────────┘
       │
       │ Creates SIP Participant
       ▼
┌─────────────────────┐
│   LiveKit Room      │
│   - SIP Participant │
│   - Agent (auto)    │
└─────────────────────┘
```

### How It Should Work:

1. **Call comes in to Telnyx number**
2. **Telnyx routes to LiveKit SIP Trunk** (configured in Telnyx portal)
3. **LiveKit SIP receives INVITE**
4. **LiveKit Dispatch Rule matches** and creates:
   - New room (or joins existing based on rule type)
   - SIP Participant in that room
   - Optionally dispatches agent via room config
5. **Agent** detects new participant via room events and connects
6. **LiveKit handles all media** - no manual bridging needed

## What Needs to Change

### 1. Configure LiveKit SIP Trunk in Telnyx
Instead of using Call Control Applications, use SIP Trunking:
- Point Telnyx SIP trunk to LiveKit SIP domain
- LiveKit handles the SIP signaling

### 2. Create LiveKit Dispatch Rules
```typescript
// Create dispatch rule for each phone number/agent combination
const rule = await sipClient.createSipDispatchRule({
  type: 'individual', // Each call gets own room
  roomPrefix: 'call-',
}, {
  name: `Dispatch for ${phoneNumber}`,
  trunkIds: [trunkId],
  roomConfig: {
    agents: [{
      agentName: 'aico-livekit-agent',
      metadata: JSON.stringify({ agentId, organizationId })
    }]
  }
});
```

### 3. Remove All Manual Call Control
Delete:
- `callControlService.answer()`
- `callControlService.dial()`
- `callControlService.bridge()`
- Manual room creation
- waitForAgent polling

### 4. Update Agent to Use SIP Participant Events
Agent should:
```python
@ctx.on("participant_connected")
async def on_participant_connected(participant):
    if participant.kind == ParticipantKind.SIP:
        # This is our caller - start the conversation
        await session.start()
```

### 5. Track Calls via LiveKit Webhooks
Instead of Telnyx webhooks for call tracking, use LiveKit webhooks:
- `participant_joined` (SIP participant = call started)
- `participant_left` (SIP participant = call ended)
- Track via `sip.phoneNumber`, `sip.callID` attributes

## Implementation Steps

1. **Set up LiveKit SIP Service** (if self-hosting)
2. **Configure Telnyx SIP Trunk** to point to LiveKit
3. **Create LiveKit Dispatch Rules** for phone numbers
4. **Update Agent Code** to handle SIP participants
5. **Refactor Webhook Handling** to use LiveKit webhooks
6. **Remove Telnyx Call Control** logic entirely
7. **Update Database Schema** to track LiveKit rooms/sessions instead of Telnyx calls

## Benefits

- ✅ **Simpler code** - Let LiveKit handle SIP
- ✅ **More reliable** - No manual bridging race conditions
- ✅ **Better media quality** - Direct SIP to WebRTC in LiveKit
- ✅ **Easier debugging** - Standard LiveKit SIP flow
- ✅ **Scalable** - LiveKit handles all media infrastructure

## Migration Path

Since this is a major architectural change:

### Phase 1: Add LiveKit SIP Services (✅ DONE)
1. ✅ Created `livekitSipService.ts` - Manages trunks, dispatch rules, SIP participants
2. ✅ Created `sipControlRoutes.ts` - REST API for call control
3. ✅ Full call control capabilities:
   - Transfer: `POST /api/sip/transfer`
   - End call: `POST /api/sip/end-call`
   - Monitor: `GET /api/sip/call-status/:roomName/:participantIdentity`
   - Outbound: `POST /api/sip/outbound-call`

### Phase 2: Configure Telnyx SIP Trunk
1. In Telnyx Portal:
   - Switch from "Call Control Application" to "SIP Connection"
   - Configure SIP URI to point to LiveKit SIP domain
   - Set authentication if required
2. In our backend:
   - Call `livekitSipService.ensureInboundTrunk()` for each phone number
   - Call `livekitSipService.ensureDispatchRule()` to route to agents

### Phase 3: Update Agent Code
Modify `agent-worker/agent.py` to handle SIP participants:
```python
@ctx.on("participant_connected")
async def on_participant_connected(participant: rtc.Participant):
    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        # This is our SIP caller
        phone_number = participant.attributes.get('sip.phoneNumber')
        logger.info(f"SIP call from {phone_number}")
        
        # Start agent session
        await session.start()
```

### Phase 4: Switch to LiveKit Webhooks
Replace Telnyx webhook handler with LiveKit webhook handler:
```typescript
// Handle participant_joined for call start
webhook.on('participant_joined', async (event) => {
  const { participant, room } = event;
  
  if (participant.kind === 'SIP') {
    // Track call session in database
    await callSessionService.create({
      roomName: room.name,
      participantIdentity: participant.identity,
      phoneNumber: participant.attributes['sip.phoneNumber'],
      status: 'active'
    });
  }
});

// Handle participant_left for call end
webhook.on('participant_left', async (event) => {
  const { participant, room } = event;
  
  if (participant.kind === 'SIP') {
    // Update call session
    await callSessionService.updateStatus(
      participant.identity,
      'ended'
    );
  }
});
```

### Phase 5: Remove Old Code
Delete/deprecate:
- `telnyxWebhookService.ts` - Manual call control logic
- `callControlService.ts` - Answer/dial/bridge functions
- Manual room creation and agent polling
- Telnyx webhook routes (keep only for compatibility)

### Phase 6: Update Database Schema
Track LiveKit sessions instead of Telnyx calls:
```sql
ALTER TABLE call_sessions 
ADD COLUMN room_name TEXT,
ADD COLUMN participant_identity TEXT,
ADD COLUMN sip_call_id TEXT; -- From sip.callID attribute
```

## Call Control Examples

### Transfer a Call
```typescript
// Transfer to another agent's room
await livekitSipService.transferCall(
  sipParticipantIdentity,
  currentRoomName,
  'tel:+15105550200' // Transfer to this number
);

// Or transfer to another SIP endpoint
await livekitSipService.transferCall(
  sipParticipantIdentity,
  currentRoomName,
  'sip:support@example.com'
);
```

### End a Call
```typescript
await livekitSipService.endCall(roomName, sipParticipantIdentity);
```

### Monitor Call Status
```typescript
// Real-time status check
const status = await livekitSipService.getCallStatus(
  roomName,
  sipParticipantIdentity
);
// Returns: 'active', 'dialing', 'ringing', 'hangup', or 'automation'

// Get all call attributes
const attrs = await livekitSipService.getCallAttributes(
  roomName,
  sipParticipantIdentity
);
/* Returns:
{
  'sip.callID': '...',
  'sip.callStatus': 'active',
  'sip.phoneNumber': '+15105550100',
  'sip.trunkID': '...',
  'sip.trunkPhoneNumber': '...'
}
*/
```

### Make Outbound Call with DTMF
```typescript
const participant = await livekitSipService.createOutboundCall(
  outboundTrunkId,
  '+15105550100',
  'call-room-123',
  {
    dtmf: '*123#ww456', // Press *123#, wait 1s, press 456
    playDialtone: true,
    waitUntilAnswered: true
  }
);
```

## Testing the Migration

1. **Test with one phone number first**
2. **Verify call flow**:
   - Inbound call → LiveKit SIP → Dispatch rule → Room created → Agent joins
3. **Test call control**:
   - Transfer call to different number
   - End call programmatically
   - Monitor call status via API
4. **Monitor LiveKit webhooks** for proper event tracking
5. **Rollout to all phone numbers** once verified
2. Test thoroughly with one phone number
3. Gradually migrate phone numbers from old to new system
4. Deprecate old call control code

## References

- [LiveKit SIP Overview](https://docs.livekit.io/sip/)
- [LiveKit Dispatch Rules](https://docs.livekit.io/sip/dispatch-rule/)
- [LiveKit SIP Participant](https://docs.livekit.io/sip/sip-participant/)
- [Accepting Inbound Calls](https://docs.livekit.io/sip/accepting-calls/)
