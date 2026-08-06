# Architecture overview

This repository demonstrates a Git-driven platform for self-hosted applications
and AI services. Workloads are independently deployable, configuration is
externalized, and sensitive operational details are deliberately excluded.

## Design principles

- **Independent services** — applications can be upgraded and rolled back without coupling unrelated workloads.
- **Declarative delivery** — reviewed Compose definitions provide repeatable deployments across heterogeneous hosts.
- **Defense in depth** — authenticated gateways, private service boundaries, and least-privilege identities reduce exposure.
- **Secretless source** — repositories contain variable contracts, never production values.
- **Operational resilience** — health checks, pinned artifacts, rollback paths, and monitoring are treated as product features.
- **AI-ready operations** — consistent structure and concise documentation help engineers and automated agents reason about changes safely.

Detailed topology, routing, host inventories, and operational runbooks are maintained privately.
