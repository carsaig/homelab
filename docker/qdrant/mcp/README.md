# Qdrant MCP

Bearer-protected semantic-memory tools backed by a dedicated Qdrant collection.

The MCP process is isolated from public ingress and shares only the deployment
network required to reach Qdrant. Its embedding cache persists independently of
the vector database.

All deployment coordinates and credentials are required environment variables.
