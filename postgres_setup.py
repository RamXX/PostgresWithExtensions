import os
import time
import sys
import subprocess
import logging
import argparse
from dotenv import load_dotenv
import shlex
import re
import socket
import platform
import yaml
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DockerfileGenerator:
    def __init__(self, config_file: str):
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        self.validate_config()

    def validate_config(self):
        """Basic validation of the configuration file."""
        required_fields = ['version', 'postgres_version', 'base_image', 'extensions']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field: {field}")

    def generate_dockerfile(self) -> str:
        """Generate the Dockerfile content based on the configuration."""
        lines = []
        
        # Base image with comment
        lines.append("# Use PostgreSQL 16 specifically until the extensions support 17 or newer")
        lines.append(f"FROM {self.config['base_image']}")
        lines.append("")
        
        # Architecture argument
        lines.append("# amd64 and arm64 have been tested. Others may work but you need to verify")
        lines.append("ARG TARGETARCH")
        lines.append("")
        
        # Global dependencies
        if 'global_dependencies' in self.config:
            deps = self.config['global_dependencies']
            if 'apt' in deps:
                build_deps = deps['apt'].get('build', [])
                runtime_deps = deps['apt'].get('runtime', [])
                if build_deps or runtime_deps:
                    lines.extend(self._generate_apt_install(build_deps + runtime_deps))
                    lines.append("")

        # Update certificates if needed
        if 'ca-certificates' in self.config['global_dependencies']['apt'].get('runtime', []):
            lines.append("RUN update-ca-certificates")
            lines.append("")

        # Process each extension
        for ext_name, ext_config in self.config['extensions'].items():
            lines.extend(self._generate_installation(ext_name, ext_config))
            lines.append("")

        # Cleanup
        lines.extend(self._generate_cleanup())
        
        # CMD
        lines.append("# Set the default command to run when starting the container")
        lines.append('CMD ["postgres"]')
        
        return '\n'.join(lines)

    def _generate_apt_install(self, packages: List[str]) -> List[str]:
        """Generate apt-get install commands."""
        if not packages:
            return []
            
        return [
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "    " + " \\\n    ".join(sorted(packages))
        ]

    def _generate_installation(self, name: str, config: Dict) -> List[str]:
        """Generate installation commands for an extension."""
        lines = [f"# Install {name}"]
        
        if config['type'] == 'package':
            lines.extend(self._generate_package_installation(config))
        elif config['type'] == 'source':
            lines.extend(self._generate_source_installation(config))
        
        return lines

    def _generate_package_installation(self, config: Dict) -> List[str]:
        """Generate installation commands for a package-type extension."""
        pkg_config = config['package']
        if pkg_config['repository']['type'] == 'github':
            repo = pkg_config['repository']
            return [
                "RUN LATEST_RELEASE=$(wget -qO - "
                f"https://api.github.com/repos/{repo['owner']}/{repo['repo']}/releases/latest) && \\",
                "    if [ \"$TARGETARCH\" = \"arm64\" ]; then \\",
                f"        ARCH_PATTERN=\"{config['architecture_map']['arm64']}\"; \\",
                "    else \\",
                f"        ARCH_PATTERN=\"{config['architecture_map']['amd64']}\"; \\",
                "    fi && \\",
                "    wget -q $(echo $LATEST_RELEASE | jq -r --arg ARCH \"$ARCH_PATTERN\" '.assets[] | select(.name | contains($ARCH)) | .browser_download_url') && \\",
                f"    apt install -y --no-install-recommends ./{pkg_config['name']}_*_${{TARGETARCH}}.deb && \\",
                f"    rm -f {pkg_config['name']}_*_${{TARGETARCH}}.deb"
            ]
        else:
            return []

    def _generate_source_installation(self, config: Dict) -> List[str]:
        """Generate installation commands for a source-type extension."""
        src_config = config['source']
        build_config = config['build']
        lines = []
        
        if src_config['repository']['type'] == 'git':
            clone_cmd = "git clone"
            if 'depth' in src_config['repository']:
                clone_cmd += f" --depth {src_config['repository']['depth']}"
            if 'branch' in src_config['repository']:
                clone_cmd += f" --branch {src_config['repository']['branch']}"
            clone_cmd += f" {src_config['repository']['url']} {build_config['directory']}"
            
            # Handle AGE-specific commands
            if 'age' in build_config['directory']:
                lines.extend([
                    f"RUN if [ -d \"{build_config['directory']}\" ]; "
                    f"then rm -rf {build_config['directory']}; fi && \\",
                    f"    {clone_cmd} && \\",
                    f"    cd {build_config['directory']} && \\",
                    "    make PG_CONFIG=/usr/bin/pg_config && \\",
                    "    make install PG_CONFIG=/usr/bin/pg_config"
                ])
            
            # Handle TimescaleDB-specific commands
            elif 'timescaledb' in build_config['directory']:
                lines.extend([
                    f"RUN if [ -d \"{build_config['directory']}\" ]; "
                    f"then rm -rf {build_config['directory']}; fi && \\",
                    f"    {clone_cmd} && \\",
                    "    cd /timescaledb && \\",
                    "    LATEST_TAG=$(curl -s https://api.github.com/repos/timescale/timescaledb/releases/latest | jq -r .tag_name) && \\",
                    "    git checkout ${LATEST_TAG} && \\",
                    "    ./bootstrap -DPG_CONFIG=/usr/bin/pg_config -DAPACHE_ONLY=1 && \\",
                    "    cd build && \\",
                    "    make && \\",
                    "    make install"
                ])
        
        return lines

    def _generate_cleanup(self) -> List[str]:
        """Generate cleanup commands."""
        # Specific list of packages to remove, matching the original exactly
        cleanup_packages = [
            'apt-utils', 'bison', 'build-essential', 'cmake', 'curl', 'flex',
            'git', 'gnupg', 'libreadline-dev', 'postgresql-server-dev-16', 'zlib1g-dev'
        ]
        
        return [
            "# Clean up",
            "RUN apt-get remove -y " + " ".join(sorted(cleanup_packages)) + " && \\",
            "    apt-get autoremove -y && \\",
            "    apt-get clean && \\",
            "    rm -rf /var/lib/apt/lists/*",
            ""
        ]

    def get_postgres_config(self) -> Dict:
        """Extract PostgreSQL configuration from extensions."""
        config = {
            'shared_preload_libraries': [],
            'search_path': []
        }
        
        for ext_config in self.config['extensions'].values():
            if 'shared_preload_libraries' in ext_config:
                config['shared_preload_libraries'].extend(ext_config['shared_preload_libraries'])
            if 'search_path' in ext_config:
                config['search_path'].extend(ext_config['search_path'])
                
        return config
    
def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def run_command(command, check=True, shell=False):
    """Execute a shell command and return its output."""
    try:
        result = subprocess.run(command, check=check, shell=shell, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}")
        logging.error(f"Error output: {e.stderr}")
        raise

def is_container_running(container_name):
    """Check if a container is running."""
    try:
        output = run_command(['docker', 'container', 'inspect', '-f', '{{.State.Running}}', container_name])
        return output.lower() == 'true'
    except subprocess.CalledProcessError:
        return False

def does_volume_exist(volume_name):
    """Check if a Docker volume exists."""
    try:
        run_command(['docker', 'volume', 'inspect', volume_name])
        return True
    except subprocess.CalledProcessError:
        return False
    
def get_system_architecture():
    """Detect system architecture and return appropriate Docker platform. Others may work but you will have to experiment and modify."""
    machine = platform.machine().lower()
    if machine in ['arm64', 'aarch64']:
        return 'linux/arm64'
    elif machine in ['x86_64', 'amd64']:
        return 'linux/amd64'
    else:
        raise Exception(f"Unsupported architecture: {machine}")

def get_container_volume(container_name):
    """Get volume name associated with a container."""
    try:
        # Get volume mounts for the container
        inspect_cmd = ['docker', 'container', 'inspect', 
                      '-f', '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}', 
                      container_name]
        volume_name = run_command(inspect_cmd)
        return volume_name if volume_name else None
    except subprocess.CalledProcessError:
        return None
    
def cleanup_buildx():
    """Clean up all buildx resources."""
    try:
        # Get all builder instances
        builders = run_command(['docker', 'buildx', 'ls']).split('\n')
        for builder in builders:
            if 'pg-extensions-builder' in builder:
                # Remove the builder
                run_command(['docker', 'buildx', 'rm', 'pg-extensions-builder'], check=False)
        
        # Find and remove any lingering buildkit containers
        containers = run_command(['docker', 'ps', '-a', '--filter', 'name=buildx_buildkit_pg-extensions-builder', '--format', '{{.Names}}']).split('\n')
        for container in containers:
            if container:  # Skip empty strings
                run_command(['docker', 'rm', '-f', container], check=False)
    except Exception as e:
        logging.warning(f"Error during buildx cleanup: {e}")


def build_image(config_file='postgres-extensions.yaml', tag='postgres-extensions:latest', platform=None):
    """Build the Docker image using buildx."""
    # Generate Dockerfile content
    generator = DockerfileGenerator(config_file)
    dockerfile_content = generator.generate_dockerfile()
    
    # Write to temporary Dockerfile
    dockerfile_path = 'PostgresWithExtensions.dockerfile'
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)

    if platform is None:
        platform = get_system_architecture()
    
    logging.info(f"Building Docker image for platform {platform}...")
    
    # Clean up any existing builder first
    cleanup_buildx()
    
    # Create new builder
    builder_name = 'pg-extensions-builder'
    logging.info("Creating new builder instance...")
    run_command(['docker', 'buildx', 'create', '--name', builder_name, '--use'])
    
    try:
        # Build the image with verbose output
        build_cmd = [
            'docker', 'buildx', 'build',
            '-f', dockerfile_path,  # Use the generated dockerfile path
            '--platform', platform,
            '-t', tag,
            '.',
            '--load',
            '--progress=plain'  # Enable verbose output
        ]
        
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            build_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Stream the output
        for line in process.stdout: # type: ignore
            print(line, end='')
        
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, build_cmd)
            
        logging.info("Image built successfully")
    finally:
        # Clean up all buildx resources
        logging.info("Cleaning up builder...")
        cleanup_buildx()


def get_postgres_version(container_name='postgres'):
    """Get PostgreSQL major version number from the container."""
    try:
        version_output = run_command(
            ['docker', 'exec', container_name, 'psql', '--version']
        )
        # Parse version string (e.g., "psql (PostgreSQL) 16.1" or "psql (PostgreSQL) 17.0")
        match = re.search(r'(\d+)\.', version_output)
        if match:
            major_version = match.group(1)
            logging.info(f"Detected PostgreSQL version: {major_version}")
            return major_version
        else:
            raise ValueError("Could not parse PostgreSQL version")
    except Exception as e:
        logging.error(f"Failed to detect PostgreSQL version: {e}")
        raise

def wait_for_postgres(container_name='postgres-extensions', max_attempts=30, delay=2):
    """Wait for PostgreSQL to become ready."""
    logging.info("Waiting for PostgreSQL to be ready...")
    for attempt in range(max_attempts):
        try:
            run_command(['docker', 'exec', container_name, 'pg_isready', '-U', 'postgres'])
            logging.info("PostgreSQL is ready.")
            return True
        except subprocess.CalledProcessError:
            logging.info(f"PostgreSQL is not ready yet. Attempt {attempt + 1}/{max_attempts}")
            time.sleep(delay)
    logging.error("PostgreSQL failed to become ready in time.")
    return False

def remove_container(container_name='postgres-extensions', remove_volume=False):
    """Remove existing container and optionally its volume."""
    container_exists = False
    volume_name = None
    
    try:
        run_command(['docker', 'container', 'inspect', container_name])
        container_exists = True
        if remove_volume:
            # Get the volume name from the container before removing it
            volume_name = get_container_volume(container_name)
    except subprocess.CalledProcessError:
        pass

    if container_exists:
        logging.info(f"Removing container {container_name}...")
        run_command(['docker', 'rm', '-f', container_name], check=False)
    else:
        logging.info(f"Container {container_name} does not exist. Nothing to remove.")
    
    if remove_volume and volume_name:
        if does_volume_exist(volume_name):
            logging.info(f"Removing volume {volume_name}...")
            run_command(['docker', 'volume', 'rm', '-f', volume_name], check=False)
        else:
            logging.info(f"Volume {volume_name} does not exist. Nothing to remove.")



def start_postgres_container(
    container_name='postgres-extensions',
    image='postgres-extensions:latest',
    port=None,
    password=None,
    volume_name=None
):
    """Start the PostgreSQL container with the specified configuration."""
    if password is None:
        password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    
    if port is None:
        port = os.getenv('POSTGRES_PORT', '5432')
        
    if volume_name is None:
        volume_name = os.getenv('POSTGRES_VOLUME', 'postgres-extensions-data')
    
    # Check if port is in use
    if is_port_in_use(int(port)):
        raise Exception(
            f"Port {port} is already in use. This might be another PostgreSQL instance.\n"
            f"Please either:\n"
            f"1. Stop the other PostgreSQL instance\n"
            f"2. Set a different port in your .env file (POSTGRES_PORT=<port>)"
        )

    logging.info(f"Starting PostgreSQL container using image {image}...")
    cmd = [
        'docker', 'run', '--name', container_name,
        '-e', f"POSTGRES_PASSWORD={password}",
        '-p', f"{port}:5432",
        '-v', f"{volume_name}:/var/lib/postgresql/data",
        '-d', image
    ]
    
    run_command(cmd)
    return wait_for_postgres(container_name)

def configure_extensions(container_name='postgres'):
    """Configure AGE and other extensions in PostgreSQL."""
    logging.info("Configuring PostgreSQL extensions...")
    
    # Get PostgreSQL version
    pg_version = get_postgres_version(container_name)
    pg_lib_path = f"/usr/lib/postgresql/{pg_version}/lib"
    
    # Configure AGE plugin directory
    logging.info(f"Setting up AGE plugin directory for PostgreSQL {pg_version}...")
    run_command(['docker', 'exec', container_name, 'bash', '-c',
                f"mkdir -p {pg_lib_path}/plugins && "
                f"ln -s {pg_lib_path}/age.so {pg_lib_path}/plugins/age.so"])

    # Configure shared_preload_libraries
    logging.info("Configuring shared_preload_libraries...")
    run_command(['docker', 'exec', container_name, 'bash', '-c',
                "echo \"shared_preload_libraries = 'age,timescaledb,vectors'\" >> "
                "/var/lib/postgresql/data/postgresql.conf"])
    run_command([
                'docker', 'exec', container_name, 'bash', '-c',
                'echo "search_path = \'ag_catalog, \\"$user\\", public, vectors\'" >> '
                '/var/lib/postgresql/data/postgresql.conf'
            ])

    # Restart PostgreSQL container
    logging.info("Restarting PostgreSQL container...")
    run_command(['docker', 'restart', container_name])

    # Wait for PostgreSQL to be ready again
    return wait_for_postgres()

def verify_extensions(container_name='postgres-extensions', dbname='postgres', user='postgres'):
    """Verify that all required extensions are installed and available."""
    if not is_container_running(container_name):
        logging.error(f"Container {container_name} is not running. Please start it first.")
        return False
        
    logging.info("Verifying extensions...")
    verify_command = """
    SELECT extname, extversion 
    FROM pg_extension 
    WHERE extname IN ('age', 'vectors', 'timescaledb');
    """
    psql_command = f"docker exec -i {container_name} psql -U {user} -d {dbname} -c {shlex.quote(verify_command)}"
    result = run_command(psql_command, shell=True)
    logging.info(f"Installed extensions:\n{result}")
    return result

def test_vectors_extension(container_name='postgres-extensions', dbname='postgres', user='postgres'):
    """Test vectors extension step by step."""
    logging.info("Testing vectors extension...")
    
    steps = [
        ("DROP TABLE IF EXISTS items;", "Cleaning up any existing items table"),
        ("CREATE TABLE items (embedding vector(3));", "Creating items table"),
        ("INSERT INTO items (embedding) SELECT ARRAY[random(), random(), random()]::real[] FROM generate_series(1, 10);", 
         "Inserting test data"),
        ("CREATE INDEX ON items USING vectors (embedding vector_l2_ops);", "Creating vector index"),
        ("SELECT * FROM items ORDER BY embedding <-> '[3,2,1]' LIMIT 5;", "Testing KNN query"),
        ("DROP TABLE items;", "Cleaning up items table")
    ]
    
    for sql, description in steps:
        execute_sql(container_name, dbname, user, sql, description)
    
    logging.info("Vectors extension test completed successfully")

def test_extensions(container_name='postgres-extensions', dbname='postgres', user='postgres'):
    """Test each extension to ensure it's working properly."""
    if not is_container_running(container_name):
        logging.error(f"Container {container_name} is not running. Please start it first.")
        return False
        
    logging.info("Testing extensions functionality...")
    
    # Test AGE
    logging.info("Testing age...")
    age_test = """
    SELECT * FROM ag_catalog.create_graph('test_graph');
    SELECT * FROM ag_catalog.drop_graph('test_graph', true);
    """
    execute_sql(container_name, dbname, user, age_test, "AGE graph creation and deletion")
    logging.info("age test passed successfully")

    # Test TimescaleDB
    logging.info("Testing timescaledb...")
    timescale_test = """
    CREATE TABLE test_table(time TIMESTAMPTZ NOT NULL, value DOUBLE PRECISION);
    SELECT create_hypertable('test_table', 'time');
    DROP TABLE test_table;
    """
    execute_sql(container_name, dbname, user, timescale_test, "TimescaleDB hypertable creation")
    logging.info("timescaledb test passed successfully")

    # Test Vectors
    test_vectors_extension(container_name, dbname, user)

def execute_sql(container_name, dbname, user, sql, description=None):
    """Execute SQL command and log the result."""
    if description:
        logging.info(f"Executing: {description}")
    
    psql_command = f"docker exec -i {container_name} psql -U {user} -d {dbname} -c {shlex.quote(sql)}"
    try:
        result = run_command(psql_command, shell=True)
        if description:
            logging.info(f"Success: {description}")
        return result
    except subprocess.CalledProcessError as e:
        if description:
            logging.error(f"Failed: {description}")
        logging.error(f"Error output: {e.stderr}")
        raise

def create_extensions(container_name='postgres-extensions', dbname='postgres', user='postgres'):
    """Create all required extensions in the database."""
    logging.info("Creating extensions...")
    
    # First, drop and recreate vectors extension
    steps = [
        ("DROP EXTENSION IF EXISTS vectors;", "Dropping vectors extension if exists"),
        ("CREATE EXTENSION vectors;", "Creating vectors extension"),
        ("LOAD 'vectors';", "Loading vectors"),
        ("CREATE EXTENSION IF NOT EXISTS age;", "Creating age extension"),
        ("LOAD 'age';", "Loading age"),
        ("CREATE EXTENSION IF NOT EXISTS timescaledb;", "Creating timescaledb extension"),
        ("SET search_path = ag_catalog, \"$user\", public, vectors;", "Setting search path")
    ]
    
    for sql, description in steps:
        execute_sql(container_name, dbname, user, sql, description)
    
    logging.info("All extensions created successfully")

def setup_argparse():
    """Set up argument parsing for the script."""
    parser = argparse.ArgumentParser(
        description='PostgreSQL Docker container management with extensions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start                    Start a new container with default settings
  %(prog)s remove --remove-volume   Remove container and its volume
  %(prog)s build                    Build the Docker image
  %(prog)s generate                 Generate Dockerfile from config
  %(prog)s verify                   Verify extension installation
  %(prog)s test                     Run extension tests
  %(prog)s full-setup              Build image and start container
        """
    )
    
    # Add generate as both an option and a command
    parser.add_argument('--generate', action='store_true',
                      help='Generate Dockerfile from config without other actions')
    
    parser.add_argument('command', nargs='?',  # Make command optional
                      choices=['start', 'remove', 'build', 'generate', 'verify', 'test', 'full-setup'],
                      help='Command to execute')
    
    parser.add_argument('--container-name', default='postgres-extensions',
                      help='Name for the Docker container (default: postgres-extensions)')
    
    parser.add_argument('--port', type=int,
                      help='Port to expose PostgreSQL (default: from .env or 5432)')
    
    parser.add_argument('--volume', help='Volume name (default: from .env or postgres-extensions-data)')
    
    parser.add_argument('--remove-volume', action='store_true',
                      help='Remove volume when removing container')
    
    parser.add_argument('--platform',
                      help='Platform for Docker build (default: auto-detected)')
    
    parser.add_argument('--config', default='postgres-extensions.yaml',
                      help='Configuration file to use (default: postgres-extensions.yaml)')
    
    return parser


def main():
    # Load environment variables if .env file exists
    
    if os.path.exists('.env'):
        load_dotenv()
    else:
        logging.warning("No .env file found. Using default values.")

    parser = setup_argparse()
    args = parser.parse_args()

    try:
        if args.generate or args.command == 'generate':
            generator = DockerfileGenerator(args.config)
            dockerfile_content = generator.generate_dockerfile()
            with open('PostgresWithExtensions.dockerfile', 'w') as f:
                f.write(dockerfile_content)
            logging.info("Dockerfile generated successfully")
            return

        # Ensure command is provided for other operations
        if not args.command:
            parser.error("Command is required unless --generate is specified")

        if args.command == 'build':
            build_image(config_file=args.config, platform=args.platform)
            
        elif args.command == 'remove':
            remove_container(args.container_name, args.remove_volume)
            
        elif args.command == 'verify':
            verify_extensions(args.container_name)
            
        elif args.command == 'test':
            test_extensions(args.container_name)
            
        elif args.command == 'start':
            port = args.port or os.getenv('POSTGRES_PORT', '5432')
            volume = args.volume or os.getenv('POSTGRES_VOLUME', 'postgres-extensions-data')
            
            remove_container(args.container_name)
            if start_postgres_container(container_name=args.container_name, port=port, volume_name=volume):
                if configure_extensions(args.container_name):
                    time.sleep(2)
                    create_extensions(args.container_name)
                    verify_extensions(args.container_name)
                    test_extensions(args.container_name)
                    logging.info("PostgreSQL container setup completed successfully.")
                else:
                    raise Exception("Failed to configure extensions")
            else:
                raise Exception("Failed to start PostgreSQL container")
                
        elif args.command == 'full-setup':
            # Build image first
            build_image(config_file=args.config, platform=args.platform)
            
            # Then start container
            port = args.port or os.getenv('POSTGRES_PORT', '5432')
            volume = args.volume or os.getenv('POSTGRES_VOLUME', 'postgres-extensions-data')
            
            remove_container(args.container_name)
            if start_postgres_container(container_name=args.container_name, port=port, volume_name=volume):
                if configure_extensions(args.container_name):
                    time.sleep(2)
                    create_extensions(args.container_name)
                    verify_extensions(args.container_name)
                    test_extensions(args.container_name)
                    logging.info("Full setup completed successfully.")
                else:
                    raise Exception("Failed to configure extensions")
            else:
                raise Exception("Failed to start PostgreSQL container")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()