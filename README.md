# PostgreSQL 17 with Extensions (Docker)

This repository provides a multi-stage Docker build for PostgreSQL 17 with three extensions built from source, using the latest available versions:
- [TensorChord](https://github.com/tensorchord/pgvecto.rs) (default) - a high-performance alternative to [pgvector](https://github.com/pgvector/pgvector)
- [Apache AGE](https://github.com/apache/age) - a graph DB extension for Postgres
- [TimescaleDB](https://github.com/timescale/timescaledb) - a time-series DB extension for Postgres

We also have an alternative build with [pgvector](https://github.com/pgvector/pgvector) proper. See below.

# What happened with the Python builder?

I realized we can achieve the same results with a multi-stage Docker build, so I deprecated the old code. It's still available in the `legacy/` directory but I'm not planning on doing additional work on it.

## Build the image

From this directory, run:
```bash
docker build -t postgres-extensions .
```

## Run the container

```bash
docker run -d --name postgres-extensions \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres-extensions
```

## Configuration

The container is pre-configured with optimized settings for a 16GB RAM / 4 vCPU environment. All settings can be customized via environment variables.

### Default Configuration Values

| Category | Setting | Default | Environment Variable |
|----------|---------|---------|---------------------|
| **Memory** | shared_buffers | 4GB | `POSTGRES_SHARED_BUFFERS` |
| | effective_cache_size | 12GB | `POSTGRES_EFFECTIVE_CACHE_SIZE` |
| | work_mem | 64MB | `POSTGRES_WORK_MEM` |
| | maintenance_work_mem | 1GB | `POSTGRES_MAINTENANCE_WORK_MEM` |
| **Connections** | max_connections | 50 | `POSTGRES_MAX_CONNECTIONS` |
| | max_worker_processes | 32 | `POSTGRES_MAX_WORKER_PROCESSES` |
| | max_parallel_workers | 8 | `POSTGRES_MAX_PARALLEL_WORKERS` |
| | max_parallel_workers_per_gather | 2 | `POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER` |
| **Locks** | max_locks_per_transaction | 1024 | `POSTGRES_MAX_LOCKS_PER_TRANSACTION` |
| | max_pred_locks_per_transaction | 512 | `POSTGRES_MAX_PRED_LOCKS_PER_TRANSACTION` |
| **WAL** | max_wal_size | 8GB | `POSTGRES_MAX_WAL_SIZE` |
| | min_wal_size | 2GB | `POSTGRES_MIN_WAL_SIZE` |
| | checkpoint_timeout | 15min | `POSTGRES_CHECKPOINT_TIMEOUT` |
| | checkpoint_completion_target | 0.9 | `POSTGRES_CHECKPOINT_COMPLETION_TARGET` |
| **Autovacuum** | autovacuum_vacuum_scale_factor | 0.02 | `POSTGRES_AUTOVACUUM_VACUUM_SCALE_FACTOR` |
| | autovacuum_analyze_scale_factor | 0.02 | `POSTGRES_AUTOVACUUM_ANALYZE_SCALE_FACTOR` |
| | autovacuum_max_workers | 5 | `POSTGRES_AUTOVACUUM_MAX_WORKERS` |
| | autovacuum_work_mem | 512MB | `POSTGRES_AUTOVACUUM_WORK_MEM` |
| **I/O** | effective_io_concurrency | 100 | `POSTGRES_EFFECTIVE_IO_CONCURRENCY` |
| | random_page_cost | 1.1 | `POSTGRES_RANDOM_PAGE_COST` |
| **TimescaleDB** | max_background_workers | 8 | `TIMESCALEDB_MAX_BACKGROUND_WORKERS` |
| **VectorChord** | probes | 10 | `VCHORDRQ_PROBES` |
| | epsilon | 1.9 | `VCHORDRQ_EPSILON` |

### Hardware Profile Examples

**Small instance (8GB RAM / 2 vCPU):**
```bash
docker run -d --name postgres-extensions \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_SHARED_BUFFERS=2GB \
  -e POSTGRES_EFFECTIVE_CACHE_SIZE=6GB \
  -e POSTGRES_WORK_MEM=32MB \
  -e POSTGRES_MAINTENANCE_WORK_MEM=512MB \
  -e POSTGRES_MAX_CONNECTIONS=30 \
  -e POSTGRES_MAX_WORKER_PROCESSES=16 \
  -e POSTGRES_MAX_PARALLEL_WORKERS=4 \
  -e POSTGRES_AUTOVACUUM_MAX_WORKERS=3 \
  -e POSTGRES_AUTOVACUUM_WORK_MEM=256MB \
  -p 5432:5432 \
  postgres-extensions
```

**Large instance (32GB RAM / 8 vCPU):**
```bash
docker run -d --name postgres-extensions \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_SHARED_BUFFERS=8GB \
  -e POSTGRES_EFFECTIVE_CACHE_SIZE=24GB \
  -e POSTGRES_WORK_MEM=128MB \
  -e POSTGRES_MAINTENANCE_WORK_MEM=2GB \
  -e POSTGRES_MAX_CONNECTIONS=100 \
  -e POSTGRES_MAX_WORKER_PROCESSES=48 \
  -e POSTGRES_MAX_PARALLEL_WORKERS=16 \
  -e POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER=4 \
  -e POSTGRES_AUTOVACUUM_MAX_WORKERS=8 \
  -e POSTGRES_AUTOVACUUM_WORK_MEM=1GB \
  -p 5432:5432 \
  postgres-extensions
```

### Lock Configuration Notes

The lock settings are critical for Apache AGE operations. If you encounter "out of shared memory" errors during graph operations:

1. Increase `POSTGRES_MAX_LOCKS_PER_TRANSACTION` (default: 1024)
2. Increase `POSTGRES_MAX_PRED_LOCKS_PER_TRANSACTION` (default: 512)
3. Consider breaking bulk DDL/imports into smaller transactions

## Test the extensions

After the container is running, execute:
```bash
./test.sh [container_name]
```

If you omit `[container_name]`, it defaults to `postgres-extensions`. This script will:
1. Wait for PostgreSQL to be ready.
2. Create and load the required extensions.
3. Run basic functionality tests for each extension.

All tests must pass for the setup to be valid.

## Alternate Build: pgvector proper

Instead of using the pgvecto.rs package, you can build the official `pgvector` extension from source using `Dockerfile.pgvector`:

1. Build:
   ```bash
   docker build -f Dockerfile.pgvector -t postgres-extensions-pgvector .
   ```
2. Run:
   ```bash
   docker run -d --name pg-pgvector \
     -e POSTGRES_PASSWORD=postgres \
     -p 5433:5432 \
     postgres-extensions-pgvector
   ```
3. Test:
   ```bash
   ./test-pgvector.sh [container_name]
   ```
   If you omit `[container_name]`, it defaults to `pg-pgvector`.

Note: The pgvector build does not include VectorChord-specific settings but shares all other PostgreSQL optimization settings.
