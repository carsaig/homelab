#!/bin/sh
# Setzt die Platzhalter in den HTML-Vorlagen. Bewusst nur diese vier Namen,
# damit ein `$` im Markup unberuehrt bleibt.
set -e
VARS='${SERVICE_NAME} ${SERVICE_URL} ${CONTACT_EMAIL} ${UPDATED}'
for f in /html-src/*.html.template; do
    [ -e "$f" ] || continue
    out="/usr/share/nginx/html/$(basename "$f" .template)"
    envsubst "$VARS" < "$f" > "$out"
    echo "[legal] $(basename "$out") gerendert"
done
cp /html-src/_style.css /usr/share/nginx/html/_style.css
echo "[legal] Stylesheet kopiert"
