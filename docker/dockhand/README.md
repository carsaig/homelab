# Dockhand

Docker/CI-CD management UI. Host: `pi` (Raspberry Pi 5).

- **Local access**: `http://<host-tailscale-ip>:3000` or the Tailscale Service (`docktail`, see below)
- **Public-domain access**: `https://dockhand.certain.cc` — tailnet-only via NextDNS rewrite → a reverse proxy on the `proxy` host, real HTTPS, no public exposure. See the `pi` host's own infrastructure docs for the full pattern; not specific to this app.

## Gotchas

- **postgres:18-alpine volume path**: as of major version 18, the official Postgres image expects the volume mounted at `/var/lib/postgresql` (no `/data` suffix) — the 16-and-earlier convention (`/var/lib/postgresql/data`) makes the image refuse to start. Compose here already reflects the fix.
- **docktail doesn't run `tailscale serve` itself**, despite its docs implying full automation. It only creates the Tailscale Service *definition* via the OAuth API — the local proxy target has to be set manually on the host:
  ```bash
  sudo tailscale serve --service=svc:dockhand --bg http://<dockhand-container-ip>:3000
  ```
  That command hardcodes the container's current Docker bridge IP, which can change on recreation (image update, `docker compose down/up`, host reboot) — check `docker inspect dockhand-dockhand-1 --format '{{.NetworkSettings.Networks.dockhand_default.IPAddress}}'` and re-run if the Tailscale Service stops resolving.
- **Requires the host to carry `tag:docktail-host`** (Tailscale ACL) — not `tag:server`. A broad `tag:server ↔ tag:server` grant was found to break LAN-local peer connectivity on this specific host; docktail hosts use a narrower, dedicated tag instead.

## API / integration docs

Reference: https://finsys-dockhand.mintlify.app/api/overview

- **Base URL**: `http(s)://<dockhand-host>:3000/api`
- **Auth**: session-cookie based — `POST /api/auth/login` to obtain a session, no API-key/bearer-token mechanism documented
- **Capability areas**: core Docker ops (containers/images/networks/volumes/stacks), management (environments/users/roles/settings), **Git integration** (repositories, Git-based stack deployment, webhooks), monitoring (events/stats/health/audit logs), and Server-Sent Events for streaming responses
- **Git-source stacks**: confirmed supported via the API ("Deploy stacks from Git with automatic sync", webhook-driven auto-deploy) — this is the path to fix the current "can't find the stack file" issue (see Gotchas above): redeploy dockhand itself *from* this `homelab` repo instead of a local compose file, so it manages its own stack definition natively going forward.
