#!/bin/sh
# The library service: its database first (made when missing, then migrated), then the API.
set -eu
# the passwords and keys as files of their own (Docker secrets under /run/secrets, R6-F1, D745): read into this
# process's environment only, never the container's settings (docker inspect shows none)
for _f in /run/secrets/EAX_*; do
  [ -f "$_f" ] || continue
  _n=$(basename "$_f")
  _v=$(cat "$_f")
  [ -n "$_v" ] && export "$_n=$_v"
done
unset _f _n _v
python -m libsvc.bootstrap
exec gunicorn --bind 0.0.0.0:8100 --workers "${EAX_LIBRARY_WORKERS:-2}" --threads 4 --timeout 120 \
  --access-logfile - "libsvc.app:create_app()"
