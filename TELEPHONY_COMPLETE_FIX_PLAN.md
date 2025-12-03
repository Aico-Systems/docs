# LiveKit SIP Integration - Complete Fix Plan

## Critical Analysis

After reviewing the entire codebase, I found:

### Current Infrastructure

**Database Schema:**
- `call_sessions` - Tracks Telnyx call control sessions (call_control_id)
- `phone_numbers` - Phone number inventory (Telnyx external_id)
- `call_routes` - Routes phone numbers to agents
- `telephony_connections` - Tracks Telnyx SIP trunks and Call Control apps
- `call_events` - Logs all call events

**Current Services:**
- `sipService.ts` - **ALREADY EXISTS** - Manages LiveKit SIP trunks (correct API usage)
- `telnyxWebhookService.ts` - Processes Telnyx Call Control webhooks
- `callSessionService.ts` - Manages call sessions in database
- `callControlService.ts` - Makes Telnyx Call Control API calls (answer, dial, bridge)

**Key Finding:** We ALREADY have a working `sipService.ts` that uses LiveKit SIP correctly!

### The Problem

We have TWO conflicting approaches:

1. **`sipService.ts`** (✅ CORRECT) - Uses LiveKit SIP API properly
2. **`telnyxWebhookService.ts`** (❌ WRONG) - Manual Call Control with answer/dial/bridge

The webhook service is using the OLD Telnyx Call Control approach instead of the LiveKit SIP approach.

### Errors to Fix

1. **livekitSipService.ts** - NEW file I created has wrong API usage (duplicates existing sipService.ts)
2. **sipControlRoutes.ts** - Incomplete file with duplicate code
3. **Database schema** - Designed for Telnyx Call Control, needs LiveKit SIP fields

## Solution: Use Existing Infrastructure

### Phase 1: Fix Immediate Errors ✅

**Action:** Remove duplicate/broken files and use existing `sipService.ts`

1. Delete `backend/src/services/livekitSipService.ts` (duplicate)
2. Delete `backend/src/routes/sipControlRoutes.ts` (broken)
3. Delete `backend/src/routes/sipControlRoutes.integration.example.ts` (example only)

### Phase 2: Extend Existing SIP Service ✅

**File:** `backend/src/services/sipService.ts` (already exists with correct API)

Add these methods to existing service:

```typescript
// Call control methods
async transferCall(participantIdentity: string, roomName: string, transferTo: string) {
  return await this.sipClient.transferSipParticipant(
    participantIdentity,
    roomName,
    transferTo
  );
}

async endCall(roomName: string, participantIdentity: string) {
  // Use RoomServiceClient to remove participant
  const roomClient = new RoomServiceClient(
    this.appConfig.LIVEKIT_URL,
    this.appConfig.LIVEKIT_API_KEY,
    this.appConfig.LIVEKIT_API_SECRET
  );
  return await roomClient.removeParticipant(roomName, participantIdentity);
}

async getCallStatus(roomName: string, participantIdentity: string) {
  const roomClient = new RoomServiceClient(...);
  const participant = await roomClient.getParticipant(roomName, participantIdentity);
  return participant.attributes['sip.callStatus'];
}
```

### Phase 3: Update Database Schema

**Current:** Tracks Telnyx `call_control_id`
**Need:** Track LiveKit `room_name` and `participant_identity`

**Migration:**
```sql
-- Add LiveKit fields to call_sessions
ALTER TABLE call_sessions 
ADD COLUMN room_name TEXT,
ADD COLUMN participant_identity TEXT,
ADD COLUMN sip_call_id TEXT, -- From sip.callID attribute
ADD COLUMN livekit_session_id UUID;

-- Create indexes
CREATE INDEX idx_call_sessions_room ON call_sessions(room_name);
CREATE INDEX idx_call_sessions_participant ON call_sessions(participant_identity);
```

### Phase 4: Switch Webhook Handler

**Replace:** `telnyxWebhookService.ts` (Telnyx Call Control webhooks)
**With:** LiveKit webhook handler

**New file:** `backend/src/services/livekitWebhookService.ts`

```typescript
import { WebhookReceiver } from 'livekit-server-sdk';

class LiveKitWebhookService {
  private receiver: WebhookReceiver;

  async processWebhook(body: string, authHeader: string) {
    const event = await this.receiver.receive(body, authHeader);
    
    if (event.event === 'participant_joined' && event.participant.kind === 'SIP') {
      await this.handleSipCallStarted(event);
    }
    
    if (event.event === 'participant_left' && event.participant.kind === 'SIP') {
      await this.handleSipCallEnded(event);
    }
  }

  private async handleSipCallStarted(event: any) {
    const { participant, room } = event;
    
    // Create call session
    await callSessionService.create({
      organizationId: room.metadata.organizationId,
      roomName: room.name,
      participantIdentity: participant.identity,
      phoneNumber: participant.attributes['sip.phoneNumber'],
      sipCallId: participant.attributes['sip.callID'],
      direction: 'inbound',
      status: 'active'
    });
  }

  private async handleSipCallEnded(event: any) {
    const { participant } = event;
    
    await callSessionService.endByParticipant(
      participant.identity,
      'normal'
    );
  }
}
```

### Phase 5: Configure Telnyx to Use LiveKit SIP

**Current Setup:** Telnyx → Call Control Application → Our Webhooks
**Target Setup:** Telnyx → SIP Connection → LiveKit SIP

**Steps:**
1. In Telnyx portal: Create SIP Connection
2. Point to LiveKit SIP domain (from `sipService.getOrCreateTrunk()`)
3. Configure dispatch rules via `sipService.createDispatchRule()`
4. Remove Call Control Application

### Phase 6: Update Agent Code

**Current:** Agent polls for room via `waitForAgent()`
**Target:** Agent handles `participant_connected` event

**File:** `agent-worker/agent.py`

```python
@ctx.on("participant_connected")
async def on_participant_connected(participant: rtc.Participant):
    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        phone_number = participant.attributes.get('sip.phoneNumber')
        logger.info(f"SIP call from {phone_number}")
        
        # Start agent session
        await session.start()
```

## Implementation Order

### Immediate (Fix Errors) - 10 minutes

1. ✅ Delete broken/duplicate files:
   - `backend/src/services/livekitSipService.ts`
   - `backend/src/routes/sipControlRoutes.ts`
   - `backend/src/routes/sipControlRoutes.integration.example.ts`

2. ✅ Verify `backend/src/services/sipService.ts` compiles correctly

### Short Term (Add Call Control) - 1 hour

3. ✅ Extend `sipService.ts` with call control methods:
   - `transferCall()`
   - `endCall()`
   - `getCallStatus()`
   - `getCallAttributes()`

4. ✅ Create proper routes in existing `telnyxRoutes.ts` or new `sipRoutes.ts`

5. ✅ Add route handlers to `router.ts`

### Medium Term (Database Migration) - 2 hours

6. Create database migration script
7. Add LiveKit fields to `call_sessions` schema
8. Update `callSessionService.ts` to handle both models during transition

### Long Term (Full Migration) - 1 day

9. Create `livekitWebhookService.ts`
10. Update agent code to handle SIP participant events
11. Configure Telnyx SIP connection (manual portal step)
12. Create dispatch rules via API
13. Test with one phone number
14. Deprecate `telnyxWebhookService.ts`
15. Remove Telnyx Call Control code

## Benefits of This Approach

✅ **Uses existing working code** - `sipService.ts` already has correct LiveKit API usage
✅ **Minimal disruption** - Extend rather than rewrite
✅ **Database compatible** - Add fields, don't break existing
✅ **Gradual migration** - Can test one number at a time
✅ **Full call control maintained** - Transfer, end, monitor via LiveKit

## API Comparison

### Correct LiveKit SDK Usage (from existing sipService.ts)

```typescript
// Create trunk (3 params)
await sipClient.createSipInboundTrunk(
  trunkName,      // string
  [phoneNumber],  // string[]
  options         // object (optional)
);

// Transfer (3 params)
await sipClient.transferSipParticipant(
  participantIdentity,  // string
  roomName,             // string
  transferTo            // string
);

// No request objects needed - just direct parameters!
```

### Wrong Usage (what I created in livekitSipService.ts)

```typescript
// ❌ Wrong - trying to pass request objects
await sipClient.createSipInboundTrunk({
  name: trunkName,
  numbers: [phoneNumber],
  // ...
} as CreateSIPInboundTrunkRequest);
```

## Next Steps

1. **Immediate:** Delete broken files
2. **Today:** Extend sipService.ts with call control
3. **This Week:** Add LiveKit fields to database
4. **Next Week:** Implement LiveKit webhooks
5. **After Testing:** Switch Telnyx to SIP connection

## Questions to Answer

1. **Do we need both Telnyx webhooks AND LiveKit webhooks during transition?**
   - Yes - Telnyx for existing calls, LiveKit for new calls

2. **Can existing call_sessions work with both models?**
   - Yes - add nullable LiveKit fields, keep existing Telnyx fields

3. **How to identify which approach a call is using?**
   - If `room_name` is set → LiveKit SIP
   - If only `call_control_id` → Telnyx Call Control

4. **Do we need to maintain call_control_id for transferred calls?**
   - No - LiveKit manages transfer completely

5. **Can we use same phone number for both approaches?**
   - No - must switch fully per number (configure in Telnyx portal)
