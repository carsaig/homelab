# tuwunel-admin: web admin UI for a tuwunel Matrix homeserver.
# No official image is published; this pulls the pinned static aarch64-musl
# release binary into a minimal alpine image (no Rust build required).
FROM alpine:3.21

ARG TA_VERSION=0.1.0
RUN apk add --no-cache ca-certificates gettext wget \
 && wget -qO /tmp/ta.tgz "https://github.com/knadh/tuwunel-admin/releases/download/v${TA_VERSION}/tuwunel-admin_${TA_VERSION}_aarch64-unknown-linux-musl.tar.gz" \
 && tar -xzf /tmp/ta.tgz -C /tmp \
 && mv "$(find /tmp -name tuwunel-admin -type f)" /usr/local/bin/tuwunel-admin \
 && chmod +x /usr/local/bin/tuwunel-admin \
 && rm -rf /tmp/ta.tgz

WORKDIR /app
COPY config.toml.tmpl /app/config.toml.tmpl
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8009
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
