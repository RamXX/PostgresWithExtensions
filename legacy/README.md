# PostgresSQL with Extensions

# Description
This repo contains a Python program to generate, build and deploy a Docker container with Postgres 16 and 3 additional extensions, all in their latest versions:

1. pgvecto.rs - for vector storage
2. Apache AGE - for graphs using OpenCypher
3. TimescaleDB - for time series data

Every operation, from build to run to delete, can be executed from the same Python program. Most are compiled from source, and it also includes the tweaks needed in the Postgres config file, with internal restart. `build` and `full-setup` will pull the latest versions available for all the extensions.

It performs all the modifications needed in the config files, and runs extensive testing and verification that each extension is loaded and setup correctly.

# Usage

Clone this repo.

Create a `.env` file. You can use the `.env.example` as a reference or rename it. Populate the name parameters needed.

Install the dependencies: `pip install python-dotenv yaml -U`.
(you can now also use `uv`)

Review the options with `--help`:

```sh
python ./postgres_setup.py --help                                                                                                                    ─╯
usage: postgres_setup.py [-h] [--generate] [--container-name CONTAINER_NAME] [--port PORT] [--volume VOLUME] [--remove-volume] [--platform PLATFORM]
                         [--config CONFIG]
                         [{start,remove,build,generate,verify,test,full-setup}]

PostgreSQL Docker container management with extensions

positional arguments:
  {start,remove,build,generate,verify,test,full-setup}
                        Command to execute

options:
  -h, --help            show this help message and exit
  --generate            Generate Dockerfile from config without other actions
  --container-name CONTAINER_NAME
                        Name for the Docker container (default: postgres-extensions)
  --port PORT           Port to expose PostgreSQL (default: from .env or 5432)
  --volume VOLUME       Volume name (default: from .env or postgres-extensions-data)
  --remove-volume       Remove volume when removing container
  --platform PLATFORM   Platform for Docker build (default: auto-detected)
  --config CONFIG       Configuration file to use (default: postgres-extensions.yaml)

Examples:
  postgres_setup.py start                    Start a new container with default settings
  postgres_setup.py remove --remove-volume   Remove container and its volume
  postgres_setup.py build                    Build the Docker image
  postgres_setup.py generate                 Generate Dockerfile from config
  postgres_setup.py verify                   Verify extension installation
  postgres_setup.py test                     Run extension tests
  postgres_setup.py full-setup               Build image and start container
```

Everything should be self-explanatory. The `PostgresWithExtensions.dockerfile` is automatically generated on `generate`, `build` and `full-setup`. 

### Potential Future
You may notice that we have `postgres-extensions.yaml` that attempts to capture the unique requirements to generate the Dockerfile and build the container. This is the first inroad to create a fully generic model where you can specify the extension and their build parameters in the config file. At the moment, however, there are still many internals in the generator class that are unique to these 3 extensions, but if there is interest in this model, we can continue to iterate towards a fully generic solution.

### Other Options
[Database.dev](https://database.dev/) has a flow blown extension installation system, but it doesn't quite fit what I needed, and not all extensions are there. However, they're a more comprehensive option if someone needs that.

### Contributing
Open to PRs if you think a feature should be added or you find any bugs.