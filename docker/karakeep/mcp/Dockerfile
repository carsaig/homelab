# ---- builder: install the npm package in isolation; this stage is discarded ----
# Digest-pinned (not just tag-pinned) — a tag can technically be moved by the
# upstream maintainer, the digest can't. Re-pin if intentionally bumping node.
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS builder

# Bump this single line to upgrade — the build workflow reads it to tag the
# published image, so the Dockerfile stays the one source of truth for version.
ARG KARAKEEP_MCP_VERSION=0.33.0

RUN npm install -g --omit=dev --no-audit --no-fund @karakeep/mcp@${KARAKEEP_MCP_VERSION}

# ---- final: mcp-proxy + caddy + only the node runtime (no npm) + the built package ----
# Also digest-pinned; the v0.12.0 tag is kept in the comment for human reference.
FROM ghcr.io/sparfenyuk/mcp-proxy@sha256:ce037447191eeed517faa80640539dedaffb79a3ec107bfd23625a4438b0d06d
# = ghcr.io/sparfenyuk/mcp-proxy:v0.12.0

RUN apk add --no-cache nodejs caddy

COPY --from=builder /usr/local/lib/node_modules/@karakeep /usr/local/lib/node_modules/@karakeep
RUN ln -s /usr/local/lib/node_modules/@karakeep/mcp/dist/index.js /usr/local/bin/karakeep-mcp \
    && chmod +x /usr/local/lib/node_modules/@karakeep/mcp/dist/index.js

COPY mcp-proxy-config.json /etc/mcp-proxy/config.json
COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
