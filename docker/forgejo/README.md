# Forgejo

**What it is:** A self-hosted Git forge providing repository hosting, code
review, issue tracking, and a CI system, operated as the primary home for
private source code.

**Business value:** It removes dependence on an external provider for private
work, keeps source code and its history under direct control, and provides a
continuous-integration surface on hardware chosen per workload rather than
per vendor availability.

## Engineering Highlights

- **Single canonical identity.** The service advertises one permanent base URL.
  Clone addresses, webhook targets, and identity-provider redirect URIs all
  derive from it, so reachability can change without rewriting application
  state or invalidating existing remotes.
- **Reachability as a network property.** Access is governed by split-horizon
  name resolution plus an allow-list at the reverse proxy, not by application
  configuration. The forge is unaware of its own exposure model.
- **Defence in depth over concealment.** An unpublished address makes a service
  unlisted, not protected, because a client that knows the address can still
  present the expected Host header. The enforcing boundary is therefore an
  explicit source-range allow-list, verified by attempting a spoofed request
  from outside and confirming rejection.
- **Certificates without public exposure.** Trust material is obtained through a
  DNS-based ACME challenge under an existing wildcard, so a valid certificate is
  served by a host that is deliberately unreachable from the public internet.
  A challenge requiring inbound public reachability cannot satisfy this design.
- **Separated data plane.** The application joins the shared proxy network; the
  database is confined to a private network and is not routable from it.
- **Outward publication instead of inward exposure.** Individual repositories
  are made public by mirroring them to an external provider on push. Publication
  is per repository and never widens the exposure of the instance itself.
- **Architecture-matched CI.** Build agents are registered per processor
  architecture and selected by job label. Native execution is preferred over
  emulation, which imposes a multiple-fold penalty on compilation workloads and
  can erase the advantage of nominally faster hardware.
- **Pinned artifacts.** Image tags are exact. The deployment platform re-pulls on
  tag change rather than on redeploy, so a floating tag silently freezes the
  running version while appearing current.
- **Runtime secret injection.** Credentials are resolved by the platform from a
  secret manager at deploy time; no values are committed.

## Operational Notes

- The standard SSH port belongs to the host's own daemon. The forge therefore
  advertises one port while binding another internally, and publishes it on a
  private interface only. Git over SSH does not traverse the reverse proxy,
  which terminates HTTP rather than arbitrary TCP.
- The database is PostgreSQL rather than an embedded file store. This is chosen
  in advance of CI being enabled, because concurrent build agents generate write
  patterns that an embedded store handles poorly and because migrating a
  populated instance between the two is disruptive.
- Registration is disabled, anonymous browsing is refused, and repositories
  default to private, so a misconfigured route cannot expose content that was
  never intended to be readable.

## Configuration Contract

See `.env.example` for the variables this definition expects. Values are supplied
by the deployment platform.

Host placement, network coordinates, routing rules, identity-provider wiring,
backup targets, and recovery procedures are maintained privately.
`traefik-router.example.yml` publishes the shape of the proxy rule without its
operational values.
