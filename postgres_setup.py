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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def build_image(dockerfile='PostgresWithExtensions.dockerfile', tag='postgres-extensions:latest', platform=None):
    """Build the Docker image using buildx."""
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
            '-f', dockerfile,
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
        for line in process.stdout:
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
  %(prog)s verify                   Verify extension installation
  %(prog)s test                     Run extension tests
  %(prog)s full-setup              Build image and start container
        """
    )
    
    parser.add_argument('command', choices=['start', 'remove', 'build', 'verify', 'test', 'full-setup'],
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
    
    parser.add_argument('--dockerfile', default='PostgresWithExtensions.dockerfile',
                      help='Dockerfile to use (default: PostgresWithExtensions.dockerfile)')
    
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
        if args.command == 'build':
            build_image(dockerfile=args.dockerfile, platform=args.platform)
            
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
            build_image(dockerfile=args.dockerfile, platform=args.platform)
            
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