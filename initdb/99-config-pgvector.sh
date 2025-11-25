#!/usr/bin/env bash
set -e

# PostgreSQL 17 Optimized Configuration
# Designed for: 16GB RAM / 4 vCPU with AGE, TimescaleDB, and pgvector
# All settings are configurable via environment variables

cat >> "$PGDATA/postgresql.conf" <<EOF

# =============================================================================
# Extension Configuration
# =============================================================================
# pgvector does not require shared_preload_libraries
shared_preload_libraries = 'age,timescaledb'
search_path = 'ag_catalog, "\$user", public'

# =============================================================================
# Memory Configuration
# =============================================================================
shared_buffers = ${POSTGRES_SHARED_BUFFERS:-4GB}
effective_cache_size = ${POSTGRES_EFFECTIVE_CACHE_SIZE:-12GB}
work_mem = ${POSTGRES_WORK_MEM:-64MB}
maintenance_work_mem = ${POSTGRES_MAINTENANCE_WORK_MEM:-1GB}

# =============================================================================
# Connection and Worker Settings
# =============================================================================
max_connections = ${POSTGRES_MAX_CONNECTIONS:-50}
max_worker_processes = ${POSTGRES_MAX_WORKER_PROCESSES:-32}
max_parallel_workers = ${POSTGRES_MAX_PARALLEL_WORKERS:-8}
max_parallel_workers_per_gather = ${POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER:-2}

# =============================================================================
# Lock Configuration (critical for Apache AGE)
# =============================================================================
max_locks_per_transaction = ${POSTGRES_MAX_LOCKS_PER_TRANSACTION:-1024}
max_pred_locks_per_transaction = ${POSTGRES_MAX_PRED_LOCKS_PER_TRANSACTION:-512}

# =============================================================================
# WAL and Checkpoint Settings
# =============================================================================
max_wal_size = ${POSTGRES_MAX_WAL_SIZE:-8GB}
min_wal_size = ${POSTGRES_MIN_WAL_SIZE:-2GB}
checkpoint_timeout = ${POSTGRES_CHECKPOINT_TIMEOUT:-15min}
checkpoint_completion_target = ${POSTGRES_CHECKPOINT_COMPLETION_TARGET:-0.9}

# =============================================================================
# Autovacuum Configuration
# =============================================================================
autovacuum = on
autovacuum_vacuum_scale_factor = ${POSTGRES_AUTOVACUUM_VACUUM_SCALE_FACTOR:-0.02}
autovacuum_analyze_scale_factor = ${POSTGRES_AUTOVACUUM_ANALYZE_SCALE_FACTOR:-0.02}
autovacuum_max_workers = ${POSTGRES_AUTOVACUUM_MAX_WORKERS:-5}
autovacuum_work_mem = ${POSTGRES_AUTOVACUUM_WORK_MEM:-512MB}

# =============================================================================
# I/O Settings (optimized for SSD/NVMe)
# =============================================================================
effective_io_concurrency = ${POSTGRES_EFFECTIVE_IO_CONCURRENCY:-100}
random_page_cost = ${POSTGRES_RANDOM_PAGE_COST:-1.1}

# =============================================================================
# TimescaleDB Settings
# =============================================================================
timescaledb.max_background_workers = ${TIMESCALEDB_MAX_BACKGROUND_WORKERS:-8}
EOF

echo "PostgreSQL configuration applied successfully."
