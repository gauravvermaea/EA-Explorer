#!/usr/bin/env bash
# eax-drill: the restore drill, automated - an installation backed up and shut down, a copy built with eax-dr in a new
# folder from the installation's own code (no GitHub, 22:44) and restored there, then tested. R5.6-B2 (the owner's
# design, 16 Nov 2026, 21:40 and 21:52; the same steps as eax-drill.ps1).
#
#   ./eax-drill.sh --install <running installation> --dr <new folder> --temp <folder>
#
# Asks nothing. Checks (the installation running, the DR folder new); the smoke test; a test
# project, models and content of every kind; the maintenance page on, the background paused, the fingerprint; a full
# backup; the test content removed, the background back; the installation shut down (containers removed, data and images
# kept); the backup, the env file and the code copied into the temp folder and checked (as a DR pack has them); eax-dr
# from that code (no GitHub) into the DR folder under its own Docker
# name (eaexplorer-dr); in the DR copy the fingerprint compared, the test content found, the smoke test. The DR copy is
# left running; the report (<temp>/drill-<time>/report.md) says how to go back to the installation.
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

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUN="$TEMP/drill-$STAMP"
mkdir -p "$RUN"
LOG="$RUN/drill.log"
STATE="$RUN/content.json"          # the test content's ids and its test accounts' tokens: removed at the end
# shellcheck source=dr-common.sh
. "$HERE/dr-common.sh"
START=$SECONDS
ORIGINAL=$INSTALL VERSION="" BACKUPS="" CONFIG="" NAME="" COPY="" SHUT=0 QUIET_IN="" CONTENT_IN="" RECOVERY=""

finish() {
  local rc=$? extra=()
  if [ -n "$QUIET_IN" ]; then INSTALL=$QUIET_IN; eax drill quiet off >/dev/null 2>&1; fi
  rm -f "$STATE"
  [ -n "$RECOVERY" ] && extra+=("Recovery time (from shutting the installation down to the DR copy restored and up): $RECOVERY minutes.")
  [ "$rc" -eq 0 ] && [ -n "$COPY" ] && rm -rf "$(dirname "$COPY")" "$RUN/code"
  [ -n "$CONTENT_IN" ] && extra+=("" "The test content (self_test_...) is still in $CONTENT_IN; the next self-test run removes it.")
  if [ "$SHUT" -eq 1 ]; then
    extra+=("" "## Back to the installation" "" "    cd \"$DR\" && ./eax.sh down" "    cd \"$ORIGINAL\" && ./eax.sh up" ""
            "Or keep the DR copy: it runs at the same address, under the Docker name $DR_PROJECT.")
    [ "$rc" -ne 0 ] && [ -n "$COPY" ] && extra+=("" "The backup is kept in \`$COPY\`.")
    say ""; say "Back to the installation:  cd \"$DR\" && ./eax.sh down   then   cd \"$ORIGINAL\" && ./eax.sh up"
  fi
  report "$RUN/report.md" "EA Explorer restore drill, $STAMP" \
    "$([ "$rc" -eq 0 ] && echo Passed || echo Failed) in $(((SECONDS - START) / 60)) minutes. Installation \`$ORIGINAL\`, DR copy \`$DR\`, version ${VERSION:-?}, backup \`${NAME:-none}\`." \
    ${extra[@]+"${extra[@]}"}
  say ""; say "EA Explorer restore drill $([ "$rc" -eq 0 ] && echo PASSED || echo FAILED) in $(((SECONDS - START) / 60)) minutes. Report: $RUN/report.md"
}
trap finish EXIT

checks() {
  [ -f "$INSTALL/eax.sh" ] && [ -f "$INSTALL/work/eaexplorer.env" ] || { echo "$INSTALL is not an EA Explorer installation (no eax.sh or work/eaexplorer.env)"; return 1; }
  for p in "$DR" "$TEMP"; do
    if inside "$p" "$INSTALL" || inside "$INSTALL" "$p"; then echo "$p must be a folder of its own, outside $INSTALL"; return 1; fi
  done
  if inside "$DR" "$TEMP" || inside "$TEMP" "$DR"; then echo "the DR folder and the temp folder must be apart"; return 1; fi
  if [ -d "$DR" ] && [ -n "$(ls -A "$DR" 2>/dev/null)" ]; then echo "$DR is not empty: the DR copy always goes into a new folder"; return 1; fi
  docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || { echo "Docker does not answer: start it"; return 1; }
  eax drill info || return 1
  VERSION=$(json_get version "$EAX_JSON")
  BACKUPS=$(json_get backups "$EAX_JSON"); CONFIG=$(json_get config "$EAX_JSON")
  eax drill running || return 1
  [ "$(docker ps -aq --filter "label=com.docker.compose.project=$DR_PROJECT" | wc -l | tr -d ' ')" -eq 0 ] \
    || { echo "a DR copy from an earlier drill is still in Docker ($DR_PROJECT): in its folder run ./eax.sh cleanup --all"; return 1; }
  echo "running, version $VERSION"
}

content() { eax drill content "$STATE" || return 1; CONTENT_IN=$INSTALL; echo "$(json_get made "$EAX_JSON") kinds made and read back"; }
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
step "the smoke test, before" eax test smoke
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
step "the smoke test, after" eax test smoke
step "the test content removed from the DR copy" content_remove
exit 0
