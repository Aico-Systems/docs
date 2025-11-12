# Logto Authentication Setup for Aico LiveKit

This document describes the Logto authentication implementation in aico-livekit, mirrored from aico-mvp but simplified for LiveKit orchestration.

## Overview

Aico LiveKit now uses Logto for authentication with the following features:
- User authentication with email/password
- Organization-based multi-tenancy (simplified)
- Role-based access control (Admin, User)
- HTTPS-enabled frontend for secure authentication
- Automatic token injection for API calls

## Architecture

### Components

1. **Logto Services** (docker-compose.logto.yml)
   - PostgreSQL database (port 5434)
   - Logto authentication service (ports 3003/3004)
   - Isolated network: `aico-livekit-logto-network`

2. **Frontend Authentication** (auth.ts)
   - Logto client integration
   - Automatic sign-in flow
   - Token management
   - Organization support

3. **Configuration** (config.ts)
   - Centralized environment variable management
   - Logto endpoint and app ID configuration

## Setup Instructions

### 1. Start Logto Services

```bash
cd aico-livekit
make logto
```

This will:
- Create the Logto network
- Start PostgreSQL and Logto containers
- Make admin console available at http://localhost:3004

### 2. Create Management Application

1. Open Logto Admin Console: http://localhost:3004
2. Go to **Applications** → **Create Application**
3. Select **Machine-to-Machine** application type
4. Name it "AICO LiveKit Management"
5. Click **Create**
6. Copy the **App ID** and **App Secret**

### 3. Run Setup Script

```bash
make logto-setup
```

The script will:
- Prompt for Management Application credentials (if needed)
- Create API resource and scopes
- Create roles (Admin, User)
- Set up the SPA application
- Create organizations and users
- Update .env.dev with the SPA app ID

### 4. Start the Stack

```bash
make up
```

Access the application at: https://localhost:5173

## Default Users

The setup creates two test users:

| Email | Username | Password | Role |
|-------|----------|----------|------|
| admin@livekit.local | admin | LiveKit!Admin2024 | Admin |
| user@livekit.local | user | LiveKit!User2024 | User |

## Environment Variables

The following variables are configured in `.env.dev`:

```bash
# Logto Configuration
LOGTO_ENDPOINT=http://localhost:3003
LOGTO_ADMIN_ENDPOINT=http://localhost:3004
LOGTO_DB_PASSWORD=logtopass
LOGTO_APP_ID=aico-livekit-spa
LOGTO_API_RESOURCE=https://api.aicoflow.xyz

# Frontend Configuration
VITE_LOGTO_ENDPOINT=http://localhost:3003
VITE_LOGTO_APP_ID=aico-livekit-spa
```

## Permissions & Scopes

### Scopes
- `livekit:read` - Read access to LiveKit resources
- `livekit:write` - Write access to LiveKit resources
- `livekit:admin` - Administrative access

### Roles
- **Admin** - Full access (all scopes)
- **User** - Read and write access (no admin)

## Frontend Implementation

### Authentication Flow

1. **App Initialization** (`App.svelte`)
   - Checks authentication status
   - Handles OAuth callback
   - Shows sign-in screen if not authenticated

2. **Auth Manager** (`auth.ts`)
   - Initializes Logto client
   - Manages user session
   - Provides token management methods

3. **Automatic Token Injection**
   - Intercepts `fetch` calls to backend
   - Automatically adds Authorization header
   - Skips for public endpoints

### Usage Example

```typescript
import { auth, isAuthenticated, user } from './lib/auth';

// Sign in
await auth.signIn();

// Sign out
await auth.signOut();

// Get access token
const token = await auth.getAccessToken();

// Switch organization
await auth.switchOrganization('org-id');
```

## Makefile Commands

```bash
# Logto management
make logto              # Start Logto services
make logto-stop         # Stop Logto services
make logto-logs         # View Logto logs
make logto-setup        # Configure Logto
make logto-wipe         # Delete all Logto data

# Full stack
make up                 # Start everything (includes Logto)
make down               # Stop everything
make clean              # Full reset
```

## Differences from aico-mvp

Simplified for LiveKit orchestration:

1. **Fewer Scopes** - Only LiveKit-related permissions (not documents, agents, etc.)
2. **Simpler Roles** - Just Admin and User (no Super Admin, Viewer)
3. **No Email Connector** - Removed SMTP configuration for simplicity
4. **Different Ports** - Logto on 3003/3004 to avoid conflicts with aico-mvp
5. **Default Organization** - Single organization setup

## Troubleshooting

### Logto Admin Console Not Accessible
```bash
make logto-logs
# Check for errors in Logto container
```

### Authentication Loop
1. Clear browser cache and localStorage
2. Check that VITE_LOGTO_APP_ID matches the SPA app ID in Logto
3. Verify redirect URIs in Logto app settings

### Token Issues
1. Ensure backend is on the `aico-livekit-logto-network`
2. Check that LOGTO_API_RESOURCE matches in both frontend and backend
3. Verify access token is being sent in requests

### Fresh Install
```bash
make logto-wipe
make logto
make logto-setup
make up
```

## Security Notes

- HTTPS is required for production (currently using self-signed cert in dev)
- Change default passwords before deploying
- Use environment-specific .env files
- Keep management credentials secure
- Rotate secrets regularly

## Next Steps

For production deployment:
1. Use proper SSL certificates
2. Configure production redirect URIs
3. Set up proper SMTP for email verification
4. Enable additional Logto security features
5. Implement proper secret management
