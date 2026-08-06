# Homelab platform engineering portfolio

This repository contains reviewed Docker Compose definitions and supporting
automation for a self-hosted application platform. It is intentionally written
as a public engineering portfolio: it explains the problems solved and the
practices applied without publishing operational topology or access details.

## What This Demonstrates

- **Platform engineering** — independently deployable services with consistent conventions.
- **DevOps and GitOps** — version-controlled infrastructure, automated builds, and repeatable releases.
- **MLOps foundations** — AI gateways, model integrations, retrieval systems, and workflow automation.
- **Security engineering** — runtime secret injection, least privilege, authenticated boundaries, and minimized exposure.
- **Reliability** — health checks, pinned artifacts, persistent-data planning, rollback paths, and observability.
- **Cost-aware architecture** — heterogeneous infrastructure selected according to workload requirements.

## Repository Principles

Each application is isolated in its own directory and can evolve without
forcing unrelated services to be rebuilt. Public files contain only portable
configuration contracts and safe defaults. Environment-specific values are
supplied by a secret manager or deployment platform.

The high-level design principles are summarized in
[docs/architecture.md](docs/architecture.md). Detailed topology, inventories,
routing, incident notes, and operational runbooks are maintained privately.

## Structure

```text
docker/
  <application>/
    docker-compose.yml
    .env.example
    README.md
```

Application READMEs are designed for three audiences:

- Recruiters and business stakeholders can understand the value delivered.
- Engineers can review the practices and trade-offs.
- Automated agents can identify stable configuration and deployment contracts.

## Security Policy

This public repository never intentionally contains production credentials,
infrastructure identifiers, network coordinates, deployment IDs, internal
routes, or operational security details. Real values are managed outside Git.
