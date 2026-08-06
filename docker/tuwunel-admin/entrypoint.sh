#!/bin/sh
# Render config.toml from the template, substituting only MATRIX_HOMESERVER,
# then start the server (reads ./config.toml from the working directory).
set -eu

if [ -z "${MATRIX_HOMESERVER:-}" ]; then
  echo "FATAL: MATRIX_HOMESERVER is not set" >&2
  exit 1
fi

envsubst '${MATRIX_HOMESERVER}' < /app/config.toml.tmpl > /app/config.toml
exec tuwunel-admin
