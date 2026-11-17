#!/bin/sh
# The backup container waits for the operations helper to run backup.sh and restore.sh in it (phase 8.4, D216): the
# schedules are kept in the database and set on Administration > Backups (D222); the job runner starts them. What
# backup.sh needs from the environment is saved for docker exec.
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
export -p | grep -E ' (EAX_|POSTGRES_)[A-Z_]*=' > /etc/eax-backup.env
chmod 600 /etc/eax-backup.env
echo "EA Explorer backup: ready (schedules: Administration > Backups)"
exec sleep infinity
