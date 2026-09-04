# Traefik MCP Server

All-in-one Model Context Protocol (MCP) server for inspecting and querying Traefik reverse proxy routing, services, and middlewares. Packaged with an internal `mcp-proxy` bridge and Bearer-authenticated Caddy edge on port 8080.

## Architecture

- **Runtime**: Python 3.12 with `mcp` SDK and `mcp-proxy`.
- **Auth**: Embedded Caddy verifying `Authorization: Bearer <MCP_PROXY_BEARER_TOKEN>`.
- **Target**: Traefik REST API (`TRAEFIK_API_URL`).

## Environment Variables

| Variable | Description | Example | Default |
|---|---|---|---|
| `TRAEFIK_API_URL` | Base URL to Traefik API | `http://traefik:8080` | `http://traefik:8080` |
| `MCP_PROXY_BEARER_TOKEN` | Bearer token for client authentication | `your-secure-token` | *Required* |
| `MCP_PROXY_PORTS` | Host port binding | `127.0.0.1:8080:8080` | `8080:8080` |
| `TRAEFIK_BASIC_AUTH_USERNAME` | Optional basic auth username for Traefik API | `admin` | None |
| `TRAEFIK_BASIC_AUTH_PASSWORD` | Optional basic auth password for Traefik API | `secret` | None |
