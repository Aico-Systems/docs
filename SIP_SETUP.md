# LiveKit SIP Setup for Telnyx Integration

This guide explains how to set up LiveKit SIP on your Hetzner server for self-hosted, open-source telephony with Telnyx.

## Architecture

```
Telnyx Call → Webhook (hooks-dev.aicoflow.xyz) → Local Backend
                                                      ↓
                                              Answers & Dials
                                                      ↓
                                    sip:livekit@sip.aicoflow.xyz
                                                      ↓
                                            Hetzner Server
                                                      ↓
                                        LiveKit SIP Service → LiveKit Server
                                                      ↓
                                              Room Created
                                                      ↓
                                    Agent Worker Connects (local or remote)
```

## Prerequisites

- Hetzner server (sandbox.aicoflow.xyz)
- Domain `sip.aicoflow.xyz` pointing to server IP
- Ports 5060/UDP and 10000-20000/UDP accessible
- Docker & Docker Compose installed

## Step 1: DNS Configuration

Configure DNS A record for your SIP domain:

```dns
sip.aicoflow.xyz    A    <YOUR_SERVER_IP>
```

**Verify DNS resolution:**
```bash
nslookup sip.aicoflow.xyz
# Should return your server IP
```

## Step 2: Firewall Rules

Update Hetzner firewall (via cloud-init or manually):

### Via UFW (Recommended)

```bash
# SSH to your server
ssh deploy@sandbox.aicoflow.xyz

# Allow SIP signaling
sudo ufw allow 5060/udp comment 'LiveKit SIP signaling'

# Allow RTP media
sudo ufw allow 10000:20000/udp comment 'LiveKit RTP media'

# Verify rules
sudo ufw status numbered
```

### Via Hetzner Cloud Console

1. Go to **Firewalls** in Hetzner Cloud Console
2. Select your server's firewall
3. Add inbound rules:
   - **Protocol**: UDP, **Port**: 5060, **Source**: Any IPv4
   - **Protocol**: UDP, **Port**: 10000-20000, **Source**: Any IPv4

## Step 3: Environment Configuration

Update `deploy/.env` on the server with SIP configuration:

```bash
# Telnyx SIP Configuration
TELNYX_SIP_SERVER=sip.telnyx.com
TELNYX_SIP_TRUNK_NAME=aico-sandbox-trunk
SIP_PUBLIC_HOST=sip.aicoflow.xyz
SIP_PUBLIC_PORT=5060
LIVEKIT_SIP_URI=sip:livekit@sip.aicoflow.xyz
```

**Note:** `TELNYX_SIP_USERNAME` and `TELNYX_SIP_PASSWORD` are only needed if using Telnyx SIP Trunk (not required for Voice API).

## Step 4: Deploy Services

The updated `docker-compose.registry.yml` includes:
- **Redis**: Required by LiveKit SIP
- **LiveKit Server**: Core real-time communication server
- **LiveKit SIP**: SIP gateway service

Deploy to sandbox:

```bash
# From local machine
make deploy-sandbox

# Or manually on server
ssh deploy@sandbox.aicoflow.xyz
cd /opt/aico
export IMAGE_TAG=sandbox REGISTRY=ghcr.io REPO_OWNER=aico-systems
docker compose -f deploy/docker-compose.registry.yml up -d redis livekit livekit-sip
```

**Verify services are running:**
```bash
docker compose -f deploy/docker-compose.registry.yml ps
# Should show: redis, livekit, livekit-sip all running
```

## Step 5: Configure LiveKit SIP Trunks

LiveKit SIP requires configuring trunks and dispatch rules via API or CLI.

### Option A: Via Backend API (Recommended)

Your backend includes a `SipService` at [backend/src/services/sipService.ts](../backend/src/services/sipService.ts).

**Create SIP trunk and dispatch rule:**

```bash
# SSH to server
ssh deploy@sandbox.aicoflow.xyz

# Access backend container
docker exec -it aico-api bun repl

# In the REPL:
const { sipService } = await import('./src/services/index.ts');
await sipService.setupDefaultTelnyxRoute('voice-room');
```

This creates:
- Inbound trunk for Telnyx
- Dispatch rule routing calls to `voice-room`

### Option B: Via HTTP API

```bash
curl -X POST https://api.aicoflow.xyz/api/admin/sip/setup \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json"
```

## Step 6: Verify SIP Endpoint

Test that LiveKit SIP is listening:

```bash
# From server
docker exec -it aico-livekit-sip cat /proc/net/udp | grep 13C4
# Should show port 5060 (0x13C4 in hex) in LISTEN state

# Check logs
docker logs aico-livekit-sip --tail 50
# Should show "SIP server started on port 5060"
```

## Step 7: Test Inbound Call

1. Call your Telnyx number: `+4984196423523`
2. Check backend logs:
   ```bash
   docker logs aico-api --tail 100 -f
   ```
3. Should see:
   ```
   ✓ Call initiated → webhook received
   ✓ Call answered
   ✓ Dialing sip:livekit@sip.aicoflow.xyz
   ✓ SIP call answered by LiveKit
   ✓ Calls bridged
   ```
4. Check LiveKit SIP logs:
   ```bash
   docker logs aico-livekit-sip --tail 100 -f
   ```
5. Should see:
   ```
   ✓ Received SIP INVITE
   ✓ Room created: voice-room-XXXXX
   ✓ SIP participant joined
   ```

## Troubleshooting

### SIP calls not connecting

**Check firewall:**
```bash
sudo ufw status | grep 5060
sudo ufw status | grep 10000
```

**Check DNS:**
```bash
dig +short sip.aicoflow.xyz
```

**Check LiveKit SIP is reachable:**
```bash
# From external machine with SIP client
# Try registering to sip.aicoflow.xyz:5060
```

### RTP media not flowing

**Ensure RTP ports are open:**
```bash
sudo ufw allow 10000:20000/udp
```

**Check LiveKit SIP config:**
```bash
docker exec aico-livekit-sip printenv | grep SIP_CONFIG_BODY
```

Should show `use_external_ip: true`

### Backend can't dial to SIP endpoint

**Verify LIVEKIT_SIP_URI is configured:**
```bash
docker exec aico-api printenv | grep LIVEKIT_SIP_URI
# Should show: LIVEKIT_SIP_URI=sip:livekit@sip.aicoflow.xyz
```

**Check backend logs for dial errors:**
```bash
docker logs aico-api | grep -i "sip\|dial"
```

## Local Development

For local development, configure your local `.env.dev` to dial the sandbox SIP endpoint:

```bash
# .env.dev
LIVEKIT_SIP_URI=sip:livekit@sip.aicoflow.xyz
```

When you receive a call:
1. Webhook tunnels to local backend (via `make webhook-tunnel`)
2. Local backend answers and dials `sip:livekit@sip.aicoflow.xyz`
3. Call routes to Hetzner LiveKit SIP
4. LiveKit creates room
5. Local agent worker connects to sandbox LiveKit

## Production Deployment

For production on `aicoflow.com`:

1. Update DNS: `sip.aicoflow.com → PROD_SERVER_IP`
2. Update firewall on production server
3. Configure `deploy/.env` with production SIP domain
4. Deploy: `make deploy-prod`

## Advanced: Multiple SIP Trunks

If you need multiple phone numbers or providers:

```javascript
// Create separate trunk for each provider
await sipService.createTelnyxTrunk(); // Telnyx
await sipService.createTwilioTrunk(); // Twilio (if implemented)

// Create dispatch rules routing to different rooms
await sipService.createDispatchRule({
  roomName: 'sales-calls',
  trunkId: telnyxTrunkId,
  metadata: JSON.stringify({ department: 'sales' })
});
```

## References

- [LiveKit SIP Documentation](https://docs.livekit.io/sip/)
- [LiveKit Self-Hosted SIP](https://docs.livekit.io/home/self-hosting/sip-server/)
- [Telnyx LiveKit Integration](https://developers.telnyx.com/docs/voice/sip-trunking/livekit-configuration-guide)
- [Media Streaming (Alternative)](https://developers.telnyx.com/docs/voice/programmable-voice/media-streaming)
