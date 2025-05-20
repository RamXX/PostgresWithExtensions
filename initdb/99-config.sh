#!/usr/bin/env bash
set -e

# Configure shared_preload_libraries and search_path
echo "shared_preload_libraries = 'age,timescaledb,vectors'" >> "$PGDATA/postgresql.conf"
echo "search_path = 'ag_catalog, \"\$user\", public, vectors'" >> "$PGDATA/postgresql.conf"
# Set max_locks_per_transaction (default 256, override via POSTGRES_MAX_LOCKS_PER_TRANSACTION)
echo "max_locks_per_transaction = ${POSTGRES_MAX_LOCKS_PER_TRANSACTION:-256}" >> "$PGDATA/postgresql.conf"