#!/bin/sh
# dumpdb NAME FILE [pg_dump connection options...]: one database of an infrastructure backup (backup.sh), in pg_dump's
# custom format, tried three times (R5.6-B1). The owner's first backup and restore test (16 Nov 2026, 19:26) failed with
# only "pg_dump: detail: Query was: SELECT pg_catalog.pg_get_viewdef(...)": a report view was dropped and made again
# while pg_dump read it (the typed report views follow every metamodel change, D139; pg_dump does not lock views). Such
# a change is over in seconds, so the dump is tried again after 20 seconds, twice. When it still fails, the last line
# names the database and pg_dump's own error line (the operations helper shows the last line), not its "detail".
dumpdb() {
  _n=$1 _f=$2
  shift 2
  _why=""
  for _try in 1 2 3; do
    if pg_dump "$@" --format=custom --file="$_f" "$_n" 2>"$_f.err"; then
      rm -f "$_f.err"
      return 0
    fi
    _why=$(grep -m1 -i 'error' "$_f.err" || tail -n1 "$_f.err")
    sed 's/^/  /' "$_f.err" >&2
    rm -f "$_f"
    if [ "$_try" -lt 3 ]; then
      echo "backup: database $_n: ${_why:-pg_dump failed}; tried again in 20 seconds (try $((_try + 1)) of 3)"
      sleep "${EAX_DUMP_RETRY_SECONDS:-20}"
    fi
  done
  rm -f "$_f.err"
  echo "backup: database $_n could not be dumped (3 tries): ${_why:-pg_dump failed}" >&2
  return 1
}
