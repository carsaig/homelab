# Thin wrapper over the pinned Draupnir image. Renders the config from env vars
# at start (no committed secrets, no fragile file-mount). Base pinned by digest:
# 'latest' at time of writing (no v3.1.0 image tag is published), multi-arch.
FROM ghcr.io/the-draupnir-project/draupnir@sha256:654bb476e1b50b9c1628bc59d525b28d969e572885aa3a5bdeb3b218ce09adf7

COPY render-config.sh /usr/local/bin/render-config.sh
RUN chmod +x /usr/local/bin/render-config.sh

ENTRYPOINT ["/usr/local/bin/render-config.sh"]
