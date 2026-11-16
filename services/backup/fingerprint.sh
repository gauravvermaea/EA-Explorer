#!/bin/sh
# The fingerprint of everything a backup holds, for the backup and restore test (R5.6-B1; owner, 16 Nov 2026: "All
# content should now be checked including files using checksum"). The operations helper runs it inside this container
# and compares two fingerprints. Nothing is changed. It prints one line per table and one per file:
#   T <database> <schema.table> <rows> <md5 of the rows>     every table of every database (as backup.sh dumps them)
#   F <file set> <path> <sha256>                             every file of every file set (as backup.sh archives them)
# A table's md5 is over its rows' md5s in order, so the same rows in any physical order give the same fingerprint.
set -eu
[ -f /etc/eax-backup.env ] && . /etc/eax-backup.env
export PGHOST="${EAX_BACKUP_PGHOST:-db}" PGPORT="${EAX_BACKUP_PGPORT:-5432}" PGUSER=postgres PGPASSWORD="${EAX_DB_SUPERUSER_PASSWORD:-}"
. "$(dirname "$0")/servers.sh"           # beside this script (/usr/local/bin in the backup container)

tables() {   # tables <database> [host port]: the T lines of one database
  _db=$1; shift
  _conn=""
  [ $# -ge 2 ] && _conn="--host=$1 --port=$2"
  # shellcheck disable=SC2086
  psql $_conn -X -q -At -F ' ' -d "$_db" <<'SQL' | sed "s#^#T $_db #"
SELECT format('SELECT %L, count(*), md5(coalesce(string_agg(r.h, '''' ORDER BY r.h), '''')) FROM (SELECT md5(t::text) AS h FROM %I.%I t) r',
              n.nspname || '.' || c.relname, n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'
 ORDER BY 1 \gexec
SQL
}

ELSEWHERE=""
HOSTS=$(own_servers)
for N in $(printf '%s\n' "$HOSTS" | awk '{print $1}'); do ELSEWHERE="$ELSEWHERE $N"; done
for DB in $(psql -X -Atc "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres' AND datname !~ '(__restoring|__before|_restore_test)$' ORDER BY 1"); do
  case " $ELSEWHERE " in *" $DB "*) continue;; esac
  tables "$DB"
done
# no database on a server of its own: one empty line, skipped (a bare `[ -n "$N" ] && ...` as the loop's last command
# ended it with 1 and, with set -e, the whole fingerprint: the owner's first run, 16 Nov 2026, 17:08)
printf '%s\n' "$HOSTS" | while read -r N H P; do
  if [ -n "$N" ]; then tables "$N" "$H" "$P"; fi
done

for SET in "documents ${EAX_BACKUP_DOCS:-/mayan}" "tls ${EAX_BACKUP_TLS:-/tls}" "reports ${EAX_BACKUP_REPORTS:-/superset-home}" \
           "imports ${EAX_BACKUP_IMPORTS:-/imports}" "exports ${EAX_BACKUP_EXPORTS:-/exports}" \
           "persist ${EAX_BACKUP_PERSIST:-/persist}"; do
  NAME=${SET%% *} DIR=${SET#* }
  [ -d "$DIR" ] || continue
  # what backup.sh leaves out is left out here too: a restore's own folders, and persist/'s safety-backups/
  (cd "$DIR" && find . -type f ! -path './.eax-restoring/*' ! -path './.eax-before/*' ! -path './safety-backups/*' -print0 \
     | xargs -0 -r sha256sum) | while read -r SUM PATH_; do
    printf 'F %s %s %s\n' "$NAME" "${PATH_#./}" "$SUM"
  done
done
