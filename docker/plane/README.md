# Plane

**What it is:** A self-hosted project and issue tracking system covering work
items, cycles, modules and documents for a small team.

**Business value:** It keeps planning data on infrastructure that is owned
outright rather than rented per seat, and removes the recurring cost and data
residency questions that come with a hosted tracker.

## Engineering Highlights

- **Explicitly pinned image tags.** All application images advance together
  through a single reviewed variable. A floating tag is not merely untidy here:
  the components share one database schema, so letting them drift apart is a
  correctness problem, not a cosmetic one.
- **Schema migration is a gated dependency.** The one-shot migration job is a
  declared prerequisite of every long-running application service via
  `service_completed_successfully`. The application cannot start against a
  schema that has not been brought forward, and a failed migration stops the
  rollout loudly instead of leaving services to idle.
- **Every process is observable.** All application and infrastructure services
  publish a health probe, including the background worker and the scheduler.
  A component that cannot report its own liveness will eventually fail in
  silence, and silence is indistinguishable from health.
- **Probes test the local process.** Health checks address the loopback
  interface rather than a service alias, so a probe result describes the
  container it runs in and cannot be confounded by name resolution.
- **Least privilege at runtime.** Services drop privilege escalation and run
  under an unprivileged account.
- **No credentials in source control.** Every secret and every host-specific
  value is supplied at deploy time; `.env.example` publishes the variable
  contract and nothing else.

## Operational Note

The self-healing restart of an unhealthy container is a containment measure,
not a repair. Where a service fails during startup rather than during
operation, restarting it reproduces the failure — so a persistent restart loop
should be read as a signal to inspect the startup path, not as a system
recovering.

## Configuration Contract

`.env.example` documents the required variable names, grouped by concern. Host
placement, addressing, ingress and recovery procedures are maintained
privately.
