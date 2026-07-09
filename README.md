# homelab

Docker Compose stacks for my self-hosted homelab. One folder per application under `docker/`, host-agnostic — which physical host runs what is tracked here in this table, not in the folder path, so a folder never has to move if an app changes host.

## Solutions used on the stack
Secrets Management: 1Password
Docker Management: Dockhand
Uptime Monitoring: Uptime Kuma
Application Monitoring: Grafana
IaC: Terraform
CI/CD: Github, hosting my own runners


## Apps

| App | Host | Access | Notes |
|-----|------|--------|-------|
| [dockhand](docker/dockhand) | pi | `dockhand.mydomain.com` (tailnet-only), `dockhand.tailscale-domain.ts.net` | Docker/CI-CD management UI |

## Structure

```
docker/
  <app-name>/
    docker-compose.yml
    .env.op             # op:// references only — resolved to real values at deploy time
    .env.example        # variable names only, for manual/local runs — never real values
    README.md           # only when the app has non-obvious setup/quirks
```

## Secrets & deployment

Real secret values never live in this repo or on the machine that clones it — only
`op://` references (`.env.op`) and `${VAR}` placeholders (`docker-compose.yml`). This
makes every app folder deployable from any machine, not just the one where a local
`.env` happened to be created by hand.

Deploying an app runs through [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)
(manual trigger, pick the app): it resolves `.env.op` via the 1Password CLI, joins the
tailnet as an ephemeral node, and pushes the compose file + resolved `.env` to the
target host over SSH. The target host and SSH user for each app are themselves stored
as 1Password fields (`deploy-host`, `deploy-user`) rather than in this file, since a
tailnet address is infrastructure-identifying information this public repo shouldn't
carry.

`.env.example` still exists per app for anyone who wants to run a stack manually
without the workflow — fill it in locally, never commit it (gitignored).
