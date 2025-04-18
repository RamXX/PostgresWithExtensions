#!/usr/bin/env bash
set -e

# Default container name; override by passing argument
CONTAINER_NAME=${1:-postgres-extensions}

echo "Waiting for PostgreSQL to be ready..."
until docker exec -i "$CONTAINER_NAME" pg_isready -U postgres > /dev/null 2>&1; do
  sleep 1
done

echo "Creating and loading extensions..."
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vectors;"
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS age;"
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

echo "Verifying installed extensions..."
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname IN ('age', 'vectors', 'timescaledb');"

echo "Testing Apache AGE extension..."
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c \
  "SELECT * FROM ag_catalog.create_graph('test_graph'); SELECT * FROM ag_catalog.drop_graph('test_graph', true);"

echo "Testing TimescaleDB extension..."
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c \
  "CREATE TABLE test_table(time TIMESTAMPTZ NOT NULL, value DOUBLE PRECISION); SELECT create_hypertable('test_table', 'time'); DROP TABLE test_table;"

echo "Testing pgvector extension..."
docker exec -i "$CONTAINER_NAME" psql -U postgres -d postgres -c \
  "CREATE TABLE items (embedding vector(3)); INSERT INTO items SELECT ARRAY[random(), random(), random()]::real[] FROM generate_series(1,10); CREATE INDEX ON items USING vectors (embedding vector_l2_ops); SELECT * FROM items ORDER BY embedding <-> '[3,2,1]' LIMIT 5; DROP TABLE items;"

echo "All tests passed successfully!"