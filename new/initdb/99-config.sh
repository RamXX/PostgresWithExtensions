#!/usr/bin/env bash
set -e

# Configure shared_preload_libraries and search_path
echo "shared_preload_libraries = 'age,timescaledb,vectors'" >> "$PGDATA/postgresql.conf"
echo "search_path = 'ag_catalog, \"\$user\", public, vectors'" >> "$PGDATA/postgresql.conf"