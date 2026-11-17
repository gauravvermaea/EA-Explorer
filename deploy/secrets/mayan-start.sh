#!/bin/bash
# Documents' (Mayan EDMS) start (R6-F1, D745): every {{EAX_...}} placeholder in its MAYAN_* settings is filled from the
# secret file of that name (Docker secrets under /run/secrets), in this process only, then Mayan's own start. Mayan
# has no *_FILE settings; this way docker inspect and the container's settings show the placeholders, never the
# passwords. Mounted read-only at /eax-secrets.
set -eu
shopt -u patsub_replacement 2>/dev/null || true   # an & in a password stays an &
for f in /run/secrets/EAX_*; do
  [ -f "$f" ] || continue
  name="${f##*/}"
  value="$(< "$f")"
  for var in $(compgen -e); do
    case "$var" in
      MAYAN_*)
        current="${!var}"
        if [[ "$current" == *"{{$name}}"* ]]; then
          export "$var=${current//"{{$name}}"/$value}"
        fi
        ;;
    esac
  done
done
for var in $(compgen -e); do
  case "$var" in MAYAN_*) if [[ "${!var}" == *"{{EAX_"* ]]; then echo "mayan-start: $var still has a placeholder: its secret file is missing" >&2; fi ;; esac
done
ENTRY="$(command -v entrypoint.sh || echo /usr/local/bin/entrypoint.sh)"
exec "$ENTRY" "$@"
