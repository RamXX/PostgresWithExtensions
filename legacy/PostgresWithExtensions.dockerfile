# Use PostgreSQL 16 specifically until the extensions support 17 or newer
FROM postgres:16

# amd64 and arm64 have been tested. Others may work but you need to verify
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-utils \
    bison \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    flex \
    git \
    gnupg \
    jq \
    libreadline-dev \
    perl \
    postgresql-server-dev-16 \
    wget \
    zlib1g-dev

RUN update-ca-certificates

# Install vectors
RUN LATEST_RELEASE=$(curl -s https://api.github.com/repos/tensorchord/pgvecto.rs/releases/latest) && \
    if [ "${TARGETARCH}" = "arm64" ]; then \
        ARCH_PATTERN="arm64"; \
    else \
        ARCH_PATTERN="amd64"; \
    fi && \
    ASSET_URL=$(echo "$LATEST_RELEASE" | perl -0777 -pe 's/"body":\s*"(?:(?!\",)[\s\S])*?"\s*(,)?//gs' | jq -r --arg ARCH "$ARCH_PATTERN" '.assets[] | select(.name | contains("pg16") and contains($ARCH)) | .browser_download_url') && \
    curl -s -L -o vectors.deb "$ASSET_URL" && \
    apt install -y --no-install-recommends ./vectors.deb && \
    rm -f vectors.deb

# Install age
RUN if [ -d "/age" ]; then rm -rf /age; fi && \
    git clone --depth 1 --branch PG16 https://github.com/apache/age.git /age && \
    cd /age && \
    make PG_CONFIG=/usr/bin/pg_config && \
    make install PG_CONFIG=/usr/bin/pg_config

# Install timescaledb
RUN if [ -d "/timescaledb" ]; then rm -rf /timescaledb; fi && \
    git clone https://github.com/timescale/timescaledb.git /timescaledb && \
    cd /timescaledb && \
    LATEST_TAG=$(curl -s https://api.github.com/repos/timescale/timescaledb/releases/latest | jq -r .tag_name) && \
    git checkout ${LATEST_TAG} && \
    ./bootstrap -DPG_CONFIG=/usr/bin/pg_config -DAPACHE_ONLY=1 && \
    cd build && \
    make && \
    make install

# Clean up
RUN apt-get remove -y apt-utils bison build-essential cmake curl flex git gnupg libreadline-dev postgresql-server-dev-16 zlib1g-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the default command to run when starting the container
CMD ["postgres"]