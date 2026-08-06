FROM python:3.11-slim@sha256:94c50be2dc994b873b55bc123e95e6dbade08095b3dfd790f51c34de3f08cbb7

RUN useradd --create-home --uid 10001 mcp \
    && mkdir -p /home/mcp/.cache \
    && chown -R mcp:mcp /home/mcp \
    && python -m pip install --no-cache-dir mcp-server-qdrant==0.8.1

USER 10001
WORKDIR /home/mcp

EXPOSE 8000

ENTRYPOINT ["python", "-c", "from mcp_server_qdrant.server import mcp; mcp.run(transport='streamable-http', host='0.0.0.0', port=8000)"]
