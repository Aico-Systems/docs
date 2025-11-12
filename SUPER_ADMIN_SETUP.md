# Super Admin Setup Guide

## Understanding the Authentication Architecture

Aico LiveKit uses Logto with a multi-tenant architecture that has **two types of permissions**:

### 1. **API Resource Scopes** (for API access)
These are attached to the API resource (`https://api.aico-livekit.local`) and grant access to backend APIs:
- `livekit:*` - LiveKit operations
- `sip:*` - SIP operations  
- `org:*` - Organization management
- `phone:*` - Phone number management
- `super_admin` - **Global cross-organization access**

### 2. **Organization Permissions** (for business logic)
These control in-app features within an organization:
- `invite:member` - Invite users to organization
- `remove:member` - Remove users from organization
- `manage:roles` - Assign/change user roles
- `manage:settings` - Update organization configuration
- `view:analytics` - View reports
- etc.

## How Super Admin Works

A **Super Admin** user has:
1. The global **`super_admin` scope** (from a global role)
2. This scope bypasses ALL permission checks in the backend
3. Can access ANY organization without being a member
4. Can perform ANY action (invite, remove users, change roles, etc.)

## Current Setup

Looking at your `users.json`:

```json
{
  "email": "admin@livekit.local",
  "username": "admin",
  "password": "LiveKit!Admin2024",
  "name": "LiveKit Admin",
  "role": "Admin",                    // Organization role (Owner/Admin/Member/Viewer)
  "organization": "Aico LiveKit Org",  // Which org they belong to
  "superAdmin": true                   // Assigns global Super Admin role
}
```

## How to Log In as Super Admin

### Step 1: Run the Logto Setup Script
```bash
cd scripts/logto
node logto-setup.js
```

This script will:
1. Create the "Super Admin" global role
2. Assign the `super_admin` scope to that role
3. Create the user `admin@livekit.local`
4. Assign the Super Admin global role to that user

### Step 2: Log In
1. Open your frontend at `http://localhost:5173`
2. Click "Sign In"
3. Use credentials:
   - **Email**: `admin@livekit.local`
   - **Password**: `LiveKit!Admin2024`

### Step 3: Verify Super Admin Status
Once logged in, open the browser console and check:
```javascript
// Should show true
console.log($isSuperAdmin);

// Should include 'super_admin'
console.log($userScopes);
```

## Troubleshooting

### Problem: User doesn't have super_admin scope

**Solution 1: Check Global Role Assignment**
```bash
# In Logto Console (http://localhost:3001)
# Go to: Users → admin@livekit.local → Roles
# Verify "Super Admin" global role is assigned
```

**Solution 2: Re-run Setup Script**
```bash
cd scripts/logto
node logto-setup.js
```

**Solution 3: Manually assign via API**
```bash
# Get the user ID and Super Admin role ID from Logto Console
# Then use Logto Management API to assign
```

### Problem: Super Admin can't access admin panel

Check that:
1. The Super Admin role has the `super_admin` scope
2. The user is actually assigned the Super Admin role (global, not org role)
3. Frontend is checking `$isSuperAdmin` store correctly
4. Backend routes have `requireSuperAdmin(ctx)` middleware

## Testing Super Admin Features

### As Super Admin, you should be able to:

1. **View all organizations**
   - Navigate to "Super Admin" page
   - See list of all organizations with user counts

2. **Manage users across ALL organizations**
   - Select any organization
   - Invite new users to that organization
   - Change user roles in that organization
   - Remove users from that organization

3. **View organization configurations**
   - See LiveKit, Telnyx, OpenAI settings for any org
   - (Future: Edit configurations for any org)

### As Organization Admin, you should be able to:

1. **Manage users in YOUR organization only**
   - Invite members (requires `invite:member` permission)
   - Remove members (requires `remove:member` permission)
   - Change roles (requires `manage:roles` permission)

2. **Manage organization settings**
   - Update configs (requires `manage:settings` permission)

## Permission Matrix

| Action | Super Admin | Org Owner | Org Admin | Org Member |
|--------|-------------|-----------|-----------|------------|
| View all orgs | ✅ | ❌ | ❌ | ❌ |
| Invite users to any org | ✅ | Own org only | Own org only | ❌ |
| Remove users from any org | ✅ | Own org only | Own org only | ❌ |
| Change roles in any org | ✅ | Own org only | Own org only | ❌ |
| Update org config | ✅ | ✅ | ✅ | ❌ |
| View analytics | ✅ | ✅ | ✅ | ✅ |
| Manage billing | ✅ | ✅ | ❌ | ❌ |

## API Endpoints

### Super Admin Endpoints (require `super_admin` scope):
- `GET /api/admin/organizations` - List all organizations
- `GET /api/admin/organizations/:orgId` - Get organization details
- `GET /api/admin/organizations/:orgId/users` - List users in any org
- `POST /api/admin/organizations/:orgId/users/invite` - Invite user to any org
- `DELETE /api/admin/organizations/:orgId/users/:userId` - Remove user from any org
- `PUT /api/admin/organizations/:orgId/users/:userId/roles` - Update user roles in any org

### Organization Admin Endpoints (require org permissions):
- `GET /api/organizations/current/users` - List users in current org (requires `org:read`)
- `POST /api/organizations/current/users/invite` - Invite user (requires `org:write` + `invite:member`)
- `DELETE /api/organizations/current/users/:userId` - Remove user (requires `org:write` + `remove:member`)
- `PUT /api/organizations/current/users/:userId/roles` - Update roles (requires `org:write` + `manage:roles`)

## Best Practices

1. **Minimize Super Admins**: Only assign super admin to absolutely trusted users
2. **Use Organization Roles**: For most users, assign appropriate org roles (Owner, Admin, Member)
3. **Audit Super Admin Actions**: Log all super admin operations
4. **Separate Environments**: Use different super admins for dev/staging/prod

## Quick Reference: User Types

### Super Admin (Global)
```json
{
  "email": "superadmin@company.com",
  "superAdmin": true,
  "role": "Owner",
  "organization": "Main Org"
}
```
→ Has `super_admin` scope + can access ALL orgs

### Organization Owner
```json
{
  "email": "owner@company.com",
  "superAdmin": false,
  "role": "Owner",
  "organization": "My Org"
}
```
→ Has all permissions within "My Org" only

### Organization Admin
```json
{
  "email": "admin@company.com",
  "superAdmin": false,
  "role": "Admin",
  "organization": "My Org"
}
```
→ Has most permissions within "My Org", except billing

### Organization Member
```json
{
  "email": "user@company.com",
  "superAdmin": false,
  "role": "Member",
  "organization": "My Org"
}
```
→ Can use features but cannot manage users/settings
