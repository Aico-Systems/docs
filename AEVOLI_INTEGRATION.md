# AEVOLI Integration with AICO

This document describes how AEVOLI integrates with AICO for LiveKit-powered AI voice/video sessions.

## Overview

AEVOLI uses AICO's LiveKit infrastructure to provide AI-powered communication services. The integration uses:

1. **Organization-scoped API Keys** for server-to-server authentication
2. **Row Level Security (RLS)** for data isolation between organizations
3. **Automatic seeding** during AICO bootstrap

## Architecture

```
AEVOLI Backend (Node.js)
    ↓ (HTTP + API Key)
AICO Backend (Bun)
    ↓ (LiveKit Token)
LiveKit Server
    ↓ (WebRTC)
AEVOLI Frontend
```

### Authentication Flow

1. AEVOLI backend holds an API key for the "AEVOLI" organization in AICO
2. AEVOLI backend calls AICO API endpoints with `Authorization: Bearer <api_key>`
3. AICO validates the API key and sets organization context for RLS
4. AICO returns LiveKit tokens that AEVOLI frontend uses to connect directly to LiveKit

## Setup

### 1. Bootstrap AICO with AEVOLI Organization

The AEVOLI organization is automatically created when you run:

```bash
cd AICO
make rebootstrap
```

This will:
- Create the "AEVOLI" organization in Logto
- Seed the AEVOLI organization in AICO database
- Generate an API key for AEVOLI
- Apply RLS policies to protect data

The API key will be printed in the logs during seeding (dev/test only).

### 2. Configure AEVOLI Environment

Add the generated API key to AEVOLI's environment:

```env
AICO_API_KEY=ak_test_xxxxxxxxxxxxx
AICO_BASE_URL=http://aico-backend:5005
AICO_ORGANIZATION_ID=<logto-org-id>
```

### 3. Verify Integration

Test the connection:

```bash
# From AEVOLI backend container
curl http://aico-backend:5005/api/aico/health \
  -H "Authorization: Bearer $AICO_API_KEY"
```

## API Key Management

### View API Keys (AICO Frontend)

Navigate to Organization Settings → API Keys (to be implemented in UI).

### Create API Key Manually (if needed)

```bash
cd AICO
make db-shell
```

```sql
-- Insert new API key
INSERT INTO api_keys (
  id,
  organization_id,
  name,
  key_hash,
  key_prefix,
  scopes,
  enabled,
  created_by
) VALUES (
  'ak_manual_' || extract(epoch from now())::text,
  '<org-id-from-logto>',
  'Manual API Key',
  encode(digest('ak_test_yourkeyhere', 'sha256'), 'hex'),
  'ak_test_yourkey',
  '["flows:read", "flows:execute", "livekit:*"]'::jsonb,
  true,
  'manual-creation'
);
```

### Rotate API Key

API keys can be rotated via the AICO API:

```bash
POST /api/api-keys/:keyId/rotate
Authorization: Bearer <your-logto-token>
```

This will:
- Generate a new key
- Revoke the old key immediately
- Return the new key (only shown once!)

## Row Level Security (RLS)

All organization-scoped tables enforce RLS policies:

```sql
-- Example: API keys table policy
CREATE POLICY tenant_isolation_policy ON api_keys
  USING (
    is_super_admin() OR 
    organization_id = get_current_tenant_id()
  );
```

### Setting Organization Context

AICO automatically sets the organization context when:
1. A Logto token is validated (extracts organization from token)
2. An API key is validated (uses key's organization_id)

```typescript
// Internally handled by tenantContext.ts
await databaseService.withOrganizationContext(organizationId, async (db) => {
  // All queries here are scoped to this organization
});
```

## Database Schema

### API Keys Table

```sql
CREATE TABLE api_keys (
  id VARCHAR(64) PRIMARY KEY,
  organization_id VARCHAR(255) NOT NULL REFERENCES organizations(id),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  key_hash VARCHAR(128) NOT NULL UNIQUE,  -- SHA-256 hash
  key_prefix VARCHAR(16) NOT NULL,        -- First 16 chars for logs
  scopes JSONB NOT NULL DEFAULT '[]',     -- ["flows:read", "livekit:*"]
  rate_limit JSONB,
  enabled BOOLEAN NOT NULL DEFAULT true,
  expires_at TIMESTAMPTZ,
  created_by VARCHAR(255) NOT NULL,
  last_used_at TIMESTAMPTZ,
  usage_count JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);
```

## Available Scopes

API keys can have fine-grained permissions:

- `flows:read` - List and view flow definitions
- `flows:execute` - Start and execute flows
- `flows:*` - Full flow access
- `livekit:read` - View LiveKit config
- `livekit:create-session` - Create LiveKit sessions and tokens
- `livekit:*` - Full LiveKit access
- `sessions:read` - View session details
- `sessions:monitor` - Monitor session logs and events
- `agents:read` - List agents
- `api-keys:read` - View API keys (admin)
- `api-keys:write` - Manage API keys (admin)
- `*` - Full access (dangerous!)

## AEVOLI Organization Configuration

Located in `AICO/backend/src/seeds/data/organizations.json`:

```json
{
  "id": "aevoli",
  "name": "AEVOLI",
  "metadata": {
    "description": "AEVOLI platform integration",
    "tier": "enterprise",
    "apiKeys": [
      {
        "name": "AEVOLI Production Key",
        "description": "Primary API key for AEVOLI",
        "scopes": [
          "flows:read",
          "flows:execute",
          "livekit:read",
          "livekit:create-session",
          "sessions:read",
          "sessions:monitor",
          "agents:read"
        ],
        "rateLimit": {
          "requestsPerMinute": 100,
          "requestsPerHour": 5000
        }
      }
    ]
  }
}
```

## User Accounts

A service account is created in Logto for AEVOLI:

- **Email**: service@aevoli.com
- **Username**: aevoli-service
- **Password**: AEVOLI!Service2024
- **Organization**: AEVOLI
- **Role**: Owner

Located in `AICO/scripts/logto/users.json`.

## Troubleshooting

### API Key Not Working

1. Check if key is enabled:
```sql
SELECT id, name, enabled, revoked_at FROM api_keys WHERE key_prefix = 'ak_test_xxx';
```

2. Verify organization ID matches:
```sql
SELECT id, name FROM organizations WHERE name = 'AEVOLI';
```

### RLS Blocking Queries

If you need to bypass RLS for debugging (super admin only):

```sql
-- Check current context
SELECT current_setting('app.organization_id', true);
SELECT current_setting('app.is_super_admin', true);

-- Set super admin context
SELECT set_config('app.is_super_admin', 'true', false);
```

### Re-generate API Key

If you lost the API key:

```bash
cd AICO
make rebootstrap
```

Or manually create a new one and rotate the old key via API.

## Security Best Practices

1. **Never commit API keys** - Use environment variables
2. **Rotate keys regularly** - Set expiration dates
3. **Use minimal scopes** - Only grant necessary permissions
4. **Monitor usage** - Check `usage_count` and `last_used_at`
5. **Revoke unused keys** - Clean up old integrations
6. **Rate limit** - Set appropriate limits for each key

## Production Deployment

For production:

1. Use `ak_live_*` keys (generated when `NODE_ENV=production`)
2. Store keys in a secret manager (Vault, AWS Secrets Manager, etc.)
3. Enable key expiration and rotation policies
4. Set up monitoring and alerts for:
   - Failed authentication attempts
   - Unusual usage patterns
   - Keys nearing expiration
5. Use separate keys for different AEVOLI environments (dev, staging, prod)

## References

- AICO Backend: `/home/nikita/Projects/AEVOLI/AICO/backend`
- AEVOLI Integration Code: `/home/nikita/Projects/AEVOLI/AEVOLI/backend/src/services/aicoService.ts`
- API Key Routes: `/home/nikita/Projects/AEVOLI/AICO/backend/src/routes/apiKeyRoutes.ts`
- RLS Policies: `/home/nikita/Projects/AEVOLI/AICO/backend/src/db/triggers.sql`
