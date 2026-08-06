#!/bin/sh
# Render /data/config/production.yaml from environment variables at start, then
# hand off to the stock Draupnir entrypoint. Secrets (access token) and the real
# homeserver/room live only in the deploy-platform env — never in this repo.
set -eu

: "${DRAUPNIR_HOMESERVER:?set DRAUPNIR_HOMESERVER, e.g. https://matrix.example.net}"
: "${DRAUPNIR_ACCESS_TOKEN:?set DRAUPNIR_ACCESS_TOKEN (bot account token)}"
: "${DRAUPNIR_MANAGEMENT_ROOM:?set DRAUPNIR_MANAGEMENT_ROOM, e.g. #moderators:example.net}"

mkdir -p /data/config
cat > /data/config/production.yaml <<EOF
homeserverUrl: "${DRAUPNIR_HOMESERVER}"
rawHomeserverUrl: "${DRAUPNIR_HOMESERVER}"
accessToken: "${DRAUPNIR_ACCESS_TOKEN}"
pantalaimon:
  use: false
experimentalRustCrypto: false
dataPath: "/data/storage"
managementRoom: "${DRAUPNIR_MANAGEMENT_ROOM}"
autojoinOnlyIfManager: true
recordIgnoredInvites: false
logLevel: "INFO"
verifyPermissionsOnStartup: true
noop: false
disableServerACL: false
automaticallyRedactForReasons: ["spam", "advertising"]
protectAllJoinedRooms: false
backgroundDelayMS: 500
admin:
  enableMakeRoomAdminCommand: false
commands:
  allowNoPrefix: false
  symbolPrefixes: ["!"]
  additionalPrefixes: ["draupnir"]
  ban:
    defaultReasons: ["spam", "brigading", "harassment", "disagreement"]
protections:
  wordlist:
    words: []
    minutesBeforeTrusting: 20
roomStateBackingStore:
  enabled: true
health:
  healthz:
    enabled: false
web:
  enabled: false
pollReports: false
displayReports: true
EOF

exec /draupnir-entrypoint.sh bot --draupnir-config /data/config/production.yaml
