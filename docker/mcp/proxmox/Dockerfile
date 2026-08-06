# ---- builder: install ProxmoxMCP-Plus into an isolated venv (discarded) ------
# TODO: digest-pin (FROM python:3.11-slim@sha256:...) like docker/karakeep-mcp.
FROM python:3.11-slim AS builder

# Pin the upstream RELEASE tag — bump when ProxmoxMCP-Plus cuts a new release.
# The image tag (IMAGE_VERSION below) mirrors this so upstream currency is obvious.
ARG PROXMOXMCP_REF=v0.5.10

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
       "git+https://github.com/RekklesNA/ProxmoxMCP-Plus.git@${PROXMOXMCP_REF}"

# ---- caddy: source the static binary from the official image ------------------
# TODO: digest-pin.
FROM caddy:2.8-alpine AS caddy

# ---- final: slim runtime, no build tools, non-root ---------------------------
# TODO: digest-pin.
FROM python:3.11-slim

# Image tag = <upstream-version>-<image-rev>. Base mirrors PROXMOXMCP_REF (drop the
# 'v'); bump -N for image-only changes (entrypoint/Caddy), reset to -1 on upstream bump.
ARG IMAGE_VERSION=0.5.10-1
LABEL org.opencontainers.image.version="${IMAGE_VERSION}"

RUN apt-get update && apt-get install -y --no-install-recommends curl openssl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin proxmoxmcp

COPY --from=builder /opt/venv /opt/venv
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
ENV PATH="/opt/venv/bin:$PATH"

COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/proxmox-config \
    && chown -R proxmoxmcp:proxmoxmcp /app

USER proxmoxmcp
WORKDIR /app
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
