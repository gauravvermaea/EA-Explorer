#!/usr/bin/env bash
# eax-drill: the restore drill, automated - an installation backed up and shut down, a copy built with eax-dr in a new
# folder from the installation's own code (no GitHub, 22:44) and restored there, then tested. R5.6-B2 (the owner's
# design, 16 Nov 2026, 21:40 and 21:52; the same steps as eax-drill.ps1).
#
#   ./eax-drill.sh --install <running installation> --dr <new folder> --temp <folder>
#
# Asks nothing. Checks (the installation running; the DR and temp folders apart from it and holding nothing but an
# earlier drill's leftovers, which are then removed, the earlier DR copy from Docker too); the smoke test; a test
# project, models and content of every kind; the maintenance page on, the background paused, the fingerprint; a full
# backup; the test content removed, the background back; the installation shut down (containers removed, data and images
# kept); the backup, the env file and the code copied into the temp folder and checked (as a DR pack has them); eax-dr
# from that code (no GitHub) into the DR folder under its own Docker
# name (eaexplorer-dr); in the DR copy the fingerprint compared, the test content found, the smoke test. Then, passed or
# failed, everything is put back (owner, 17 Nov 2026, 09:03: "auto remove and create destination folders. Expect them to
# be cleaned and deleted"): the DR copy removed from Docker and its folder deleted, the temp folder deleted, the
# installation started again, the drill's backup deleted (kept when it failed). Report: <install>/work/tests/drill-<time>/.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
INSTALL="" DR="" TEMP=""
while [ $# -gt 0 ]; do
  case $1 in
    --install) INSTALL=$2; shift 2;; --dr) DR=$2; shift 2;; --temp) TEMP=$2; shift 2;;
    *) echo "Unknown option $1"; exit 2;;
  esac
done
[ -n "$INSTALL" ] && [ -n "$DR" ] && [ -n "$TEMP" ] || { echo "Usage: ./eax-drill.sh --install <folder> --dr <new folder> --temp <folder>"; exit 2; }
abs() { case $1 in /*) printf '%s' "${1%/}";; *) printf '%s/%s' "$(pwd)" "${1%/}";; esac; }
INSTALL=$(abs "$INSTALL"); DR=$(abs "$DR"); TEMP=$(abs "$TEMP")
inside() { case "$1/" in "$2/"*) return 0;; esac; return 1; }
DR_PROJECT=eaexplorer-dr
# what the drill may delete by itself: nothing, or only what a drill leaves (a DR copy under its Docker name; drill-* and
# eax-dr-* folders) - never a folder of anything else, however it was given
disposable_dr() {
  [ ! -d "$1" ] || [ -z "$(ls -A "$1" 2>/dev/null)" ] || [ "$(head -n 1 "$1/work/compose-project" 2>/dev/null | tr -d '[:space:]')" = "$DR_PROJECT" ]
}
disposable_temp() {
  local i
  [ -d "$1" ] || return 0
  for i in "$1"/* "$1"/.[!.]*; do
    [ -e "$i" ] || continue
    [ -d "$i" ] && [[ "$(basename "$i")" =~ ^(drill|eax-dr)-[0-9]{8}T[0-9]{6}Z ]] || return 1
  done
}
disposable_temp "$TEMP" || { echo "$TEMP holds files other than an earlier drill's: give a new folder (the drill deletes it afterwards)"; exit 2; }

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUN="$TEMP/drill-$STAMP"
KEEP="$INSTALL/work/tests/drill-$STAMP"   # the report and the logs, kept in the installation
mkdir -p "$RUN"
LOG="$RUN/drill.log"
STATE="$RUN/content.json"          # the test content's ids and its test accounts' tokens: removed at the end
# shellcheck source=dr-common.sh
. "$HERE/dr-common.sh"
START=$SECONDS
ORIGINAL=$INSTALL VERSION="" BACKUPS="" CONFIG="" NAME="" COPY="" SHUT=0 QUIET_IN="" CONTENT_IN="" RECOVERY="" DR_STARTED=0

finish() {
  local rc=$? extra=() notes=() n r diag=""
  # the failure explains itself (19:05): every container's state and its log's last lines, where it failed
  if [ "$rc" -ne 0 ] && eax drill diagnose "$RUN/diagnostics" >/dev/null 2>&1; then diag=$(json_get not_well "$EAX_JSON" || echo ""); fi
  if [ -n "$QUIET_IN" ]; then INSTALL=$QUIET_IN; eax drill quiet off >/dev/null 2>&1; fi
  # the test content removed wherever EA Explorer still runs with it, before its state (and tokens) goes
  if [ -n "$CONTENT_IN" ] && [ -f "$STATE" ] && ! { [ "$SHUT" -eq 1 ] && [ "$CONTENT_IN" = "$ORIGINAL" ]; }; then
    INSTALL=$CONTENT_IN; eax drill content-remove "$STATE" >/dev/null 2>&1 && CONTENT_IN=""
  fi
  rm -f "$STATE"
  INSTALL=$ORIGINAL
  # put everything back (09:03): the DR copy out of Docker and its folder gone, the installation started again
  if [ "$DR_STARTED" -eq 1 ]; then
    [ -d "$DR/work/dr" ] && cp -R "$DR/work/dr" "$RUN/eax-dr" 2>/dev/null
    wait_later_start "$DR" 20 || notes+=("The DR copy's background start was still running after 20 minutes; removed anyway.")
    if eax drill remove-copy "$DR_PROJECT" >/dev/null; then
      notes+=("The DR copy removed from Docker: $(json_get containers "$EAX_JSON") container(s), $(json_get volumes "$EAX_JSON") volume(s).")
    else notes+=("The DR copy could not be removed from Docker: run \`./eax drill remove-copy $DR_PROJECT\` in the installation."); fi
    if rm -rf "$DR"; then notes+=("The DR folder $DR deleted."); else notes+=("The DR folder $DR could not be deleted."); fi
  elif [ -d "$DR" ] && [ -z "$(ls -A "$DR" 2>/dev/null)" ]; then rmdir "$DR"; fi
  if [ "$SHUT" -eq 1 ]; then
    say ""; say "> the installation started again"
    if eax up --wait-all >/dev/null; then notes+=("The installation started again.")
    else notes+=("The installation could not be started again: in $ORIGINAL run \`./eax up\`."); fi
  fi
  if [ -n "$NAME" ]; then
    if [ "$rc" -eq 0 ]; then
      if eax drill delete-backup "$NAME" >/dev/null; then notes+=("The drill's backup $NAME deleted.")
      else notes+=("The drill's backup $NAME could not be deleted: \`./eax drill delete-backup $NAME\`."); fi
    else notes+=("The drill's backup $NAME is kept (pinned) in the installation's backups: \`./eax drill delete-backup $NAME\` when done."); fi
  fi
  [ -n "$CONTENT_IN" ] && notes+=("The test content (self_test_...) may still be in $CONTENT_IN; the next self-test run there removes it.")
  [ -n "$RECOVERY" ] && extra+=("Recovery time (from shutting the installation down to the DR copy restored and sign-in working): $RECOVERY minutes.")
  if [ "${#ALL_WARNINGS[@]}" -gt 0 ]; then
    extra+=("" "## Warnings (the drill carried on)" "")
    for n in "${ALL_WARNINGS[@]}"; do extra+=("- $n"); done
  fi
  if [ -d "$RUN/diagnostics" ]; then
    extra+=("" "## Diagnostics" "" "Every container's state and the last lines of each one's log: \`diagnostics/containers.txt\` and \`diagnostics/logs/\` beside this report." "")
    extra+=("- ${diag:+not well: }${diag:-every container was running}")
  fi
  extra+=("" "## Afterwards" "")
  for n in ${notes[@]+"${notes[@]}"}; do extra+=("- $n"); done
  report "$RUN/report.md" "EA Explorer restore drill, $STAMP" \
    "$(if [ "$rc" -ne 0 ]; then echo Failed; elif [ "${#ALL_WARNINGS[@]}" -gt 0 ]; then echo "Passed with ${#ALL_WARNINGS[@]} warning(s)"; else echo Passed; fi) in $(((SECONDS - START) / 60)) minutes. Installation \`$ORIGINAL\`, DR copy \`$DR\` ($DR_PROJECT), version ${VERSION:-?}, backup \`${NAME:-none}\`." \
    ${extra[@]+"${extra[@]}"}
  # the report and the logs kept in the installation; the temp folder deleted
  r="$RUN/report.md"
  mkdir -p "$KEEP" 2>/dev/null && r="$KEEP/report.md"
  for n in ${notes[@]+"${notes[@]}"}; do say "$n"; done
  for n in ${ALL_WARNINGS[@]+"${ALL_WARNINGS[@]}"}; do say "warning: $n"; done
  say ""; say "EA Explorer restore drill $(if [ "$rc" -ne 0 ]; then echo FAILED; elif [ "${#ALL_WARNINGS[@]}" -gt 0 ]; then echo "PASSED with ${#ALL_WARNINGS[@]} warning(s)"; else echo PASSED; fi) in $(((SECONDS - START) / 60)) minutes. Report: $r"
  if [ -d "$KEEP" ] && cp -R "$RUN/report.md" "$RUN/drill.log" "$KEEP/" 2>/dev/null; then
    [ -d "$RUN/eax-dr" ] && cp -R "$RUN/eax-dr" "$KEEP/"
    [ -d "$RUN/diagnostics" ] && cp -R "$RUN/diagnostics" "$KEEP/"
    rm -rf "$RUN"; rmdir "$TEMP" 2>/dev/null
  fi
  return 0
}
trap finish EXIT

checks() {
  [ -f "$INSTALL/eax.sh" ] && [ -f "$INSTALL/work/eaexplorer.env" ] || { echo "$INSTALL is not an EA Explorer installation (no eax.sh or work/eaexplorer.env)"; return 1; }
  for p in "$DR" "$TEMP"; do
    if inside "$p" "$INSTALL" || inside "$INSTALL" "$p"; then echo "$p must be a folder of its own, outside $INSTALL"; return 1; fi
  done
  if inside "$DR" "$TEMP" || inside "$TEMP" "$DR"; then echo "the DR folder and the temp folder must be apart"; return 1; fi
  disposable_dr "$DR" || { echo "$DR holds something other than an earlier drill's DR copy: give a new folder (the drill deletes it afterwards)"; return 1; }
  docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || { echo "Docker does not answer: start it"; return 1; }
  eax drill info || return 1
  VERSION=$(json_get version "$EAX_JSON")
  BACKUPS=$(json_get backups "$EAX_JSON"); CONFIG=$(json_get config "$EAX_JSON")
  case "$EAX_JSON" in *'"shared": []'*|*'"shared":[]'*) ;; *'"shared"'*)
    echo "the config file puts data in this machine's own folders ($(json_get shared "$EAX_JSON")): a DR copy on this machine would use the same folders and its restore would write over the installation's data. Rehearse on another machine with a DR pack instead"; return 1;; esac
  eax drill running || return 1
  # the pre-flight (19:05): too little disk fails now, in seconds; a container still starting or the background busy warns
  eax drill preflight "$TEMP" "$DR" || return 1
  echo "running, version $VERSION; a backup of about $(json_get backup_gb "$EAX_JSON") GB fits"
}

leftovers() {
  eax drill remove-copy "$DR_PROJECT" || return 1
  local n; n="$(json_get containers "$EAX_JSON") container(s), $(json_get volumes "$EAX_JSON") volume(s)"
  rm -rf "$DR" && mkdir -p "$DR" || return 1
  find "$TEMP" -mindepth 1 -maxdepth 1 ! -name "drill-$STAMP" -exec rm -rf {} + || return 1
  echo "$n of an earlier DR copy removed"
}

# the smoke test: passed; or failed only on timing (a warning, the drill carries on); or found a fault (a failure)
smoke() {
  if eax test smoke; then echo "passed"; return 0; fi
  eax drill smoke-result || return 1
  echo "passed, but some checks only slow"
}

content() { CONTENT_IN=$INSTALL; eax drill content "$STATE" || return 1; echo "$(json_get made "$EAX_JSON") kinds made and read back"; }
quiet_on() { eax drill quiet on || return 1; QUIET_IN=$INSTALL; }
quiet_off() { eax drill quiet off || return 1; QUIET_IN=""; }
backup() { eax drill backup || return 1; NAME=$(json_get name "$EAX_JSON"); echo "$NAME"; }
content_remove() { eax drill content-remove "$STATE" || return 1; CONTENT_IN=""; echo "removed"; }
shutdown() { eax drill shutdown || return 1; SHUT=1; echo "stopped"; }

copy_files() {
  COPY="$RUN/backup/$NAME"
  mkdir -p "$RUN/backup" && cp -R "$BACKUPS/$NAME" "$COPY" && cp "$CONFIG" "$RUN/eaexplorer.env" || return 1
  [ "$(sha256sum <"$CONFIG")" = "$(sha256sum <"$RUN/eaexplorer.env")" ] || { echo "the env file's copy does not match"; return 1; }
  eax drill code "$RUN/code" || return 1
  code_whole "$RUN/code" "$VERSION" >/dev/null || { code_whole "$RUN/code" "$VERSION"; return 1; }
  echo "$(backup_whole "$COPY"), the env file and the code ($(json_get files "$EAX_JSON") files)"
}

dr() {
  DR_STARTED=1
  "$BASH" "$HERE/eax-dr.sh" --backup "$COPY" --install "$DR" --code "$RUN/code" --env "$RUN/eaexplorer.env" \
    --project "$DR_PROJECT" --keep-quiet --no-smoke || { echo "eax-dr failed (its report is in $DR/work/dr)"; return 1; }
  QUIET_IN=$DR; CONTENT_IN=$DR
  echo "done"
}

compare() {
  eax drill fingerprint "$RUN/after.json" || return 1
  eax drill compare "$RUN/before.json" "$RUN/after.json" || return 1
  echo "$(json_get tables "$EAX_JSON") tables and $(json_get files "$EAX_JSON") files the same"
}

say "EA Explorer restore drill: $INSTALL backed up and shut down; a copy built from its own code in $DR and restored. Nothing is asked."
step "checks (nothing touched yet)" checks
step "an earlier drill's leftovers removed and the folders made" leftovers
step "the smoke test, before" smoke
step "a test project, models and content of every kind" content
step "the maintenance page on and the background paused" quiet_on
step "the background finished what it was doing" eax drill idle
step "the fingerprint before (every table and file)" eax drill fingerprint "$RUN/before.json"
step "a full infrastructure backup" backup
step "the test content removed from the installation" content_remove
step "the background back and the maintenance page off" quiet_off
T0=$SECONDS
step "the installation shut down (containers removed; data and images kept)" shutdown
step "the backup, the env file and the code copied into the temp folder and checked" copy_files
step "eax-dr: v$VERSION from the copied code (no GitHub) into $DR, built and restored ($DR_PROJECT)" dr
RECOVERY=$(((SECONDS - T0) / 60))
INSTALL=$DR                        # from here on, eax runs in the DR copy
step "the fingerprint after, compared with before (every table and file)" compare
step "the test content found in the DR copy as it was made" eax drill content-check "$STATE"
step "the background back and the maintenance page off" quiet_off
step "the rest of the DR copy up (Reports, Documents, Diagrams)" eax up --wait-all
step "the smoke test, after" smoke
step "the test content removed from the DR copy" content_remove
exit 0
