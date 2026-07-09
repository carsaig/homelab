# homelab

Docker Compose stacks for my self-hosted homelab. One folder per application under `docker/`, host-agnostic — which physical host runs what is tracked here in this table, not in the folder path, so a folder never has to move if an app changes host.

## Apps

| App | Host | Access | Notes |
|-----|------|--------|-------|
| [dockhand](docker/dockhand) | pi | `dockhand.certain.cc` (tailnet-only), `dockhand.tortoise-bramble.ts.net` | Docker/CI-CD management UI |

## Structure

```
docker/
  <app-name>/
    docker-compose.yml
    .env.example       # variable names only, never real values
    README.md          # only when the app has non-obvious setup/quirks
```

## Secrets

Every `.env` file is gitignored. `.env.example` documents required variable *names* only — never commit real values, credentials, or IPs. This repo is public.
