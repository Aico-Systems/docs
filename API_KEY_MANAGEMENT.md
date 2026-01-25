# API Key Management

This document describes the API key management system for AICO, which enables secure server-to-server authentication for external services like AEVOLI.

## Overview

API keys provide a secure way for external services to authenticate with AICO without requiring user Logto tokens. Each API key is:

- **Organization-scoped**: Keys can only access data within their assigned organization
- **Scope-limited**: Keys have specific permissions (e.g., `flows:read`, `flows:execute`)
- **Secure**: Only SHA-256 hashes are stored in the database
- **Auditable**: Usage tracking and last-used timestamps
- **Revocable**: Keys can be disabled or revoked at any time

## Database Schema

API keys are stored in the `api_keys` table with the following structure:

```sql
api_keys
├── id                  # Unique identifier (e.g., ak_1234567890_abc123)
├── organization_id     # Organization this key belongs to
├── name               # Human-readable name
├── description        # Optional description
├── key_hash           # SHA-256 hash of the actual key
├── key_prefix         # First 8 chars for identification (e.g., "ak_live_")
├── scopes             # JSON array of permission strings
├── enabled            # Boolean flag
├── expires_at         # Optional expiration timestamp
├── created_by         # User ID who created the key
├── last_used_at       # Last usage timestamp
├── usage_count        # JSON with usage statistics
├── created_at         # Creation timestamp
├── updated_at         # Last update timestamp
└── revoked_at         # Soft delete timestamp
```

## Backend API

### Endpoints

#### `GET /api/api-keys`
List all API keys for the current organization.

**Response:**
```json
{
  "success": true,
  "data": {
    "keys": [...],
    "total": 5
  }
}
```

#### `POST /api/api-keys`
Create a new API key.

**Request Body:**
```json
{
  "name": "AEVOLI Integration",
  "description": "API key for AEVOLI to start LiveKit sessions",
  "scopes": ["flows:read", "flows:execute", "livekit:*"],
  "expiresAt": "2025-12-31T23:59:59Z",
  "rateLimit": {
    "requestsPerMinute": 60,
    "requestsPerHour": 1000
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "key": "ak_live_abc123def456...",
    "metadata": {
      "id": "ak_1234567890_xyz",
      "name": "AEVOLI Integration",
      "keyPrefix": "ak_live_abc123",
      "scopes": ["flows:read", "flows:execute", "livekit:*"],
      "enabled": true,
      "createdAt": "2024-01-15T10:30:00Z"
    },
    "warning": "Save this key securely! It will not be shown again."
  }
}
```

⚠️ **Important**: The full key is only returned once during creation. Store it securely immediately.

#### `PATCH /api/api-keys/:keyId`
Update an API key (name, description, enabled status, scopes, expiration).

**Request Body:**
```json
{
  "enabled": false,
  "scopes": ["flows:read"]
}
```

#### `DELETE /api/api-keys/:keyId`
Revoke an API key (soft delete).

#### `POST /api/api-keys/:keyId/rotate`
Rotate an API key (creates new key, revokes old one).

**Response:** Returns a new key (same structure as create endpoint).

## Frontend UI

The API key management interface is integrated into the Organization page at `/organization`.

### Features

1. **List API Keys**: View all keys with their status, scopes, and last usage
2. **Create Key**: Modal dialog for creating new keys with scope selection
3. **Secure Display**: New keys are shown once in a modal with copy button
4. **Enable/Disable**: Quick toggle for key status
5. **Rotate Key**: Generate new key and revoke old one in one action
6. **Revoke Key**: Permanently disable a key with confirmation dialog

### Components

- **ApiKeyManagement.svelte**: Main component with table and modals
- **ApiKeyService.ts**: Frontend service for API key operations

## Available Scopes

Common scope patterns:

- `flows:read` - Read flow configurations
- `flows:execute` - Execute flows
- `flows:write` - Create/update flows
- `sessions:read` - Read session data
- `sessions:monitor` - Monitor active sessions
- `livekit:*` - All LiveKit operations
- `agents:read` - Read agent configurations
- `agents:write` - Create/update agents
- `*` - All permissions (use with caution)

## Security Best Practices

### For Developers

1. **Never log full API keys** - Only log key prefixes for debugging
2. **Store keys securely** - Use environment variables or secret managers (Vault, AWS Secrets Manager)
3. **Rotate regularly** - Implement key rotation policies (e.g., every 90 days)
4. **Use minimal scopes** - Grant only the permissions needed
5. **Monitor usage** - Track `last_used_at` and `usage_count` for anomalies
6. **Set expiration dates** - Use `expiresAt` for temporary integrations

### For Administrators

1. **Review keys regularly** - Audit active keys in the organization
2. **Revoke unused keys** - Remove keys that haven't been used in 90+ days
3. **Enforce scope policies** - Limit use of wildcard (`*`) scopes
4. **Enable rate limiting** - Set appropriate rate limits per key
5. **Monitor failed attempts** - Alert on suspicious authentication failures

## Authentication Flow

When an external service makes a request with an API key:

1. Extract the `Authorization: Bearer <api_key>` header
2. Hash the key using SHA-256
3. Look up the key in the database by hash
4. Verify:
   - Key exists and is not revoked
   - Key is enabled
   - Key has not expired
   - Request scope is allowed
5. Set tenant context to the key's organization
6. Track usage (increment count, update `last_used_at`)
7. Process the request with organization-scoped RLS

## Row-Level Security (RLS)

API keys work with Postgres RLS policies to ensure data isolation:

- When a request is authenticated via API key, the `organization_id` is set in the session
- All queries are automatically filtered by this organization ID
- Keys cannot access data from other organizations, even with `*` scope

## Example: AEVOLI Integration

```bash
# AEVOLI environment variables
AICO_API_URL=https://aico.example.com
AICO_API_KEY=ak_live_abc123def456...

# Making a request from AEVOLI
curl -X POST https://aico.example.com/api/flows/execute \
  -H "Authorization: Bearer ak_live_abc123def456..." \
  -H "Content-Type: application/json" \
  -d '{
    "flowId": "flow_123",
    "parameters": {...}
  }'
```

## Seeding Development Keys

During development, API keys can be seeded via the seeding system:

```typescript
// In backend/src/seeds/organizations.json
{
  "id": "aevoli",
  "name": "AEVOLI",
  "apiKeys": [{
    "name": "AEVOLI Development Key",
    "scopes": ["flows:read", "flows:execute", "livekit:*"],
    "enabled": true
  }]
}
```

The seeding script will:
1. Generate a cryptographic key
2. Store the hash in the database
3. Log the full key to the console (development only)

## Troubleshooting

### Key authentication fails

1. Check that the key is enabled and not revoked
2. Verify the key hasn't expired (`expires_at`)
3. Ensure the key has the required scopes for the operation
4. Check backend logs for authentication errors

### Key not found in UI

1. Ensure you're viewing the correct organization
2. Check that the key hasn't been revoked
3. Verify you have the `api-keys:read` scope

### Cannot create new key

1. Ensure you have the `api-keys:write` scope
2. Verify all required fields (name, scopes)
3. Check scope format (must be `resource:action` or `*`)

## Migration Notes

If upgrading from a system without API keys:

1. Run `drizzle-kit push` to apply the `api_keys` table schema
2. Apply RLS policies from `backend/src/db/triggers.sql`
3. Update frontend to include the API key management component
4. Configure external services with new API keys

## Future Enhancements

- [ ] Rate limiting enforcement in middleware
- [ ] IP whitelist support per key
- [ ] Webhook notifications for key events (created, revoked, expired)
- [ ] Key usage analytics dashboard
- [ ] Automatic key rotation reminders
- [ ] API key templates for common use cases
