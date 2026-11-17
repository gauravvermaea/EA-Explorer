#!/bin/bash
# Keycloak's start (R6-F1, D745): its database password and its first administrator's password read from their files
# (Docker secrets under /run/secrets) into this process only, then Keycloak's own start. Keycloak has no *_FILE
# settings; this way docker inspect and the container's settings show no password. Mounted read-only at /eax-secrets.
set -eu
read_secret() { [ -f "/run/secrets/$1" ] && printf '%s' "$(< "/run/secrets/$1")"; }
KC_DB_PASSWORD="$(read_secret EAX_KEYCLOAK_DB_PASSWORD)"
KC_BOOTSTRAP_ADMIN_PASSWORD="$(read_secret EAX_KC_ADMIN_PASSWORD)"
export KC_DB_PASSWORD KC_BOOTSTRAP_ADMIN_PASSWORD
# certificate mode (R6-C1): the database is reached with Keycloak's own certificate instead, when it has one
if [ -f /eax-certs/client.key.pk8 ]; then
  export KC_DB_URL="${KC_DB_URL}?sslmode=verify-full&sslrootcert=/eax-certs/ca.crt&sslcert=/eax-certs/client.crt&sslkey=/eax-certs/client.key.pk8"
fi
exec /opt/keycloak/bin/kc.sh "$@"
