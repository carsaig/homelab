# Dockhand

Docker/CI-CD management UI. Host: `pi` (Raspberry Pi 5).

- **Local access**: `http://<host-tailscale-ip>:3000` or the Tailscale Service (`docktail`, see below)
- **Public-domain access**: `https://dockhand.mydomain.com` — tailnet-only via NextDNS rewrite → a reverse proxy on the `proxy` host, real HTTPS, no public exposure. See the `pi` host's own infrastructure docs for the full pattern; not specific to this app.

## Gotchas

- **postgres:18-alpine volume path**: as of major version 18, the official Postgres image expects the volume mounted at `/var/lib/postgresql` (no `/data` suffix) — the 16-and-earlier convention (`/var/lib/postgresql/data`) makes the image refuse to start. Compose here already reflects the fix.
- **docktail doesn't run `tailscale serve` itself**, despite its docs implying full automation. It only creates the Tailscale Service *definition* via the OAuth API — the local proxy target has to be set manually on the host:
  ```bash
  sudo tailscale serve --service=svc:dockhand --bg http://<dockhand-container-ip>:3000
  ```
  That command hardcodes the container's current Docker bridge IP, which can change on recreation (image update, `docker compose down/up`, host reboot) — check `docker inspect dockhand-dockhand-1 --format '{{.NetworkSettings.Networks.dockhand_default.IPAddress}}'` and re-run if the Tailscale Service stops resolving.
- **Requires the host to carry `tag:docktail-host`** (Tailscale ACL) — not `tag:server`. A broad `tag:server ↔ tag:server` grant was found to break LAN-local peer connectivity on this specific host; docktail hosts use a narrower, dedicated tag instead.

## Secrets & deployment

Secrets resolve via 1Password references (`.env.op`), not a locally-created `.env` —
see the root [README](../../README.md#secrets--deployment) for the general mechanism.
For this app specifically:

- `POSTGRES_PASSWORD` → `op://SECRETS/Dockhand/add more/database-pw`
- `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_CLIENT_SECRET` → `op://SECRETS/Tailscale/Dockhand/client-id-oauth` / `client-secret-oauth` (docktail's own OAuth client, scoped to `Services:Write` + `Devices:Read/Write`, tagged `tag:docktail-service` — unrelated to the CI runner's own tailnet identity)
- Deploy target: `op://SECRETS/Dockhand/deploy-host` + `deploy-user`

## API / integration docs

Reference: https://finsys-dockhand.mintlify.app/api/overview

- **Base URL**: `http(s)://<dockhand-host>:3000/api`
- **Auth**: session-cookie based — `POST /api/auth/login` to obtain a session, no API-key/bearer-token mechanism documented
- **Capability areas**: core Docker ops (containers/images/networks/volumes/stacks), management (environments/users/roles/settings), **Git integration** (repositories, Git-based stack deployment, webhooks), monitoring (events/stats/health/audit logs), and Server-Sent Events for streaming responses
- **Git-source stacks**: Dockhand can also pull its own stack definitions directly from a Git repo with webhook-driven auto-deploy. That's a *different* deployment path from this repo's `deploy.yml` (push-based, secrets resolved externally) — Dockhand's native Git integration has no 1Password support, so it can't resolve `.env.op` itself. Worth revisiting once/if that gap closes; until then, `deploy.yml` is the supported path for this app.
