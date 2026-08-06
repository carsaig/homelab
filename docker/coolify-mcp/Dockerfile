# Dedicated Coolify MCP server with an HTTP bridge and bearer-authenticated edge.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293

ARG COOLIFY_MCP_VERSION=2.19.3
ARG MCP_PROXY_VERSION=0.12.0
ARG MCP_SDK_VERSION=1.29.0
ARG IMAGE_REV=3

LABEL org.opencontainers.image.source="https://github.com/carsaig/homelab" \
      org.opencontainers.image.version="${COOLIFY_MCP_VERSION}-${IMAGE_REV}"

RUN apk add --no-cache python3 py3-pip libcap \
    && python3 -m venv /opt/mcp-proxy \
    && /opt/mcp-proxy/bin/pip install --no-cache-dir \
        "mcp==${MCP_SDK_VERSION}" \
        "mcp-proxy==${MCP_PROXY_VERSION}" \
    && addgroup -S app \
    && adduser -S -G app -h /home/app app

COPY --from=caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d /usr/bin/caddy /usr/bin/caddy
RUN setcap -r /usr/bin/caddy

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force

COPY Caddyfile /etc/caddy/Caddyfile
COPY mcp-proxy-config.json /etc/mcp-proxy/config.json
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && chown -R app:app /app /home/app

ENV HOME=/home/app \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CONFIG_HOME=/tmp/caddy-config \
    XDG_DATA_HOME=/tmp/caddy-data

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import socket; s=socket.create_connection(('127.0.0.1',8080),2); s.close()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
