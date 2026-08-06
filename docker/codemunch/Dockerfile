# Token-efficient code-intelligence MCP server.
#
# Debian (glibc) base ON PURPOSE: onnxruntime — the local semantic-embedding
# backend — ships manylinux (glibc) wheels only, no musl. Multi-stage: a builder
# installs + strips + prunes, the final stage copies only the lean result.
#
# Two stdio MCP servers run behind one mcp-proxy + Caddy bearer gate:
#   codemunch       = codemunch_gateway.py (merged surface, the ONLY one exposed)
#   codemunch-core  = jcodemunch-mcp serve (kept warm, reached over loopback)

# ── builder: install, bake model, strip, prune — all discarded ──────────────
# Digest-pinned (not just tag) — a tag can be moved upstream, a digest can't.
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS builder

# Bump this one line to upgrade codemunch — the build workflow greps it to tag
# the published image, so the Dockerfile stays authoritative for the version.
ARG JCODEMUNCH_VERSION=1.108.193
ARG MCP_PROXY_VERSION=0.12.0
# Wrapper revision — bump when codemunch_gateway.py / plumbing changes but the
# codemunch version doesn't. The image tag is <JCODEMUNCH_VERSION>-r<CODEMUNCH_REV>
# so Coolify (which won't re-pull an unchanged tag) always sees a new tag.
ARG CODEMUNCH_REV=6

# binutils = strip (removes debug symbols from native .so — behaviour-neutral).
RUN apt-get update && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

# Install into a relocatable prefix so the final stage can copy just this tree.
# [local-embed] pulls onnxruntime; with the baked model below, _detect_provider()
# auto-selects the local encoder — no API key, offline.
# [local-embed] = onnxruntime local encoder (default); [openai] = the openai SDK
# so embeddings can optionally be routed to an OpenAI-compatible endpoint
# (e.g. Bifrost) — MUCH faster than the 2-thread local encoder for big repos.
# Which one runs is chosen at runtime by env (see the compose OPENAI_* vars).
RUN pip install --no-cache-dir --prefix=/install \
        "jcodemunch-mcp[local-embed,openai]==${JCODEMUNCH_VERSION}" \
        "mcp-proxy==${MCP_PROXY_VERSION}"

# Bake the ONNX model OUTSIDE /data (the runtime volume would hide it; clear_repo
# wipes /data/code-index and would delete it). /opt survives every clear.
RUN PYTHONPATH=/install/lib/python3.12/site-packages python -c \
    "from pathlib import Path; \
from jcodemunch_mcp.embeddings.local_encoder import download_model; \
download_model(Path('/opt/models/all-MiniLM-L6-v2'))"

# Slim the installed tree (all behaviour-neutral): strip native libs, drop
# bytecode caches + test suites + the package manager (unused at runtime).
RUN set -eux; \
    find /install -name "*.so*" -type f -exec strip --strip-unneeded {} + 2>/dev/null || true; \
    find /install -depth -type d -name __pycache__ -exec rm -rf {} +; \
    find /install -depth -type d -name tests -exec rm -rf {} +; \
    rm -rf /install/lib/python3.12/site-packages/pip \
           /install/lib/python3.12/site-packages/pip-* \
           /install/lib/python3.12/site-packages/setuptools* \
           /install/lib/python3.12/site-packages/wheel* \
           /install/bin/pip*

# ── final: clean runtime, only the lean tree + git + caddy ──────────────────
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

# Static Caddy binary from the official image (Go static build → runs on debian).
COPY --from=caddy:2-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648 /usr/bin/caddy /usr/bin/caddy

# git stays at RUNTIME (the gateway clones with it). No build toolchain — every
# dependency ships prebuilt aarch64 wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The stripped/pruned Python tree and the baked model from the builder.
COPY --from=builder /install /usr/local
COPY --from=builder /opt/models /opt/models

# App files.
COPY codemunch_gateway.py /app/codemunch_gateway.py
COPY mcp-proxy-config.json /etc/mcp-proxy/config.json
COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Runtime config ───────────────────────────────────────────────────────────
# PYTHONDONTWRITEBYTECODE: we stripped __pycache__; don't let the runtime
# regenerate it into the writable layer.
ENV CODE_INDEX_PATH=/data/code-index \
    JCODEMUNCH_LOCAL_EMBED_MODEL=/opt/models/all-MiniLM-L6-v2 \
    JCODEMUNCH_TRUSTED_FOLDERS=/data/workspace \
    JCODEMUNCH_TRANSPORT=stdio \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# TCP-connect only: an HTTP GET would hit Caddy's 401 bearer gate and look
# unhealthy. A successful connect proves Caddy (and thus the stack) is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8080),2); s.close()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
