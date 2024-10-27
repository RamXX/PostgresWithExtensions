# PostgresSQL with Extensions

# Description
This repo contains a Python program to build and deploy a Docker container with Postgres 16 and 3 additional extensions, all in their latest versions:

1. pgvecto.rs - for vector storage
2. Apache AGE - for graphs using OpenCypher
3. TimescaleDB - for time series data

Every operation, from build to run to delete, can be performed from the same Python program.

It performs all the modifications needed in the config files, and runs extensive testing and verification that each extension is loaded and setup correctly.

# Usage

Create a `.env` file. You can use the `.env.example` as a reference or rename it. Populate the name parameters needed.

Install the only dependecy: `pip install python-dotenv -U`.

Review the options with `--help`:

```sh
python ./postgres_setup --help                                                                                          


usage: postgres_setup.py [-h] [--container-name CONTAINER_NAME] [--port PORT] [--volume VOLUME] [--remove-volume] [--platform PLATFORM]
                         [--dockerfile DOCKERFILE]
                         {start,remove,build,verify,test,full-setup}

PostgreSQL Docker container management with extensions

positional arguments:
  {start,remove,build,verify,test,full-setup}
                        Command to execute

options:
  -h, --help            show this help message and exit
  --container-name CONTAINER_NAME
                        Name for the Docker container (default: postgres-extensions)
  --port PORT           Port to expose PostgreSQL (default: from .env or 5432)
  --volume VOLUME       Volume name (default: from .env or postgres-extensions-data)
  --remove-volume       Remove volume when removing container
  --platform PLATFORM   Platform for Docker build (default: auto-detected)
  --dockerfile DOCKERFILE
                        Dockerfile to use (default: PostgresWithExtensions.dockerfile)

Examples:
  postgres_setup.py start                    Start a new container with default settings
  postgres_setup.py remove --remove-volume   Remove container and its volume
  postgres_setup.py build                    Build the Docker image
  postgres_setup.py verify                   Verify extension installation
  postgres_setup.py test                     Run extension tests
  postgres_setup.py full-setup               Build image and start container
```

Everything should be self-explanatory. Open to PRs if you think a feature should be added or you find any bugs.