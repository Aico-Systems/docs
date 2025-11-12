# Sandboxed Custom Tools System

## Overview

The AICO LiveKit platform includes a powerful **sandboxed custom tools system** that allows organizations to create, test, and execute their own JavaScript-based tools in a secure, isolated environment using `isolated-vm`.

### Key Features

- ✅ **True Isolation**: Each tool executes in its own V8 isolate
- ✅ **Memory & CPU Limits**: Enforced at the VM level
- ✅ **Permission System**: Fine-grained control over capabilities (network, etc.)
- ✅ **Built-in Testing**: Test cases with automatic validation
- ✅ **Code Validation**: AST parsing to detect dangerous patterns
- ✅ **Marketplace Ready**: Versioning, ratings, and publishing support
- ✅ **Organization Scoped**: Tools can be private or public
- ✅ **Seed & Bootstrap**: Global tools seeded from `bootstrap.json`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Tool Execution Flow                      │
└─────────────────────────────────────────────────────────────┘

User Request → API Route → toolService
                             │
                             ├─ Built-in Tool? → ToolRegistry
                             │
                             └─ Custom Tool? → SandboxManager
                                                 │
                                                 ├─ Create Isolate
                                                 ├─ Inject Safe APIs
                                                 ├─ Execute Code
                                                 ├─ Collect Metrics
                                                 └─ Return Result
```

### Core Components

1. **[sandboxManager.ts](src/services/sandboxManager.ts)** - V8 isolate management and code execution
2. **[toolService.ts](src/services/toolService.ts)** - Tool CRUD, validation, testing, publishing
3. **[toolRegistry.ts](src/services/toolRegistry.ts)** - Built-in tool registration
4. **[seedingService.ts](src/seeds/seedingService.ts)** - Bootstrap tool seeding
5. **[toolRoutes.ts](src/routes/toolRoutes.ts)** - API endpoints
6. **[schema.ts](src/db/schema.ts)** - Database schema with all tool fields

---

## Database Schema

The `tool_definitions` table includes:

```typescript
{
  id: UUID                    // Primary key
  organizationId: string | null  // null = global tool
  name: string                // Unique per org
  description: string
  category: string            // 'network', 'utility', 'database', etc.

  // Execution
  handler: string | null      // Built-in handler identifier
  handlerCode: string | null  // Raw JavaScript for sandboxed tools
  runtime: 'isolated-vm' | 'nodejs'

  // Parameters & Metadata
  parameters: JSONB           // Parameter definitions
  permissions: JSONB          // ['network', 'database', ...]
  tags: JSONB                 // Searchable tags

  // Testing & Examples
  examples: JSONB             // Usage examples
  testCases: JSONB            // Automated test cases

  // Marketplace
  version: string             // Semver (e.g., '1.0.0')
  author: string              // Creator ID
  sourceUrl: string           // Git repo or marketplace link
  isPublic: boolean           // Available in marketplace
  ratingAverage: decimal
  ratingCount: integer
  downloadCount: integer
  publishedAt: timestamp

  // System
  isBuiltIn: boolean
  isEnabled: boolean
  metadata: JSONB
  createdAt, updatedAt: timestamp
}
```

---

## API Endpoints

### Core CRUD

```http
GET    /api/tools                    # List tools (with filters)
GET    /api/tools/:toolName          # Get tool details
POST   /api/tools                    # Create custom tool
PUT    /api/tools/:toolName          # Update tool
DELETE /api/tools/:toolName          # Delete tool
```

### Execution & Testing

```http
POST   /api/tools/execute            # Execute a tool
POST   /api/tools/validate           # Validate code without executing
POST   /api/tools/:toolName/test     # Run test cases
```

### Marketplace

```http
GET    /api/tools/llm-format         # Export for LLM function calling
GET    /api/tools/categories         # List categories
POST   /api/tools/:toolName/publish  # Publish to marketplace
```

---

## Creating a Custom Tool

### Example: Weather Lookup Tool

```typescript
POST /api/tools
{
  "name": "weather_lookup",
  "description": "Get current weather for a city using OpenWeatherMap API",
  "category": "external_api",
  "tags": ["weather", "api", "external"],
  "runtime": "isolated-vm",
  "version": "1.0.0",
  "permissions": ["network"],
  "parameters": {
    "city": {
      "type": "string",
      "description": "City name",
      "required": true
    },
    "units": {
      "type": "string",
      "description": "Temperature units",
      "enum": ["metric", "imperial"],
      "default": "metric",
      "required": false
    }
  },
  "handlerCode": `
    async function handler(context, parameters) {
      const city = parameters.city;
      const units = parameters.units || 'metric';

      console.log(\`Fetching weather for \${city}\`);

      try {
        const apiKey = 'YOUR_API_KEY'; // In production, get from org secrets
        const url = \`https://api.openweathermap.org/data/2.5/weather?q=\${city}&units=\${units}&appid=\${apiKey}\`;

        const response = await fetch(url);
        const data = await response.json();

        if (!response.ok) {
          return {
            success: false,
            error: \`Weather API error: \${data.message || 'Unknown error'}\`
          };
        }

        return {
          success: true,
          output: {
            city: data.name,
            temperature: data.main.temp,
            description: data.weather[0].description,
            humidity: data.main.humidity,
            units: units
          }
        };
      } catch (error) {
        return {
          success: false,
          error: \`Failed to fetch weather: \${error.message}\`
        };
      }
    }
  `,
  "examples": [
    {
      "name": "Get London weather",
      "description": "Fetch current weather for London in metric units",
      "parameters": {
        "city": "London",
        "units": "metric"
      }
    }
  ],
  "testCases": [
    {
      "name": "Test valid city",
      "description": "Should return weather data for a valid city",
      "parameters": {
        "city": "London",
        "units": "metric"
      },
      "expectedSuccess": true,
      "timeout": 10000
    }
  ],
  "metadata": {
    "allowedDomains": ["*.openweathermap.org"]
  }
}
```

---

## Tool Handler Specification

### Function Signature

```javascript
async function handler(context, parameters) {
  // Your code here
  return {
    success: boolean,
    output?: any,
    error?: string
  };
}
```

### Context Object

```typescript
interface ToolExecutionContext {
  flowId: string              // Current flow ID
  organizationId: string      // Organization ID
  sessionId: string           // Execution session ID
  userId?: string             // User ID (if available)
  variables: Record<string, unknown>  // Flow context variables
  history: ConversationMessage[]      // Conversation history

  // Method to store values back to flow context
  store(key: string, value: any): boolean
}
```

### Available APIs in Sandbox

#### Always Available

```javascript
// Console (captured for debugging)
console.log(message)
console.info(message)
console.warn(message)
console.error(message)

// Math operations
Math.random()
Math.floor(x)
// ... all Math methods

// JSON
JSON.parse(str)
JSON.stringify(obj)

// Date (limited)
Date.now()
new Date().toISOString()
```

#### With `network` Permission

```javascript
// HTTP requests (domain whitelist required in metadata.allowedDomains)
const response = await fetch(url, {
  method: 'GET',
  headers: { 'Content-Type': 'application/json' }
});

const data = await response.text();  // or response.json()
```

#### Context Methods

```javascript
// Store value in flow context
context.store('variableName', value);

// Access flow variables
const userName = context.variables.userName;
```

### Blocked APIs (Security)

The following are **NOT** available and will cause validation errors:

- ❌ `require()` / `import`
- ❌ `eval()` / `Function()` constructor
- ❌ `process` object
- ❌ `fs` module
- ❌ `child_process`
- ❌ `__dirname` / `__filename`

---

## Security Model

### 1. Code Validation (Pre-execution)

```typescript
// AST parsing detects forbidden patterns
const validation = await validateToolCode(ctx, code, permissions);

if (!validation.valid) {
  throw new Error(validation.errors.join(', '));
}
```

### 2. Isolation (Runtime)

- Each execution runs in a **separate V8 isolate**
- **Memory limit**: 128MB (configurable)
- **Timeout**: 5 seconds (configurable)
- **No shared state** between executions

### 3. Permission System

Tools must declare required permissions:

```typescript
permissions: ['network', 'database', 'filesystem']
```

Permissions are checked before execution:
- `network`: Enables `fetch()` with domain whitelist
- `database`: (Future) Direct database queries
- `filesystem`: (Future) File operations

### 4. Domain Whitelisting (Network)

When `network` permission is granted, domains must be whitelisted:

```json
{
  "metadata": {
    "allowedDomains": [
      "api.example.com",
      "*.openweathermap.org",
      "jsonplaceholder.typicode.com"
    ]
  }
}
```

Wildcard patterns supported: `*.domain.com`

---

## Testing Tools

### Running Tests

```http
POST /api/tools/weather_lookup/test
{
  "testCaseIndex": 0  // Optional: run specific test
}
```

### Response

```json
{
  "results": [
    {
      "name": "Test valid city",
      "success": true,
      "result": {
        "success": true,
        "output": { ... },
        "executionTime": 245
      },
      "duration": 250
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "successRate": 100
  }
}
```

---

## Publishing to Marketplace

### Requirements

Before publishing, a tool must have:

1. ✅ `handlerCode` (not just a handler identifier)
2. ✅ Description >= 20 characters
3. ✅ At least 1 example
4. ✅ At least 1 test case
5. ✅ **All tests passing**

### Publishing

```http
POST /api/tools/weather_lookup/publish
```

This will:
1. Run all test cases
2. Fail if any tests don't pass
3. Set `isPublic = true` and `publishedAt = now()`
4. Make the tool discoverable in the marketplace

---

## Seeding Global Tools

### Adding Tools to Bootstrap

Edit `src/seeds/bootstrap.json`:

```json
{
  "version": "1.0",
  "tools": [
    {
      "organizationId": null,
      "name": "http_request",
      "description": "Make HTTP requests to external APIs",
      "category": "network",
      "runtime": "isolated-vm",
      "handlerCode": "async function handler(context, parameters) { ... }",
      "parameters": { ... },
      "permissions": ["network"],
      "testCases": [ ... ],
      "isBuiltIn": true,
      "isPublic": true
    }
  ]
}
```

### Generating Tool Seeds

Use the helper script:

```bash
cd backend
bun run src/seeds/tools/generateToolSeeds.ts > tools.json
```

Then copy the relevant entries into `bootstrap.json`.

### Seeding Order

On application startup:
1. Organizations
2. Flows
3. **Tools** ← New!

Seeding is **idempotent** - tools are skipped if they already exist.

---

## Built-in Tools

The system includes several default global tools:

### 1. http_request
Make HTTP requests with retry logic and error handling.

**Category**: `network`
**Permissions**: `['network']`

### 2. data_transform
Transform JSON data using map, filter, reduce, sort operations.

**Category**: `utility`
**Permissions**: `[]`

### 3. text_processor
Process text with operations like uppercase, lowercase, capitalize, word count, truncate.

**Category**: `utility`
**Permissions**: `[]`

### 4. datetime_utility
Work with dates and times - format, parse, add days, calculate differences.

**Category**: `utility`
**Permissions**: `[]`

### 5. json_validator
Validate and parse JSON data with strict mode.

**Category**: `utility`
**Permissions**: `[]`

---

## Integration with Flow Builder

Tools integrate seamlessly with the flow builder:

### Tool Node

```typescript
interface ToolNode {
  type: 'tool'
  data: {
    toolName: string
    parameters: Record<string, any>
    outputVariable?: string
    continueOnError?: boolean
    timeout?: number
  }
}
```

### LLM Node with Tools

```typescript
interface LLMNode {
  type: 'llm'
  data: {
    prompt: string
    tools?: string[]  // Tool names to make available
    temperature?: number
  }
}
```

The LLM can choose to call tools, and the flow executor handles the execution automatically.

---

## LiveKit Agent Integration

The Python agent worker can request organization-specific tools:

```python
# agent-worker/agent.py
async def initialize_tools(self, org_id: str):
    response = await self.http_client.get(
        f"{self.backend_url}/api/tools/llm-format?org={org_id}"
    )
    self.available_tools = response.json()
```

Tools are exported in **OpenAI function calling format** for seamless LLM integration.

---

## Performance Considerations

### Execution Metrics

Each tool execution returns:

```typescript
{
  success: boolean
  output: any
  executionTime: number  // Wall time in ms
  metadata: {
    cpuTime: number      // CPU time in ns
    wallTime: number     // Wall time in ns
    memoryUsed: number   // Memory in bytes
    consoleLogs: string[]
  }
}
```

### Optimization Tips

1. **Keep code minimal**: Smaller code = faster compilation
2. **Use built-in APIs**: Faster than complex logic
3. **Set appropriate timeouts**: Default is 5s
4. **Cache fetch results**: Store in `context.store()`
5. **Test performance**: Monitor `executionTime` in production

---

## Future Enhancements

### Phase 2 Features

- [ ] **Tool Marketplace UI**: Browse, search, install tools
- [ ] **Tool Ratings & Reviews**: Community feedback
- [ ] **Tool Dependencies**: Tools can call other tools
- [ ] **Tool Versioning**: Multiple versions, upgrade paths
- [ ] **Database Permission**: Direct SQL queries with RLS
- [ ] **Filesystem Permission**: Read/write files in sandbox
- [ ] **Webhook Support**: External tool triggering
- [ ] **Scheduled Tools**: Cron-like execution
- [ ] **Tool Analytics**: Usage stats, error rates
- [ ] **Code Templates**: Scaffolding for new tools

---

## Troubleshooting

### Common Issues

#### 1. Tool Validation Fails

**Error**: `Code validation failed: eval() is not allowed`

**Fix**: Remove forbidden patterns like `eval()`, `require()`, `import`

#### 2. Timeout Errors

**Error**: `Execution timeout (5000ms exceeded)`

**Fix**:
- Optimize code
- Increase timeout in test cases
- Check for infinite loops

#### 3. Memory Limit Exceeded

**Error**: `Memory limit exceeded (128MB)`

**Fix**:
- Reduce data size in processing
- Stream large datasets
- Increase memory limit (if authorized)

#### 4. Network Permission Denied

**Error**: `Domain not allowed: api.example.com`

**Fix**: Add domain to `metadata.allowedDomains`:
```json
{
  "metadata": {
    "allowedDomains": ["api.example.com"]
  }
}
```

---

## Best Practices

### ✅ DO

- Write clear, descriptive tool names
- Add comprehensive test cases
- Document parameters thoroughly
- Use `console.log()` for debugging
- Handle errors gracefully
- Validate inputs in handler
- Use TypeScript for seed generation

### ❌ DON'T

- Use external dependencies (not supported)
- Store secrets in code (use org configs)
- Make unbounded loops
- Process huge datasets in memory
- Skip test cases
- Publish untested tools

---

## Support & Contributing

For issues or feature requests:
- GitHub: [anthropics/claude-code](https://github.com/anthropics/claude-code/issues)
- Docs: [AICO LiveKit Documentation](../README.md)

---

**Built with 🔒 Security & 🚀 Performance in mind**
