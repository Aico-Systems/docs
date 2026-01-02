# AICO Data Archival & Retention System

## Overview

The AICO backend includes an automated data archival system that preserves all historical data while keeping the active database performant. Data is never deleted—only archived to persistent storage.

---

## System Components

### 1. **Log Archival Service** (`backend/src/services/archival/logArchivalService.ts`)
Archives old flow execution logs to prevent database bloat.

- **Archives**: `flow_execution_logs` table
- **Retention**: Configurable (default: 90 days)
- **Schedule**: Monthly (1st of month at 2 AM UTC)
- **Output**: Compressed JSON files with integrity checksums

### 2. **Session Archival Service** (`backend/src/services/archival/sessionArchivalService.ts`) ⭐ **NEW**
Archives old flow execution sessions and their deltas - **CRITICAL for database performance**.

- **Archives**: `flow_execution_sessions` and `flow_execution_deltas` tables
- **Retention**: Configurable (default: 90 days)
- **Schedule**: Monthly (1st of month at 2 AM UTC)
- **Output**: Two JSON files (sessions + deltas) with integrity checksums
- **Impact**: Handles 90%+ of database writes (deltas are highest volume data)

### 3. **Call Archival Service** (`backend/src/services/archival/callArchivalService.ts`) ⭐ **NEW**
Archives call sessions and events for compliance.

- **Archives**: `call_sessions` and `call_events` tables
- **Retention**: Configurable (default: 12 months for compliance)
- **Schedule**: Monthly (1st of month at 2 AM UTC)
- **Output**: Two JSON files (sessions + events) with integrity checksums
- **Compliance**: HIPAA/PCI requirements for call recording retention

### 4. **Memory Cleanup Job** (`backend/src/jobs/memoryCleanupJob.ts`)
Cleans up expired memory chunks while archiving them for compliance.

- **Archives**: `memory_chunks` table (where `expires_at < now()`)
- **Schedule**: Daily at 2 AM UTC
- **Output**: JSON archives of expired chunks

### 5. **Job Scheduler** (`backend/src/jobs/scheduler.ts`)
Cron-based scheduler that manages all archival jobs.

- **Integration**: Automatically starts with backend (see `backend/src/main.ts`)
- **Graceful Shutdown**: Stops cleanly on backend shutdown
- **Manual Triggers**: Supports admin-initiated archival runs

---

## Configuration

### Environment Variables (`.env.dev`)

#### Basic Settings
```bash
# Enable/disable archival system
ARCHIVAL_ENABLED=true

# Storage backend: 'local' or 's3'
ARCHIVAL_STORAGE_TYPE=local

# Archive retention period (days)
ARCHIVAL_RETENTION_DAYS=90

# Export format: 'json' or 'parquet'
ARCHIVAL_FORMAT=json

# Compression: 'gzip', 'zstd', or 'none'
ARCHIVAL_COMPRESSION=gzip

# Cron schedules (UTC timezone)
ARCHIVAL_SCHEDULE_CRON=0 2 1 * *          # Monthly on 1st at 2 AM
MEMORY_CLEANUP_SCHEDULE_CRON=0 2 * * *    # Daily at 2 AM
```

#### Local Storage (Docker)
```bash
ARCHIVAL_STORAGE_TYPE=local
ARCHIVAL_PATH=/data/archives  # Maps to Docker volume
```

**Docker Volume**: Defined in `docker-compose.yml`
```yaml
services:
  backend:
    volumes:
      - aico_archives:/data/archives  # Persistent across container restarts

volumes:
  aico_archives:  # Named volume for archival storage
```

#### S3 Storage (Production)
```bash
ARCHIVAL_STORAGE_TYPE=s3
ARCHIVAL_PATH=s3://your-bucket-name/aico-archives

# AWS S3 credentials
ARCHIVAL_S3_REGION=us-east-1
ARCHIVAL_S3_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
ARCHIVAL_S3_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# For MinIO/custom S3-compatible storage
ARCHIVAL_S3_ENDPOINT=http://minio:9000
```

#### Memory Cleanup
```bash
MEMORY_CLEANUP_ENABLED=true
MEMORY_CLEANUP_SCHEDULE_CRON=0 2 * * *  # Daily at 2 AM UTC
```

---

## Archive Structure

### Local Storage (`/data/archives/`)
```
/data/archives/
├── flow_logs/
│   ├── flow_logs_2024-01-01_to_2024-03-31.json.gz
│   ├── flow_logs_2024-04-01_to_2024-06-30.json.gz
│   └── flow_logs_2024-07-01_to_2024-09-30.json.gz
├── flow_sessions/  ⭐ NEW
│   ├── flow_sessions_2024-01-01_to_2024-03-31.json
│   ├── flow_sessions_2024-04-01_to_2024-06-30.json
│   └── flow_sessions_2024-07-01_to_2024-09-30.json
├── flow_deltas/  ⭐ NEW (CRITICAL - highest volume)
│   ├── flow_deltas_2024-01-01_to_2024-03-31.json
│   ├── flow_deltas_2024-04-01_to_2024-06-30.json
│   └── flow_deltas_2024-07-01_to_2024-09-30.json
├── call_sessions/  ⭐ NEW
│   ├── call_sessions_2024-01-01_to_2024-03-31.json
│   └── call_sessions_2024-04-01_to_2024-06-30.json
├── call_events/  ⭐ NEW
│   ├── call_events_2024-01-01_to_2024-03-31.json
│   └── call_events_2024-04-01_to_2024-06-30.json
└── memory_chunks/
    ├── expired_chunks_2024-12-01_1701388800000.json
    └── expired_chunks_2024-12-15_1702598400000.json
```

### S3 Storage (`s3://bucket/aico-archives/`)
```
s3://your-bucket-name/aico-archives/
├── flow_logs/
│   └── flow_logs_2024-01-01_to_2024-03-31.json.gz
├── flow_sessions/  ⭐ NEW
│   └── flow_sessions_2024-01-01_to_2024-03-31.json
├── flow_deltas/  ⭐ NEW
│   └── flow_deltas_2024-01-01_to_2024-03-31.json
├── call_sessions/  ⭐ NEW
│   └── call_sessions_2024-01-01_to_2024-03-31.json
├── call_events/  ⭐ NEW
│   └── call_events_2024-01-01_to_2024-03-31.json
└── memory_chunks/
    └── expired_chunks_2024-12-01_1701388800000.json
```

---

## Usage

### Automatic Operation (Recommended)

The archival system runs automatically when the backend starts:

```bash
# Backend startup logs
Step 9/10: Starting job scheduler...
✓ Job scheduler started {
  "log-archival": { "nextRun": "2025-02-01T02:00:00.000Z" },
  "session-archival": { "nextRun": "2025-02-01T02:00:00.000Z" },  ⭐ NEW
  "call-archival": { "nextRun": "2025-02-01T02:00:00.000Z" },     ⭐ NEW
  "memory-cleanup": { "nextRun": "2025-01-02T02:00:00.000Z" }
}
```

Jobs will execute according to their cron schedules automatically.

### Manual Triggering (Testing/Admin)

You can manually trigger archival jobs programmatically:

```typescript
import { jobScheduler } from "./jobs/scheduler.js";

// Trigger log archival immediately
await jobScheduler.triggerJob("log-archival");

// Trigger session archival immediately (CRITICAL)
await jobScheduler.triggerJob("session-archival");

// Trigger call archival immediately
await jobScheduler.triggerJob("call-archival");

// Trigger memory cleanup immediately
await jobScheduler.triggerJob("memory-cleanup");

// Check job status
const status = jobScheduler.getStatus();
console.log(status);
// Output: { 
//   "log-archival": { nextRun: "2025-02-01T02:00:00.000Z" },
//   "session-archival": { nextRun: "2025-02-01T02:00:00.000Z" },
//   "call-archival": { nextRun: "2025-02-01T02:00:00.000Z" },
//   ...
// }
```

---

## Storage Estimates

### Before Complete Archival Implementation
- **Active Database**: ~500-800 MB
- **Growth Rate**: ~10-20 MB/day (logs + sessions + deltas + calls)
- **Critical Issue**: `flowExecutionDeltas` represents 90%+ of database writes

### After Complete Archival (90-day retention for sessions, 12-month for calls)
- **Active Database**: ~200-300 MB (3 months of recent data)
- **Archived Data**: Compressed to 10-20x smaller
  - Example: 500 MB of sessions/deltas → ~25-50 MB compressed
  - Example: 100 MB of calls → ~5-10 MB compressed

### Data Volume Breakdown
- **flowExecutionDeltas**: 60-70% of total database size (50-100+ per session)
- **flowExecutionSessions**: 15-20% (large JSON fields: initialState, workingMemoryCache, history)
- **callEvents**: 10-15% (50-100+ per call, every Telnyx webhook)
- **flowExecutionLogs**: 5-10% (per-node execution logging)
- **callSessions**: 2-5% (call metadata)
- **memoryChunks**: 1-3% (depends on memory node usage)

### Cost Comparison

| Storage Type | Monthly Cost (100 GB archived) | Notes |
|--------------|-------------------------------|-------|
| Docker Volume | $0 (local disk) | Suitable for dev/small deployments |
| AWS S3 Standard | ~$2.30 | 100 GB × $0.023/GB |
| AWS S3 Glacier | ~$0.40 | 100 GB × $0.004/GB (retrieval fees apply) |
| MinIO (self-hosted) | $0 (your infrastructure) | Full S3 compatibility |

---

## Disaster Recovery

### Restoring Archived Data

#### Local Archives
```bash
# Copy archive back to container
docker cp aico-livekit-backend:/data/archives/flow_logs/flow_logs_2024-01-01_to_2024-03-31.json.gz ./restore/

# Decompress
gunzip ./restore/flow_logs_2024-01-01_to_2024-03-31.json.gz

# Import to database (manual SQL or custom restore script)
psql -U aico_livekit -d aico_livekit < restore_script.sql
```

#### S3 Archives
```bash
# Download from S3
aws s3 cp s3://your-bucket/aico-archives/flow_logs/flow_logs_2024-01-01_to_2024-03-31.json.gz ./restore/

# Decompress and restore (same as local)
gunzip ./restore/flow_logs_2024-01-01_to_2024-03-31.json.gz
```

### Archive Metadata

Each archive includes metadata stored in the `archived_partitions` table:

```sql
SELECT * FROM archived_partitions ORDER BY archived_at DESC;
```

Columns:
- `table_name`: Source table (e.g., "flow_execution_logs")
- `start_date`, `end_date`: Date range of archived data
- `archive_path`: Full path to archive file
- `row_count`: Number of rows archived
- `compressed_size`: Size in bytes
- `archived_at`: Timestamp of archival

---

## Monitoring

### Check Archival Job Status

```typescript
import { jobScheduler } from "./jobs/scheduler.js";

const status = jobScheduler.getStatus();
console.log("Next archival run:", status["log-archival"].nextRun);
console.log("Next cleanup run:", status["memory-cleanup"].nextRun);
```

### View Archive History

```sql
-- Check what has been archived
SELECT 
  table_name,
  partition_name,
  start_date,
  end_date,
  row_count,
  pg_size_pretty(compressed_size) as size,
  archived_at
FROM archived_partitions
ORDER BY archived_at DESC;
```

### Monitor Database Size

```sql
-- View current database size breakdown
SELECT * FROM database_size_stats;
```

---

## Cron Schedule Examples

```bash
# Every day at 2 AM UTC
0 2 * * *

# Every Monday at 3 AM UTC
0 3 * * 1

# First day of every month at 2 AM UTC
0 2 1 * *

# Every 6 hours
0 */6 * * *

# Every Sunday at midnight
0 0 * * 0
```

Use [crontab.guru](https://crontab.guru) to test cron expressions.

---

## Troubleshooting

### Issue: Archives not being created

**Check logs:**
```bash
docker logs aico-livekit-backend | grep archival
```

**Verify configuration:**
```bash
# Ensure ARCHIVAL_ENABLED=true
docker exec aico-livekit-backend env | grep ARCHIVAL
```

**Check disk space (local storage):**
```bash
docker exec aico-livekit-backend df -h /data/archives
```

### Issue: Permission denied writing to `/data/archives`

**Fix volume permissions:**
```bash
# Create directory with correct permissions in Dockerfile
RUN mkdir -p /data/archives && chmod 777 /data/archives
```

Or use a named volume (already configured in `docker-compose.yml`).

### Issue: S3 upload fails

**Check AWS credentials:**
```bash
# Test S3 access from container
docker exec aico-livekit-backend aws s3 ls s3://your-bucket-name/
```

**Common issues:**
- Invalid credentials (check `ARCHIVAL_S3_ACCESS_KEY_ID` and `ARCHIVAL_S3_SECRET_ACCESS_KEY`)
- Incorrect region (check `ARCHIVAL_S3_REGION`)
- Bucket doesn't exist or no write permissions
- MinIO endpoint unreachable (check `ARCHIVAL_S3_ENDPOINT`)

---

## Security Considerations

### Local Storage
- ✅ Archives stored in Docker named volume (persistent across restarts)
- ✅ Volume accessible only to backend container
- ⚠️ No encryption at rest (use encrypted volumes for sensitive data)

### S3 Storage
- ✅ Server-side encryption available (SSE-S3, SSE-KMS)
- ✅ Access controlled via IAM policies
- ✅ Versioning and lifecycle policies supported
- ✅ Audit logging via CloudTrail

### Recommended IAM Policy (S3)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/aico-archives/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

---

## Performance Impact

### Database
- ✅ **No impact during archival** (runs at 2 AM UTC by default)
- ✅ **Faster queries** on active tables (smaller indexes)
- ✅ **Reduced backup time** (smaller active database)

### Disk I/O
- ⚠️ Brief I/O spike during archival (typically < 1 minute for 1M rows)
- ✅ Compression reduces disk write volume by 80-90%

### Network (S3)
- ⚠️ Upload bandwidth usage during archival
- ✅ Compression reduces upload volume by 80-90%
- 💡 **Tip**: Schedule during low-traffic periods

---

## Future Enhancements

### Planned Features
- [ ] Parquet format support (better compression + queryable with DuckDB)
- [ ] Table partitioning by month (for faster archival)
- [ ] Restore API endpoint (on-demand archive retrieval)
- [ ] Archive encryption (AES-256)
- [ ] Multi-region S3 replication
- [ ] Prometheus metrics for monitoring

### Contribution
See implementation plan in `~/.claude/plans/federated-growing-orbit.md`

---

## Support

For issues or questions:
1. Check logs: `docker logs aico-livekit-backend | grep archival`
2. Review this documentation
3. Check database optimization plan: `~/.claude/plans/federated-growing-orbit.md`
4. Open GitHub issue with:
   - Configuration (`.env.dev` snippet)
   - Error logs
   - Docker/database setup details
