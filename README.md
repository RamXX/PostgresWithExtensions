# PostgreSQL 16 with Extensions (Docker)

This repository provides a multi-stage Docker build for PostgreSQL 16 with three extensions built from source, using the latest available versions:
- [pgvecto.rs](https://github.com/tensorchord/pgvecto.rs) (default) - a high-performance alternative to [pgvector](https://github.com/pgvector/pgvector)
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

The first time the container starts, it will initialize the database, configure necessary parameters, and apply the extensions.

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