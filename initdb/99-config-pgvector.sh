#!/usr/bin/env bash
set -e

# Configure shared_preload_libraries for AGE and TimescaleDB; pgvector does not require preload
echo "shared_preload_libraries = 'age,timescaledb'" >> "$PGDATA/postgresql.conf"
# Standard search_path without vectors package
echo "search_path = 'ag_catalog, \"\$user\", public'" >> "$PGDATA/postgresql.conf"