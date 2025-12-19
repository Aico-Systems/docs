# Frontend Fix Required for Clean Reconnections

## Problem

When user clicks "Restart" in the flow test panel, the frontend calls:

```typescript
async function handleRestartSession() {
  await resetState();  // Disconnects from LiveKit
  await startTestSession();  // Immediately creates new session
}
```

However, LiveKit's `room.disconnect()` is async, and the disconnection may not have fully propagated to the LiveKit server by the time the new session creation request reaches the backend. This causes the backend to see participants still in the room.

## Solution

Add a small delay after disconnect to ensure LiveKit processes the disconnection before creating a new session.

### File to Modify

`frontend/src/lib/components/flow/FlowTestSidebar.svelte`

### Change Required

Replace the `handleRestartSession()` function (around line 637):

**Before:**
```typescript
async function handleRestartSession() {
  if (!flow) return;
  const preservedInput = form.userInput;
  await resetState();
  form = {
    userInput: preservedInput,
  };
  await startTestSession();
}
```

**After:**
```typescript
async function handleRestartSession() {
  if (!flow) return;
  const preservedInput = form.userInput;
  await resetState();
  
  // Wait briefly for LiveKit disconnect to propagate to server
  // This ensures the room is empty when backend checks for participants
  await new Promise(resolve => setTimeout(resolve, 200));
  
  form = {
    userInput: preservedInput,
  };
  await startTestSession();
}
```

## Why This Works

1. `resetState()` calls `disconnectLivekit()` which calls `room.disconnect()`
2. The disconnect is async and needs to propagate through WebRTC/WebSocket to LiveKit server
3. 200ms is enough time for the disconnect event to reach the server
4. Backend then sees room as empty (numParticipants === 0) and reuses it
5. No race condition - clean restart every time

## Alternative Solution (Event-Driven, No Timeout)

If you want to avoid the timeout completely, you could listen for the `ConnectionState.Disconnected` event:

```typescript
async function handleRestartSession() {
  if (!flow) return;
  const preservedInput = form.userInput;
  
  // Wait for actual disconnection event
  const disconnected = new Promise<void>((resolve) => {
    if (!livekitRoom || !livekitRoom.room) {
      resolve();
      return;
    }
    
    const checkState = () => {
      if (livekitRoom?.room?.state === ConnectionState.Disconnected) {
        resolve();
      }
    };
    
    livekitRoom.room.once(RoomEvent.Disconnected, () => resolve());
    checkState(); // Check immediately in case already disconnected
  });
  
  await resetState();
  await disconnected;
  
  form = {
    userInput: preservedInput,
  };
  await startTestSession();
}
```

However, the 200ms timeout is simpler and more reliable.
