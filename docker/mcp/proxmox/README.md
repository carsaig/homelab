# Proxmox MCP

**What it is:** A Model Context Protocol integration for controlled AI-assisted
virtualization operations.

**Business value:** It makes repetitive infrastructure workflows easier to
automate while preserving approval, identity, and least-privilege boundaries.

## Engineering Highlights

- Automated native-architecture builds with pinned source revisions.
- Slim, non-root runtime image.
- Dedicated least-privilege service identity.
- Authenticated access with higher-risk capabilities disabled by default.
- Runtime-rendered configuration with secrets kept outside Git.
- Independent deployment and rollback lifecycle.

## Configuration Contract

`.env.example` describes variable contracts without production values. Access
policies, endpoint details, and operational procedures are private.
