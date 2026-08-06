# Qdrant

**What it is:** A self-hosted vector database used for semantic search, memory,
and retrieval-augmented AI workflows.

**Business value:** It keeps embedding-based retrieval under direct operational
control while supporting reusable AI services instead of isolated point solutions.

## Engineering Highlights

- Pinned upstream artifacts for predictable upgrades and rollback.
- Persistent storage with explicit health monitoring.
- Authenticated, non-public service boundary.
- Shared-service design that avoids duplicating vector infrastructure.
- Runtime secret injection with no production values in Git.
- Compatibility controls for embedding dimensions and collection schemas.

## Configuration Contract

The Compose definition exposes environment-variable contracts and portable
defaults only. Deployment coordinates and operational runbooks remain private.
