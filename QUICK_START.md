# Quick Start: Logto Authentication in Aico LiveKit

## ✅ Problem Solved

The network conflict has been resolved. The Makefile now properly cleans up any stale networks before starting Logto.

## 🚀 Getting Started

### 1. Start Logto (Already Running!)

```bash
make logto
```

✅ **Status**: Logto is now running
- Admin Console: http://localhost:3004
- API Endpoint: http://localhost:3003

### 2. Create Management Application

Open http://localhost:3004 in your browser and:

1. Click **Applications** in the sidebar
2. Click **Create Application**
3. Select **Machine-to-Machine** type
4. Name it: `AICO LiveKit Management`
5. Click **Create**
6. **Copy the App ID and App Secret** (you'll need these next)

### 3. Run Setup Script

```bash
make logto-setup
```

The script will:
- Ask for the Management App ID and Secret (paste from step 2)
- Create API resources and scopes
- Set up roles (Admin, User)
- Create the SPA application
- Create test organization and users
- Update your `.env.dev` file

### 4. Start the Full Stack

```bash
make up
```

This will start:
- LiveKit Server
- Backend (Bun)
- Frontend (Svelte + HTTPS)
- STT Service (Vosk)
- TTS Service (Piper)
- Agent Worker

### 5. Access the Application

Open https://localhost:5173 (note: HTTPS)

**Test Credentials:**
- Email: `admin@livekit.local`
- Password: `LiveKit!Admin2024`

Or:
- Email: `user@livekit.local`
- Password: `LiveKit!User2024`

## 🔧 Useful Commands

```bash
# View logs
make logs                 # All services
make logto-logs          # Just Logto

# Check status
make status              # All services
docker compose -f docker-compose.logto.yml ps  # Logto only

# Restart services
make restart             # All services
make logto-stop && make logto  # Restart Logto

# Clean slate
make logto-wipe         # Remove all Logto data
make clean              # Remove all services + volumes
```

## 🐛 Troubleshooting

### Network Conflict Error
If you see the network error again:
```bash
docker network rm aico-livekit-logto-network
make logto
```

### Can't Access Admin Console
Check Logto is running:
```bash
docker compose -f docker-compose.logto.yml ps
make logto-logs
```

### Authentication Loop
1. Clear browser cache and localStorage
2. Verify `.env.dev` has `VITE_LOGTO_APP_ID` set
3. Check redirect URIs in Logto match: https://localhost:5173/callback

### Setup Script Fails
Make sure you're running from the aico-livekit directory:
```bash
cd /home/nikita/Projects/Gitkubikon/Aico/aico-livekit
make logto-setup
```

## 📚 More Information

See `docs/LOGTO_AUTHENTICATION.md` for detailed documentation including:
- Architecture overview
- Security considerations
- Production deployment guide
- API integration examples

## ✨ What's Different from aico-mvp?

- **Simpler scopes**: Only LiveKit-related permissions
- **Fewer roles**: Just Admin and User
- **Different ports**: 3003/3004 (vs 3001/3002 in mvp)
- **No email connector**: Simplified for development
- **Automatic network cleanup**: Prevents conflicts

## 🎯 Next Steps

After logging in, you'll have access to:
- LiveKit room orchestration
- Real-time voice communication
- STT/TTS integration
- Agent worker management

Happy coding! 🚀
