# Arcane

**What it is:** A web interface for operating containerized applications across
one or more hosts, covering runtime state, image currency, and lifecycle actions.

**Business value:** It replaces ad-hoc shell access to production hosts with an
authenticated, auditable management surface, and makes image drift visible
instead of leaving it to be discovered during an incident.

## Engineering Highlights

- Declarative deployment definition held in version control, not on the host.
- Explicitly pinned image tag, so upgrades are reviewed changes rather than
  ambient drift.
- Management port bound to a private address only; a reverse proxy is the sole
  ingress path and the sole source of trusted forwarding headers.
- Runtime secret injection with no credentials committed to source control.
- Persistent operational state on a dedicated data volume.

## Configuration Contract

`.env.example` documents the required variable names. Values are supplied at
deploy time from a secret manager; host placement, addressing, and recovery
procedures are maintained privately.

## Upgrade Path

The in-app updater resolves its target from the running container's own image
reference. Because that reference is pinned, the updater will report success and
correctly make no change — the pinned tag is the source of truth. Version
changes are therefore made in this file and rolled out from the repository.
