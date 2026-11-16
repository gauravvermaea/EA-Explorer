#!/usr/bin/env bash
# eax-dr: builds a whole EA Explorer environment from an infrastructure backup (disaster recovery). R5.6-B2.
# The owner, 16 Nov 2026, 20:27: "build me another command which builds an enviornment from a backup. We give it 1. a
# backup folder 2. an install folder 3. a version 4. It downloads the code from github 5. Builds the entire enviornment.
# Like a DR script, call it eax-dr"; 20:28: it needs a copy of the env file too; 20:29: the dr folder runs isolated.
#
#   ./eax-dr.sh --pack <DR pack> --install <folder>          (a pack eax dr-pack made: checked, fingerprint compared)
#   ./eax-dr.sh --backup <folder> --install <folder> --version <x.y.z> --env <file> [--repo <github link>] [--project <name>]
#   --project: its own Docker name (containers and volumes), to keep it apart from an installation on this machine
#
# Asks nothing. One step after another, stopping at the first that fails (the same steps as eax-dr.ps1):
#   1. checks, nothing touched: the backup whole (manifest good, every file matching SHA256SUMS), the env file, the
#      install folder new or empty, Docker answers, the version published on GitHub (never the main branch)
#   2. that release's code from GitHub into the install folder (git, or its tarball)
#   3. the env file as work/eaexplorer.env, the work folders, the backup copied into work/backups/infrastructure
#   4. built and started; 5. the maintenance page on, the background paused, the full restore, started again;
#   6. the background back, the maintenance page off; the smoke test. Report: <install>/work/dr/dr-<time>/.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PACK="" BACKUP="" INSTALL="" VERSION="" ENV_FILE="" REPO="" PROJECT=eaexplorer KEEP_QUIET=0 NO_SMOKE=0 FINGERPRINT=""
while [ $# -gt 0 ]; do
  case $1 in
    --pack) PACK=$2; shift 2;;   # a DR pack (eax dr-pack): the backup, version and env file from it, checked
    --backup) BACKUP=$2; shift 2;; --install) INSTALL=$2; shift 2;; --version) VERSION=${2#v}; shift 2;;
    --env) ENV_FILE=$2; shift 2;; --repo) REPO=$2; shift 2;;
    --project) PROJECT=$2; shift 2;;   # its own Docker name: keeps a copy apart from an installation on this machine
    --keep-quiet) KEEP_QUIET=1; shift;; --no-smoke) NO_SMOKE=1; shift;;   # eax-drill: it compares and tests itself
    *) echo "Unknown option $1"; exit 2;;
  esac
done
abs() { case $1 in /*) printf '%s' "${1%/}";; *) printf '%s/%s' "$(pwd)" "${1%/}";; esac; }
ENV_GIVEN=${ENV_FILE:+1}       # an env file given beside a pack (a new machine's name): the pack's own is not checked
if [ -n "$PACK" ]; then
  PACK=$(abs "$PACK")
  n=$(find "$PACK/backup" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = 1 ] || { echo "$PACK is not a DR pack (it needs one backup in backup/)"; exit 2; }
  [ -n "$BACKUP" ] || BACKUP=$(find "$PACK/backup" -mindepth 1 -maxdepth 1 -type d)
  [ -n "$ENV_FILE" ] || ENV_FILE="$PACK/eaexplorer.env"
  [ -n "$VERSION" ] || VERSION=$(head -n 1 "$PACK/VERSION.txt" 2>/dev/null | tr -d '[:space:]v')
  [ -f "$PACK/fingerprint.json" ] && FINGERPRINT="$PACK/fingerprint.json"
fi
[ -n "$BACKUP" ] && [ -n "$INSTALL" ] && [ -n "$VERSION" ] && [ -n "$ENV_FILE" ] \
  || { echo "Usage: ./eax-dr.sh --pack <DR pack> --install <folder>   or   --backup <folder> --install <folder> --version <x.y.z> --env <file>"; exit 2; }
BACKUP=$(abs "$BACKUP"); INSTALL=$(abs "$INSTALL"); ENV_FILE=$(abs "$ENV_FILE")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG=$(mktemp "${TMPDIR:-/tmp}/eax-dr-$STAMP.XXXX.log")
# shellcheck source=dr-common.sh
. "$HERE/dr-common.sh"
NAME=$(basename "$BACKUP")
START=$SECONDS
RECOVERY=""

finish() {
  local rc=$? result
  if [ "$rc" -eq 0 ]; then result="Done"; else result="Failed"; fi
  local dir="$INSTALL/work/dr/dr-$STAMP"
  [ -d "$INSTALL/work" ] || dir="${TMPDIR:-/tmp}/eax-dr-$STAMP"
  mkdir -p "$dir"
  report "$dir/report.md" "EA Explorer DR, $STAMP" "$result in $(((SECONDS - START) / 60)) minutes. Backup \`$BACKUP\`, install \`$INSTALL\`, version $VERSION." \
    ${RECOVERY:+"Recovery time (from the restore's start to EA Explorer up again): $RECOVERY minutes."}
  cp "$LOG" "$dir/dr.log"
  say ""; say "EA Explorer DR $( [ "$rc" -eq 0 ] && echo DONE || echo FAILED ) in $(((SECONDS - START) / 60)) minutes. Report: $dir/report.md"
}
trap finish EXIT

checks() {
  [ -f "$BACKUP/manifest.json" ] || { echo "$BACKUP is not an infrastructure backup (no manifest.json)"; return 1; }
  local m status bv
  m=$(tr -d '\n' <"$BACKUP/manifest.json")
  status=$(json_get status "$m" || true); bv=$(json_get version "$m" || true)
  [ -z "$status" ] || [ "$status" = "ok" ] || { echo "the backup's manifest says $status: $(json_get error "$m" || true)"; return 1; }
  backup_whole "$BACKUP" >/dev/null || { backup_whole "$BACKUP"; return 1; }
  if [ -n "$bv" ] && [ "$(printf '%s\n%s\n' "${bv%%-*}" "${VERSION%%-*}" | sort -V | tail -n 1)" != "${VERSION%%-*}" ]; then
    echo "the backup is of version $bv, newer than $VERSION: restore it with $bv or newer"; return 1; fi
  [ -f "$ENV_FILE" ] || { echo "the env file $ENV_FILE is not there"; return 1; }
  grep -qE '^(EAX_DEPLOYMENT|EAX_HOSTNAME)=' "$ENV_FILE" || { echo "$ENV_FILE does not read as EA Explorer's env file"; return 1; }
  if [ -d "$INSTALL" ] && [ -n "$(ls -A "$INSTALL" 2>/dev/null)" ]; then echo "$INSTALL is not empty: give a new or empty folder"; return 1; fi
  case "$BACKUP/" in "$INSTALL/"*) echo "the backup may not be inside the install folder"; return 1;; esac
  docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || { echo "Docker does not answer: start it"; return 1; }
  [[ "$PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo "--project is lower-case letters, digits, - and _"; return 1; }
  local mine; mine=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d ' ')
  [ "$mine" -eq 0 ] || { echo "Docker already has $mine container(s) named $PROJECT (another installation): give another --project"; return 1; }
  [ -n "$REPO" ] || REPO=$(grep -E '^EAX_UPDATE_GIT_URL=' "$ENV_FILE" | head -n 1 | cut -d= -f2- | tr -d "\"'")
  REPO=${REPO:-https://github.com/gauravvermaea/EA-Explorer}
  release_published "$REPO" "$VERSION" || return 1
  echo "backup $NAME whole (version ${bv:-?}); v$VERSION published on $REPO"
}

code() {
  mkdir -p "$(dirname "$INSTALL")"
  if command -v git >/dev/null 2>&1; then
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch "v$VERSION" "$REPO" "$INSTALL" || { echo "git clone of v$VERSION failed"; return 1; }
  else
    [[ "$REPO" =~ github\.com[/:]([^/]+)/([^/.]+) ]] || return 1
    mkdir -p "$INSTALL"
    curl -fsSL "https://github.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/archive/refs/tags/v$VERSION.tar.gz" \
      | tar -xz -C "$INSTALL" --strip-components=1 || { echo "the download of v$VERSION failed"; return 1; }
  fi
  local have
  have=$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' "$INSTALL/services/api/version.toml")
  [ "$have" = "$VERSION" ] || { echo "the code says version $have, not $VERSION"; return 1; }
  echo "version $have"
}

in_place() {
  for d in work/logs work/backups/infrastructure work/proxy work/data/imports work/data/exports work/data/tls; do mkdir -p "$INSTALL/$d"; done
  cp "$ENV_FILE" "$INSTALL/work/eaexplorer.env"
  [ "$PROJECT" = eaexplorer ] || printf '%s\n' "$PROJECT" >"$INSTALL/work/compose-project"
  cp -R "$BACKUP" "$INSTALL/work/backups/infrastructure/$NAME"
  echo "the env file as work/eaexplorer.env; the backup copied: $(backup_whole "$INSTALL/work/backups/infrastructure/$NAME")"
}

pack_whole() {
  [ -f "$PACK/PACK.sha256" ] || { echo "$PACK has no PACK.sha256: make the pack with eax dr-pack"; return 1; }
  (cd "$PACK" && if [ -n "$ENV_GIVEN" ]; then grep -v '  eaexplorer.env$' PACK.sha256; else cat PACK.sha256; fi | sha256sum --quiet -c -) >/dev/null 2>&1 \
    || { echo "a file of the pack is missing or does not match its checksum"; return 1; }
  echo "$(grep -c . "$PACK/PACK.sha256") files, each matching its checksum"
}

compare_pack() {
  mkdir -p "$INSTALL/work/dr"
  eax drill fingerprint "$INSTALL/work/dr/fingerprint-after.json" || return 1
  eax drill compare "$FINGERPRINT" "$INSTALL/work/dr/fingerprint-after.json" || return 1
  echo "$(json_get tables "$EAX_JSON") tables and $(json_get files "$EAX_JSON") files the same as when the pack was made"
}

say "EA Explorer DR: builds $INSTALL from the backup $BACKUP, version $VERSION. Nothing is asked."
[ -z "$PACK" ] || step "the DR pack is whole (every file against PACK.sha256)" pack_whole
step "checks (nothing touched yet)" checks
step "the code of v$VERSION from GitHub" code
step "the env file, the work folders and the backup in place" in_place
step "EA Explorer built and started" eax up --wait-all
T1=$SECONDS
step "the maintenance page on and the background paused" eax drill quiet on
step "the full restore of $NAME" eax drill restore "$NAME"
step "EA Explorer started again" eax up --wait-all
[ -z "$FINGERPRINT" ] || step "every table and file compared with the pack's fingerprint" compare_pack
RECOVERY=$(((SECONDS - T1) / 60))
[ "$KEEP_QUIET" -eq 1 ] || step "the background back and the maintenance page off" eax drill quiet off
[ "$NO_SMOKE" -eq 1 ] || step "the smoke test" eax test smoke
exit 0
