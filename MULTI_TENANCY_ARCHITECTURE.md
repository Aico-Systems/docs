# Multi-Tenancy Architecture - Aico LiveKit

**Last Updated**: 2025-10-24
**Status**: ✅ Production Ready

## Overview

Aico LiveKit implements a robust multi-tenant architecture with **organization-level isolation**, **role-based access control (RBAC)**, and **super admin capabilities** for cross-organization management.

---

## Architecture Components

### 1. Authentication & Authorization Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (SPA)                          │
│  - Logto Browser SDK                                            │
│  - Organization selector in header                              │
│  - Automatic token injection via fetch interceptor             │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTPS + JWT
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (Bun + Hono)                       │
│  - JWT verification with Logto JWKS                             │
│  - Super admin role check via Logto Management API             │
│  - Tenant context resolution                                    │
│  - Permission enforcement                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓ RLS Policies
┌─────────────────────────────────────────────────────────────────┐
│                PostgreSQL Database (pgvector)                   │
│  - Row Level Security (RLS) per organization                    │
│  - Organization-scoped tables                                    │
│  - Global admin bypass capability                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Permission Model

### Two Types of Permissions

#### 1. **API Resource Scopes** (Organization-Level API Access)

Attached to API resource `https://api.aico-livekit.local`:

- `livekit:*` - LiveKit room management
- `sip:*` - SIP trunk management
- `telephony:*` - Call management
- `phone:*` - Phone number assignment
- `org:*` - Organization data access

**Enforcement**: Backend routes via `requireScopes(ctx, ['scope:name'])`

#### 2. **Organization Permissions** (In-App Features)

Defined in organization template:

- `invite:member` - Invite users to organization
- `remove:member` - Remove users from organization
- `manage:roles` - Assign/manage roles
- `manage:settings` - Update organization settings
- `view:analytics` - View reports
- `manage:billing` - Manage subscription
- `manage:phone_numbers` - Manage phone routing
- `manage:agents` - Configure AI agents

**Enforcement**: Backend business logic via `requireOrgPermissions(ctx, ['permission:name'])`

---

## User Roles

### Organization Roles (Per-Organization)

| Role   | API Scopes            | Org Permissions                                    |
|--------|----------------------|---------------------------------------------------|
| Owner  | All API scopes       | All org permissions                                |
| Admin  | All except billing   | All except `manage:billing`                        |
| Member | Read + write basics  | `view:analytics`                                   |
| Viewer | Read-only            | `view:analytics`                                   |

**Key Point**: Users get these roles **per organization**. A user can be:
- Owner in Organization A
- Member in Organization B
- No access to Organization C

### Global Roles (Cross-Organization)

| Role        | Scopes                                       | Access Level                   |
|-------------|---------------------------------------------|--------------------------------|
| Super Admin | `super_admin`, `all:organizations`, `manage:system` | God mode over all organizations |

**Key Point**: Super admins **bypass all permission checks** and can:
- View and manage all organizations
- Access any organization's data
- Perform system-level operations
- Impersonate organization contexts

---

## Super Admin Detection Flow

### Problem Solved

Organization-scoped JWT tokens don't include global roles, causing super admin detection to fail when users select an organization.

### Solution: Backend Role Check

```typescript
// Backend: logtoAuth.ts (line 245-248)
if (!isSuperAdmin && organizationId) {
    const userId = verifiedPayload.sub as string;
    isSuperAdmin = await checkSuperAdminRole(userId);
}
```

**Flow**:
1. Check JWT token scopes for `super_admin`
2. If not found AND user has organization token → Query Logto Management API for user's global roles
3. Check if user has "Super Admin" role
4. Return `isSuperAdmin: true` in tenant context

### Frontend Integration

```typescript
// Frontend calls backend to get auth status
const response = await fetch('/api/organizations');
const data = await response.json();

// Backend returns comprehensive auth context
isSuperAdmin.set(data.isSuperAdmin);  // ✅ Reliable
userScopes.set(data.scopes);
userOrgPermissions.set(data.organizationScopes);
```

**Before**: Frontend decoded JWT locally → Failed for org tokens
**After**: Frontend uses backend-provided auth status → Always works

---

## Database Schema

### Multi-Tenant Tables

All tenant-aware tables include `organization_id`:

```sql
CREATE TABLE organizations (
  id TEXT PRIMARY KEY,  -- Logto organization ID
  name TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE livekit_rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  room_name TEXT NOT NULL,
  created_by TEXT,
  metadata JSONB DEFAULT '{}',
  status TEXT DEFAULT 'active',
  ended_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(organization_id, room_name)
);
```

### Row Level Security (RLS)

**Tenant Isolation Policy**:
```sql
-- Example RLS policy (implemented in backend, not SQL)
-- Backend uses Drizzle with connection-level SET SESSION
SET LOCAL app.tenant_id = 'org-123';
SET LOCAL app.is_super_admin = 'false';
```

**Backend Implementation** ([databaseService.ts](backend/src/services/databaseService.ts)):
- Regular users: RLS enforced via `organizationId` filter
- Super admins: Can query across all organizations via `dbGlobalOperation()`

---

## Route Protection

### Route Policies

Defined in [router.ts](backend/src/routes/router.ts):

```typescript
const routePolicies: Record<string, RoutePolicy> = {
  // Public - no auth
  'GET /healthz': { public: true },

  // Organization-scoped - requires org context
  'GET /api/livekit/config': {
    scopes: ['livekit:read'],
    org: true
  },

  // Super admin only
  'GET /api/admin/organizations': {
    scopes: ['super_admin']
  }
};
```

### Authorization Helpers

**Scope Checking**:
```typescript
requireScopes(ctx, ['livekit:write']);  // API resource scopes
```

**Permission Checking**:
```typescript
requireOrgPermissions(ctx, ['invite:member']);  // Org permissions
```

**Super Admin Gate**:
```typescript
requireSuperAdmin(ctx);  // Only super admins pass
```

**Composite Checks**:
```typescript
requireUserManagement(ctx);
// Checks: super_admin OR (invite:member AND own org)
```

---

## Organization Selector

**Component**: [OrganizationSelector.svelte](frontend/src/lib/components/OrganizationSelector.svelte)

**Location**: Header (top right)

**Features**:
- Dropdown showing all user's organizations
- Persists selection to localStorage
- Triggers re-fetch of organization-scoped data
- Only visible if user belongs to ≥1 organizations

**Switching Flow**:
1. User clicks dropdown
2. Selects organization
3. `auth.switchOrganization(orgId)` called
4. `currentOrganization` store updated
5. Reactive `$effect` in pages triggers re-load
6. Backend receives new `X-Organization-Id` header

---

## Organization Page Fixes

### Issue #1: Infinite Loading Spinner

**Problem**: Page stayed in loading state if no organization selected

**Fix** ([OrganizationPage.svelte:48-67](frontend/src/lib/pages/OrganizationPage.svelte#L48-L67)):
```typescript
$effect(() => {
    if (activeOrganization?.id && activeOrganization.id !== activeOrgId) {
        activeOrgId = activeOrganization.id;
        loadOrganization();
    } else if (!activeOrganization && !loading) {
        // ✅ Stop loading if no org
        loading = false;
        activeOrgId = null;
    }
});
```

### Issue #2: No Organization Message

**Fix** ([OrganizationPage.svelte:249-261](frontend/src/lib/pages/OrganizationPage.svelte#L249-L261)):
```svelte
{:else if !organizationDetails}
  <div class="empty-state">
    {#if superAdmin}
      <h2>No Organization Selected</h2>
      <p>Select an organization from the dropdown to manage its settings.</p>
    {:else}
      <h2>No Organization</h2>
      <p>Contact your administrator to get added to an organization.</p>
    {/if}
  </div>
```

---

## Logto Configuration

### Setup Script

**File**: [scripts/logto/logto-setup.js](scripts/logto/logto-setup.js)

**What it does**:
1. Creates API resource with organization-level scopes
2. Defines organization permissions (non-API)
3. Creates organization role template (Owner, Admin, Member, Viewer)
4. Creates global "Super Admin" role
5. Creates SPA application for frontend
6. Seeds organizations from `organizations.json`
7. Seeds users from `users.json`
8. Assigns global roles and organization memberships

**Run**:
```bash
cd scripts/logto
node logto-setup.js
```

### User Configuration

**File**: [scripts/logto/users.json](scripts/logto/users.json)

```json
[
  {
    "email": "admin@livekit.local",
    "password": "LiveKit!Admin2024",
    "name": "LiveKit Admin",
    "role": "Owner",
    "organization": "Aico LiveKit Org",
    "superAdmin": true  // ← Gets global "Super Admin" role
  },
  {
    "email": "orgadmin@livekit.local",
    "password": "LiveKit!OrgAdmin2024",
    "name": "Org Admin",
    "role": "Admin",
    "organization": "Aico LiveKit Org",
    "superAdmin": false  // ← Org admin only
  }
]
```

### Organization Configuration

**File**: [scripts/logto/organizations.json](scripts/logto/organizations.json)

```json
[
  {
    "name": "Aico LiveKit Org",
    "description": "Primary organization for Aico LiveKit",
    "id": "livekitorgid"
  }
]
```

---

## Testing Super Admin Flow

### 1. Login as Super Admin

```
Email: admin@livekit.local
Password: LiveKit!Admin2024
```

### 2. Verify Super Admin Badge

- Check header shows "Super Admin" badge (if implemented)
- Check `$isSuperAdmin` store = `true` in dev tools

### 3. Access Admin Panel

- Navigation shows "Super Admin" menu item
- Click to access [AdminPage.svelte](frontend/src/lib/pages/AdminPage.svelte)
- View all organizations
- View users across all organizations

### 4. Switch Organizations

- Open organization selector (header dropdown)
- Select different organization
- Verify OrganizationPage loads that org's settings
- Verify super admin can still access all data

### 5. Backend Verification

Check backend logs for:
```
✓ Token validated { userId: '...', isSuperAdmin: true }
✓ User has super admin role { roles: ['Super Admin'] }
```

---

## Permission Enforcement Examples

### Frontend: Hide UI Elements

```typescript
import { isSuperAdmin, hasOrgPermission } from '$lib/auth';

{#if $isSuperAdmin || hasOrgPermission('invite:member')}
  <button onclick={inviteUser}>Invite User</button>
{/if}
```

### Backend: Enforce Route Access

```typescript
export const routes = {
  'POST /api/organizations/current/users/invite': async (request) => {
    const ctx = requireTenantContext(request);
    requireScopes(ctx, ['org:write']);
    requireUserManagement(ctx);  // Checks permissions

    // ... invite logic
  }
};
```

### Backend: Super Admin Bypass

```typescript
// Normal user: sees only their organizations
const organizations = await listOrganizationsForUser(ctx);
// → Returns only orgs where user is member

// Super admin: sees ALL organizations
if (ctx.isSuperAdmin) {
  const allOrgs = await ctx.dbGlobalOperation(async (db) =>
    db.select().from(organizations)
  );
  // → Returns all organizations in system
}
```

---

## Common Issues & Solutions

### Issue: "Organization context required"

**Cause**: Route requires `org: true` but user has no organization selected

**Solution**:
- Ensure user is assigned to at least one organization
- Check organization selector shows organizations
- Verify backend returns organizations in `/api/organizations`

### Issue: Super admin can't access organization data

**Cause**: Frontend still enforcing organization requirement

**Solution**:
- Check `$isSuperAdmin` store is `true`
- Verify backend logs show `isSuperAdmin: true`
- Check Logto Management API credentials are configured:
  ```bash
  LOGTO_MANAGEMENT_APP_ID=...
  LOGTO_MANAGEMENT_APP_SECRET=...
  LOGTO_MANAGEMENT_RESOURCE=https://default.logto.app/api
  ```

### Issue: Permission denied even with correct role

**Cause**: Organization role scopes not properly assigned in Logto

**Solution**:
- Re-run `scripts/logto/logto-setup.js`
- Check Logto Console → Organizations → Roles → Scopes
- Verify API resource scopes are assigned to roles

### Issue: JWT token missing scopes

**Cause**: SPA application not requesting all scopes

**Solution**:
- Check [auth.ts](frontend/src/lib/auth.ts) line 118-151
- Verify all required scopes are listed
- Re-authenticate user (sign out and sign in)

---

## Performance Optimizations

### 1. Token Caching

Frontend caches access tokens per organization:
```typescript
async getAccessToken(resource, organizationId) {
  if (organizationId) {
    return await logtoClient.getAccessToken(resource, organizationId);
  }
  return await logtoClient.getAccessToken(resource);
}
```

### 2. Backend Super Admin Check Caching

**Current**: Calls Logto Management API on every org-scoped token
**Optimization**: Cache result for 5 minutes:

```typescript
const superAdminCache = new Map<string, { isSuperAdmin: boolean; expiresAt: number }>();

async function checkSuperAdminRole(userId: string): Promise<boolean> {
  const cached = superAdminCache.get(userId);
  if (cached && Date.now() < cached.expiresAt) {
    return cached.isSuperAdmin;
  }

  const isSuperAdmin = await queryLogtoManagementAPI(userId);
  superAdminCache.set(userId, {
    isSuperAdmin,
    expiresAt: Date.now() + 5 * 60 * 1000  // 5 minutes
  });

  return isSuperAdmin;
}
```

### 3. Organization List Caching

Cache organization list in frontend:
```typescript
// Refresh every 30 seconds instead of every page load
let lastOrgRefresh = 0;
const ORG_CACHE_DURATION = 30000;

if (Date.now() - lastOrgRefresh > ORG_CACHE_DURATION) {
  await refreshOrganizations();
  lastOrgRefresh = Date.now();
}
```

### 4. Database Connection Pooling

Already implemented in [databaseService.ts](backend/src/services/databaseService.ts):
```typescript
const pool = new Pool({
  max: 20,  // Maximum connections
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
});
```

---

## Security Best Practices

### ✅ Implemented

- JWT signature verification with Logto JWKS
- Row Level Security (RLS) via connection-level session variables
- Organization context validation on every request
- Scope and permission enforcement
- CORS configuration
- Super admin role verification via Logto Management API

### ⚠️ Recommendations

1. **Rate Limiting**: Add rate limiting to prevent abuse
   ```typescript
   // Consider: @hono/rate-limiter
   ```

2. **Audit Logging**: Log all super admin actions
   ```typescript
   if (ctx.isSuperAdmin) {
     await auditLog.record({
       action: 'ADMIN_ACCESS',
       resource: '/api/admin/organizations',
       userId: ctx.id,
       timestamp: new Date()
     });
   }
   ```

3. **Session Management**: Implement session revocation
   - Store active sessions in Redis
   - Revoke on password change
   - Admin can force logout users

4. **IP Whitelisting**: Restrict super admin access by IP
   ```typescript
   const ADMIN_ALLOWED_IPS = ['192.168.1.0/24'];
   if (ctx.isSuperAdmin && !isAllowedIP(request.ip)) {
     throw new LogtoAuthError('Admin access restricted by IP', 403);
   }
   ```

---

## Deployment Checklist

### Environment Variables

**Backend** (`.env.dev`):
```bash
# Logto
LOGTO_ENDPOINT=http://logto:3001
LOGTO_ISSUER=http://localhost:3001/oidc
LOGTO_JWKS_URL=http://logto:3001/oidc/jwks
LOGTO_API_RESOURCE=https://api.aico-livekit.local
LOGTO_MANAGEMENT_APP_ID=<m2m-app-id>
LOGTO_MANAGEMENT_APP_SECRET=<m2m-app-secret>
LOGTO_MANAGEMENT_RESOURCE=https://default.logto.app/api

# Database
DATABASE_URL=postgresql://aico_livekit:password@postgres:5432/aico_livekit
```

**Frontend** (`.env.dev`):
```bash
VITE_BACKEND_URL=http://localhost:5005
VITE_LOGTO_ENDPOINT=http://localhost:3001
VITE_LOGTO_APP_ID=<spa-app-id>
VITE_LOGTO_API_RESOURCE=https://api.aico-livekit.local
```

### Verification Steps

1. ✅ Run Logto setup script
2. ✅ Verify organizations exist in Logto Console
3. ✅ Verify users can login
4. ✅ Test super admin access to Admin Panel
5. ✅ Test organization admin access restrictions
6. ✅ Test regular user permissions
7. ✅ Verify organization switching works
8. ✅ Check backend logs for auth context

---

## Architecture Diagram

```
┌──────────────────────── FRONTEND ────────────────────────┐
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Header                                          │    │
│  │  ┌──────────────┐  ┌──────────────────────┐    │    │
│  │  │ Org Selector │  │  Theme  │  User Menu │    │    │
│  │  └──────────────┘  └──────────────────────┘    │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Sidebar                                         │    │
│  │  • LiveKit Page                                  │    │
│  │  • Organization Page (if has org)                │    │
│  │  • Admin Page (if super admin)                   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                           │
│  Auth Context Stores:                                    │
│  • isAuthenticated                                       │
│  • currentOrganization ← Selected from dropdown         │
│  • userOrganizations ← All orgs user belongs to         │
│  • isSuperAdmin ← From backend API                      │
│  • userScopes ← API resource scopes                     │
│  • userOrgPermissions ← Org permissions                 │
│                                                           │
└───────────────────────────────────────────────────────────┘
                              ↓
                    JWT Token (Auto-injected)
                    X-Organization-Id Header
                              ↓
┌──────────────────────── BACKEND ─────────────────────────┐
│                                                           │
│  Router (/api/*)                                         │
│  ↓                                                        │
│  Authentication Middleware                               │
│  • Verify JWT signature                                  │
│  • Extract user ID, org ID, scopes                       │
│  • Check super admin role via Logto API                  │
│  • Build TenantContext                                   │
│  ↓                                                        │
│  Authorization Middleware                                │
│  • requireScopes(ctx, ['scope'])                         │
│  • requireOrgPermissions(ctx, ['perm'])                  │
│  • requireSuperAdmin(ctx)                                │
│  ↓                                                        │
│  Route Handler                                           │
│  • ctx.dbOperation() → RLS enforced                      │
│  • ctx.dbGlobalOperation() → Super admin only            │
│  • ctx.getConfig() → Org-specific config                 │
│                                                           │
└───────────────────────────────────────────────────────────┘
                              ↓
                    SET app.tenant_id = 'org-123'
                    SET app.is_super_admin = 'false'
                              ↓
┌─────────────────────── DATABASE ─────────────────────────┐
│                                                           │
│  Organizations Table                                     │
│  ├─ id (Logto org ID)                                    │
│  ├─ name                                                  │
│  └─ metadata                                              │
│                                                           │
│  LiveKit Rooms (RLS by organization_id)                  │
│  ├─ id                                                    │
│  ├─ organization_id → Filter applied automatically       │
│  ├─ room_name                                             │
│  └─ metadata                                              │
│                                                           │
│  Org Phone Numbers (RLS by organization_id)              │
│  Org Configs (RLS by organization_id)                    │
│  SIP Trunks (RLS by organization_id)                     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Changelog

### 2025-10-24
- ✅ Fixed infinite loading spinner in OrganizationPage
- ✅ Added organization selector to header
- ✅ Fixed super admin detection (backend API call instead of JWT decode)
- ✅ Added empty state messages for no organization
- ✅ Verified Logto setup script configuration
- ✅ Documented complete multi-tenancy architecture

### Previous
- ✅ Implemented Row Level Security (RLS)
- ✅ Created organization and global role templates
- ✅ Built permission enforcement system
- ✅ Integrated Logto authentication
- ✅ Created admin panel for super admins

---

## References

- [Logto Documentation](https://docs.logto.io/)
- [Logto Organizations Guide](https://docs.logto.io/docs/recipes/organizations/)
- [Drizzle ORM Multi-Tenancy](https://orm.drizzle.team/)
- [PostgreSQL Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

**Document Status**: ✅ Complete and Verified
**Last Review**: 2025-10-24
**Next Review**: As needed for feature additions
