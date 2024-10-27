# Use PostgreSQL 16 specifically until the extensions support 17 or newer
FROM postgres:16

# amd64 and arm64 have been tested. Others may work but you need to verify
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-utils \
    build-essential \
    cmake \
    gnupg \
    git \
    curl \
    postgresql-server-dev-16 \
    flex \
    bison \
    libreadline-dev \
    zlib1g-dev \
    ca-certificates \
    jq \
    wget

RUN update-ca-certificates

# Install vector.rs
RUN LATEST_RELEASE=$(wget -qO - https://api.github.com/repos/tensorchord/pgvecto.rs/releases/latest) && \
    if [ "$TARGETARCH" = "arm64" ]; then \
        ARCH_PATTERN="arm64"; \
    else \
        ARCH_PATTERN="amd64"; \
    fi && \
    wget -q $(echo $LATEST_RELEASE | jq -r --arg ARCH "$ARCH_PATTERN" '.assets[] | select(.name | contains($ARCH)) | .browser_download_url') && \
    apt install -y --no-install-recommends ./vectors-pg16_*_${TARGETARCH}.deb && \
    rm -f vectors-pg16_*_${TARGETARCH}.deb

# Install Apache AGE extension 
RUN if [ -d "/age" ]; then rm -rf /age; fi && \
    git clone --depth 1 --branch PG16 https://github.com/apache/age.git /age && \
    cd /age && \
    make PG_CONFIG=/usr/bin/pg_config && \
    make install PG_CONFIG=/usr/bin/pg_config

# Install TimescaleDB extension (Apache-2 licensed version)
RUN if [ -d "/timescaledb" ]; then rm -rf /timescaledb; fi && \
    git clone https://github.com/timescale/timescaledb.git /timescaledb && \
    cd /timescaledb && \
    # Get latest release version from GitHub API
    LATEST_TAG=$(curl -s https://api.github.com/repos/timescale/timescaledb/releases/latest | jq -r .tag_name) && \
    git checkout ${LATEST_TAG} && \
    ./bootstrap -DPG_CONFIG=/usr/bin/pg_config -DAPACHE_ONLY=1 && \
    cd build && \
    make && \
    make install

# Clean up
RUN apt-get remove -y build-essential git curl gnupg cmake flex bison && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the default command to run when starting the container
CMD ["postgres"]