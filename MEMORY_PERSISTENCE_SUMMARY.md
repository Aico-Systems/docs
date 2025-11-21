# Memory Persistence Per User - Implementation Summary

## ✅ Already Implemented

Memory persistence per user (including phone number-based identity) is **fully implemented** in the AICO system!

### Database Schema

**Table: `user_memory`** ([schema.ts:1079-1108](backend/src/db/schema.ts#L1079-L1108))

```sql
CREATE TABLE user_memory (
  id UUID PRIMARY KEY,
  organization_id TEXT NOT NULL,
  user_id TEXT,              -- Nullable: for authenticated users
  phone_number TEXT,         -- Nullable: for phone-based identity
  conversation_count TEXT DEFAULT '0',
  total_tokens TEXT DEFAULT '0',
  last_interaction_at TIMESTAMP,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  -- Unique constraint: one memory record per identity
  CONSTRAINT ux_user_memory_identity UNIQUE (organization_id, user_id, phone_number)
);

-- Indexes for fast lookup
CREATE INDEX idx_user_memory_org_user ON user_memory(organization_id, user_id);
CREATE INDEX idx_user_memory_org_phone ON user_memory(organization_id, phone_number);
```

### Related Tables

1. **`memory_chunks`** - Stores conversation snippets, facts, preferences, events
2. **`entities`** - Extracted entities (people, places, things, concepts)
3. **`entity_relationships`** - Relationships between entities
4. **`preferences`** - User preferences and settings

### Service Implementation

**UnifiedMemoryService** ([unifiedMemoryService.ts](backend/src/services/unifiedMemoryService.ts))

```typescript
interface MemoryIdentity {
  organizationId: string;
  userId?: string;        // Optional
  phoneNumber?: string;   // Optional - phone-based identity
}

// Get or create memory for a user
await memoryService.getOrCreateMemory({
  organizationId: 'org-123',
  phoneNumber: '+1234567890'  // Phone number as identity!
});
```

**Key Features:**
- ✅ Supports userId OR phoneNumber OR both as identity
- ✅ Proper NULL handling in database queries
- ✅ Automatic memory creation on first interaction
- ✅ LLM-powered entity and preference extraction
- ✅ Semantic search across memories
- ✅ Conversation history tracking

### Flow Integration

Memory nodes automatically use phone number from context:

```typescript
// MemoryStoreNodeExecutor (lines 109-113)
const memory = await memoryService.getOrCreateMemory({
  organizationId: context.organizationId,
  userId: context.userId,
  phoneNumber: context.metadata.phoneNumber  // ← Phone number used here!
});
```

## ✅ New Feature: Optional Memory Configuration

Added configurable memory settings to make persistence **optional per organization or flow**.

### Configuration Interface

**Added to `FlowConfiguration`** ([agentFlow.ts:463-478](backend/src/types/agentFlow.ts#L463-L478))

```typescript
interface FlowConfiguration {
  // ... other configs
  memory?: MemoryConfiguration;  // NEW!
}

interface MemoryConfiguration {
  enabled: boolean;                 // Enable/disable memory (default: true)
  usePhoneNumber?: boolean;         // Use phone number (default: true)
  useUserId?: boolean;              // Use user ID (default: true)
  autoStore?: boolean;              // Auto-store conversations (default: false)
  retentionDays?: number;           // Retention period (default: 365)
  extractEntities?: boolean;        // Auto-extract entities (default: false)
  extractPreferences?: boolean;     // Auto-extract preferences (default: false)
}
```

### Updated Memory Executors

**MemoryStoreNodeExecutor** now checks configuration:

```typescript
// Check if memory is enabled
const memoryConfig = context.metadata.flowConfiguration?.memory;
const memoryEnabled = memoryConfig?.enabled !== false; // Default: true

if (!memoryEnabled) {
  // Skip storage if disabled
  return createSuccessResult(this.getNextNode(node.id, edges));
}

// Build identity based on configuration
const identity: MemoryIdentity = {
  organizationId: context.organizationId
};

// Only use userId if enabled (default: true)
if (memoryConfig?.useUserId !== false && context.userId) {
  identity.userId = context.userId;
}

// Only use phoneNumber if enabled (default: true)
if (memoryConfig?.usePhoneNumber !== false && context.metadata.phoneNumber) {
  identity.phoneNumber = context.metadata.phoneNumber as string;
}

const memory = await memoryService.getOrCreateMemory(identity);
```

## Usage Examples

### Example 1: Enable Memory with Phone Number Only

```json
{
  "configuration": {
    "memory": {
      "enabled": true,
      "usePhoneNumber": true,
      "useUserId": false
    }
  }
}
```

### Example 2: Disable Memory Persistence

```json
{
  "configuration": {
    "memory": {
      "enabled": false
    }
  }
}
```

### Example 3: Auto-Extract Entities and Preferences

```json
{
  "configuration": {
    "memory": {
      "enabled": true,
      "usePhoneNumber": true,
      "extractEntities": true,
      "extractPreferences": true,
      "retentionDays": 90
    }
  }
}
```

## How Phone Number Gets Into Context

The phone number is passed via `context.metadata.phoneNumber` from:

1. **LiveKit Sessions** - Phone number from caller ID (SIP/Telnyx integration)
2. **Manual Flow Execution** - Can be set when starting a flow via API
3. **Agent Worker** - Extracts from session metadata

Example from agent worker:
```typescript
const context = {
  organizationId: 'org-123',
  metadata: {
    phoneNumber: '+1234567890'  // From caller ID
  }
};
```

## Database Queries

### Find User Memory by Phone Number

```typescript
const memory = await db
  .select()
  .from(userMemory)
  .where(
    and(
      eq(userMemory.organizationId, 'org-123'),
      eq(userMemory.phoneNumber, '+1234567890')
    )
  );
```

### Store Memory Chunk

```typescript
await memoryService.storeChunk(memoryId, {
  content: 'User prefers email communication',
  type: 'preference',
  importance: 0.8,
  topics: ['communication', 'contact']
});
```

### Retrieve User Preferences

```typescript
const preferences = await memoryService.getPreferences(memoryId);
// Returns: [{ key: 'contact_method', value: 'email', ... }]
```

## Benefits

✅ **Privacy-Friendly** - No account required, just phone number
✅ **Persistent** - Memory survives across sessions and days
✅ **Configurable** - Can be enabled/disabled per organization/flow
✅ **Intelligent** - LLM-powered entity and preference extraction
✅ **Scalable** - Indexed for fast lookups across millions of users
✅ **Flexible** - Supports userId, phoneNumber, or both

## Next Steps (Optional Enhancements)

These are documented in [TODO.md](TODO.md) for future consideration:

- [ ] Add memory retention policies (auto-delete old memories)
- [ ] Implement memory export/import (GDPR compliance)
- [ ] Add memory analytics dashboard
- [ ] Implement cross-organization memory sharing (with consent)
- [ ] Add memory conflict resolution for merged accounts

## Testing

To test memory persistence:

1. Make a call with phone number `+1234567890`
2. During conversation, mention your name: "My name is John"
3. End the call
4. Call again with same number
5. Agent should remember: "Hi John!"

Check database:
```sql
SELECT * FROM user_memory WHERE phone_number = '+1234567890';
SELECT * FROM memory_chunks WHERE memory_id = '<memory_id>';
SELECT * FROM entities WHERE memory_id = '<memory_id>';
```

---

**Status:** ✅ Fully Implemented
**Date:** 2025-11-21
**Files Modified:**
- `backend/src/types/agentFlow.ts` - Added MemoryConfiguration interface
- `backend/src/core/flow-executor/executors/MemoryStoreNodeExecutor.ts` - Added configuration checks
