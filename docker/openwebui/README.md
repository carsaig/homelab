# Open WebUI Production Stack

Open WebUI stack for host Frankfurt (`ai.certain.cc`) with PostgreSQL 16 persistence, Multi-SSO authentication, OmniRoute LLM gateway, Bifrost MCP integration, and SearXNG web search.

## Features
- **Database**: PostgreSQL 16
- **SSO**: Tailscale IDP (OIDC), Google, GitHub, Microsoft Azure Entra ID
- **Ingress**: Traefik (Dokploy) with automatic Let's Encrypt TLS on `ai.certain.cc`
- **Inference**: OmniRoute LLM Gateway
- **MCP**: Bifrost MCP Gateway
- **Search**: SearXNG Integration
- **Policy**: `DEFAULT_USER_ROLE=pending` for manual admin verification of public signups
