# ---- builder: install dependencies into venv ----
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- caddy: source static binary ----
FROM caddy:2.10.2-alpine AS caddy

# ---- final: runtime ----
FROM python:3.12-slim

ARG IMAGE_VERSION=1.0.0-1
LABEL org.opencontainers.image.source="https://github.com/carsaig/homelab" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin traefikmcp

COPY --from=builder /opt/venv /opt/venv
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

WORKDIR /app
COPY src/ ./src/
COPY Caddyfile /etc/caddy/Caddyfile
COPY mcp-proxy-config.json /etc/mcp-proxy/config.json
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && chown -R traefikmcp:traefikmcp /app

USER traefikmcp
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
