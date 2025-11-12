# AICO LiveKit - Dynamic Provider System

## 🎯 Overview

This project now features a **highly efficient, clean abstraction layer** for STT/TTS/LLM providers that can be:
- ✅ **Organization-scoped**: Each organization can configure different providers
- ✅ **Dynamically loaded**: Providers instantiated at runtime from backend API
- ✅ **Externally configurable**: Bind to any external API or internal server
- ✅ **Locally testable**: Full support for local development with Makefiles
- ✅ **Production-ready**: Efficient caching, fallback chains, graceful degradation

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Backend (TypeScript)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Provider Registry  →  Provider Service               │ │
│  │  (System-wide)         (Organization-scoped)          │ │
│  │                                                        │ │
│  │  • Provider definitions (STT/TTS/LLM)                 │ │
│  │  • Organization configs (per-provider settings)       │ │
│  │  • Secrets management (API keys, tokens)              │ │
│  │  • Priority & fallback chains                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            │ REST API                        │
│   GET /api/providers/organization/enabled?type=stt         │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  Agent Worker (Python)                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Provider Loader  →  Provider Factory  →  Agent        │ │
│  │  (Fetch configs)     (Instantiate)        (Use)        │ │
│  │                                                         │ │
│  │  1. Fetch org provider configs from backend            │ │
│  │  2. Cache configs (5min TTL)                           │ │
│  │  3. Instantiate providers (LiveKit plugins or custom)  │ │
│  │  4. Create AgentSession with providers                 │ │
│  │  5. Handle graceful fallback to env vars               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Supported Providers:                                        │
│  • STT: Deepgram, Vosk, Whisper                             │
│  • TTS: Piper, ElevenLabs, Cartesia, OpenAI                 │
│  • LLM: OpenAI, Groq, Gemini, Claude, Azure OpenAI         │
└──────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Local Development (No API Keys Needed)

```bash
cd agent-worker

# Start with local providers (Vosk + Piper)
make dev-local

# Or explicitly:
make dev-vosk-piper
```

### 2. Test with Cloud Providers

```bash
# Set API keys
export DEEPGRAM_API_KEY=your_key
export ELEVENLABS_API_KEY=your_key

# Run with Deepgram + ElevenLabs
make dev-deepgram-elevenlabs
```

### 3. Production Deployment

```bash
# Backend loads configs from database
docker-compose up -d

# Agent fetches provider configs per organization
# Falls back to env vars if backend unavailable
```

## 📁 Project Structure

```
.
├── agent-worker/
│   ├── providers/              # 🆕 Provider abstraction layer
│   │   ├── __init__.py
│   │   ├── types.py           # Provider types & data classes
│   │   ├── loader.py          # Fetch configs from backend (with caching)
│   │   └── factory.py         # Instantiate providers dynamically
│   ├── plugins/               # Custom provider plugins
│   │   ├── vosk_stt.py        # Vosk/Deepgram gateway
│   │   └── piper_tts.py       # Piper TTS gateway
│   ├── agent.py               # 🔄 Updated: Dynamic provider loading
│   ├── Makefile               # 🔄 Enhanced: Provider testing targets
│   ├── PROVIDERS.md           # 🆕 Comprehensive provider documentation
│   ├── .env.example           # 🆕 Configuration examples
│   ├── .env.local-testing     # 🆕 Local testing preset
│   ├── .env.cloud-providers   # 🆕 Cloud providers preset
│   └── .env.production        # 🆕 Production preset
│
├── backend/
│   └── src/
│       ├── providers/
│       │   ├── types.ts              # Provider type definitions
│       │   ├── ProviderRegistry.ts   # System-wide provider registry
│       │   ├── ProviderService.ts    # Org-scoped provider service
│       │   ├── definitions/          # Provider definitions
│       │   │   ├── stt.ts           # STT providers (Deepgram, Vosk, Whisper)
│       │   │   ├── tts.ts           # TTS providers (Piper, ElevenLabs, etc.)
│       │   │   └── llm.ts           # LLM providers (OpenAI, Groq, etc.)
│       │   └── index.ts
│       └── routes/
│           └── providerRoutes.ts    # 🔄 Updated: Agent provider endpoint
│
└── README_PROVIDERS.md              # 🆕 This file
```

## 🔧 Configuration Modes

### Mode 1: Backend-Driven (Production)

**Use Case**: Multi-tenant production, different orgs use different providers

**Configuration**:
```bash
# agent-worker/.env
PROVIDER_ENV_FALLBACK=false  # Enforce backend config
AICO_BACKEND_URL=http://backend:5005
AICO_INTERNAL_API_KEY=<key>
```

**Backend Setup**:
```typescript
// Enable Deepgram for organization
PUT /api/organizations/current/providers/deepgram/config
{
  "config": {"model": "nova-2", "language": "de"},
  "isEnabled": true,
  "priority": 100
}

PUT /api/organizations/current/providers/deepgram/secrets
{
  "secrets": {"apiKey": "your-api-key"}
}
```

### Mode 2: Environment-Based (Development)

**Use Case**: Local development, quick provider testing

**Configuration**:
```bash
# agent-worker/.env.local-testing
PROVIDER_ENV_FALLBACK=true

STT_PROVIDER=vosk
STT_HOST=localhost
STT_PORT=2700

TTS_HOST=localhost
TTS_PORT=5000
```

### Mode 3: Hybrid (Recommended)

**Use Case**: Production with resilience

```bash
PROVIDER_ENV_FALLBACK=true  # Try backend, fallback to env vars
```

## 📊 Supported Providers

### Speech-to-Text (STT)

| Provider | Type | API Key | Quality | Latency | Cost |
|----------|------|---------|---------|---------|------|
| **Deepgram** | Cloud | ✅ Required | High | ~100ms | Pay-per-use |
| **Vosk** | Local | ❌ None | Medium | ~150ms | Free |
| **Whisper** | Local | ❌ None | High | ~300ms | Free (GPU needed) |

### Text-to-Speech (TTS)

| Provider | Type | API Key | Quality | Latency | Cost |
|----------|------|---------|---------|---------|------|
| **Piper** | Local | ❌ None | Medium | ~100ms | Free |
| **ElevenLabs** | Cloud | ✅ Required | Very High | ~200ms | Pay-per-use |
| **Cartesia** | Cloud | ✅ Required | High | ~150ms | Pay-per-use |
| **OpenAI TTS** | Cloud | ✅ Required | High | ~250ms | Pay-per-use |

### Large Language Models (LLM)

| Provider | API Key | Models | Context | Cost |
|----------|---------|--------|---------|------|
| **OpenAI** | ✅ Required | GPT-4o, GPT-4o-mini | 128K | $$$ |
| **Groq** | ✅ Required | Llama 3.1, Mixtral | 32K | $ |
| **Google Gemini** | ✅ Required | Gemini 1.5 Pro/Flash | 2M | $$ |
| **Anthropic** | ✅ Required | Claude 3.5 Sonnet | 200K | $$$ |
| **Azure OpenAI** | ✅ Required | GPT-4, GPT-3.5 | 128K | $$ |

## 🧪 Testing Different Providers

### Local Testing Commands

```bash
cd agent-worker

# Test 1: Local providers (no API keys)
make dev-local

# Test 2: Vosk + Piper explicitly
make dev-vosk-piper

# Test 3: Deepgram + Piper
export DEEPGRAM_API_KEY=your_key
make dev-deepgram-piper

# Test 4: Deepgram + ElevenLabs
export DEEPGRAM_API_KEY=your_key
export ELEVENLABS_API_KEY=your_key
make dev-deepgram-elevenlabs

# Test 5: Verify provider loading
make test-providers
```

### Custom Configuration

```bash
# Copy example env file
cp .env.local-testing .env.custom

# Edit configuration
vim .env.custom

# Load and run
source .env.custom
python agent.py
```

## 🔐 Security Best Practices

1. **Never commit API keys** to version control
2. **Use backend secrets management** for production
3. **Rotate keys regularly** via backend API
4. **Set provider access per organization** (backend controls)
5. **Monitor provider usage** to detect anomalies

## 📈 Performance Optimizations

1. **Caching**: Provider configs cached for 5 minutes (configurable)
2. **Parallel initialization**: STT/TTS loaded concurrently
3. **Lazy loading**: Providers instantiated only when needed
4. **Connection pooling**: HTTP client reused across requests
5. **Graceful degradation**: Fallback providers if primary fails

## 🐛 Troubleshooting

### Provider Not Loading

```bash
# Check agent logs
grep "Loading.*provider" agent-worker.log

# Verify organization providers
curl -H "X-Organization-Id: $ORG_ID" \
     http://localhost:5005/api/providers/organization/enabled

# Test provider system directly
cd agent-worker
make test-providers
```

### API Key Issues

```bash
# For env-based:
echo $DEEPGRAM_API_KEY  # Should print key

# For backend-based:
curl -H "X-Organization-Id: $ORG_ID" \
     http://localhost:5005/api/organizations/current/providers/deepgram
# Check if secrets.apiKey is present
```

### Plugin Not Installed

```bash
# Install LiveKit plugins
pip install livekit-plugins-deepgram
pip install livekit-plugins-elevenlabs
pip install livekit-plugins-cartesia
pip install livekit-plugins-openai
```

## 📚 Documentation

- **[agent-worker/PROVIDERS.md](agent-worker/PROVIDERS.md)**: Comprehensive provider documentation
- **[agent-worker/.env.example](agent-worker/.env.example)**: Full configuration reference
- **Backend Provider API**: See `backend/src/routes/providerRoutes.ts`

## 🎉 Key Benefits

✅ **Clean Architecture**: Provider-agnostic abstractions
✅ **Organization-Scoped**: Multi-tenant with per-org configs
✅ **Flexible**: External APIs or internal servers
✅ **Efficient**: Caching, lazy loading, parallel init
✅ **Testable**: Comprehensive Makefile targets
✅ **Production-Ready**: Graceful fallbacks, error handling
✅ **Extensible**: Easy to add new providers
✅ **Well-Documented**: Examples, guides, troubleshooting

## 🚀 Next Steps

1. **Configure your organization's providers** via backend API
2. **Test locally** with different provider combinations
3. **Deploy to production** with backend-driven configuration
4. **Monitor usage** and optimize for cost/performance
5. **Add custom providers** as needed for your use case

---

**Need Help?** Check [PROVIDERS.md](agent-worker/PROVIDERS.md) or review the `.env.example` files.
