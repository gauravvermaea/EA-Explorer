#!/usr/bin/env bash
# EA Explorer {{VERSION}}: a new installation on THIS machine (Linux or macOS), from the deploy repository (D973).
# Made by EA Explorer's tools/deploy_repo.py: change it there. The deploy page ({{DEPLOY_REPO}}) writes a script made
# for your case (a remote server, mount points, a managed database, Jenkins); this one is the plain local install.
#
#   ./install.sh [laptop|server] [--container] [--yes]
#
#   laptop       one machine, for one person or a demo (the default)
#   server       a server for a team: strong passwords, HTTPS with your certificate (guides/deploy.md)
#   --container  run eax in its container (this machine then needs only Docker); otherwise eax runs here
#   --yes        ask nothing (the checks still stop it when something is missing)
#
# What it does, each step said as it goes: checks this machine (Docker running, Compose, disk, memory, the ports), makes
# the settings (passwords made strong and random, never shown in a log), pulls this release's images, starts EA
# Explorer and waits until it answers, then shows the admin logins once, on the screen only.
set -euo pipefail
cd "$(dirname "$0")"
KIND=laptop; CONTAINER=""; YES=""
for a in "$@"; do
  case "$a" in
    laptop|server) KIND="$a" ;;
    --container) CONTAINER=1 ;;
    --yes) YES=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Unknown: $a (./install.sh --help)"; exit 2 ;;
  esac
done
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' services/api/version.toml)"
EAX=(bash ./eax.sh); [ -n "$CONTAINER" ] && EAX=(./eax)
step() { printf '\n\033[36m== %s\033[0m\n' "$*"; }
ok() { printf '   ok    %s\n' "$*"; }
warn() { printf '\033[33m   warn  %s\033[0m\n' "$*"; }
fail() { printf '\033[31m   STOP  %s\033[0m\n' "$*"; exit 1; }

step "EA Explorer $VERSION: a $KIND installation in $(pwd)"

step "1. This machine"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Linux: https://docs.docker.com/engine/install/ (then add yourself to the docker group); macOS: Docker Desktop."
docker info >/dev/null 2>&1 || fail "Docker is installed but not answering: start it (Linux: sudo systemctl start docker; macOS: open Docker Desktop), or add yourself to the docker group and sign in again."
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null)"
cv="$(docker compose version --short 2>/dev/null || true)"
[ -n "$cv" ] || fail "Docker Compose (the 'docker compose' plugin) is missing: install docker-compose-plugin."
ok "Compose $cv"
free_gb="$(df -Pk . | awk 'NR==2 {print int($4/1048576)}')"
[ "${free_gb:-0}" -ge 20 ] && ok "${free_gb} GB free here" || warn "only ${free_gb} GB free here: 20 GB or more is advised (images, data, backups)"
if [ -r /proc/meminfo ]; then mem_gb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1048576 )); else mem_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 )); fi
need=8; [ "$KIND" = server ] && need=16
[ "${mem_gb:-0}" -ge "$need" ] && ok "${mem_gb} GB of memory" || warn "${mem_gb} GB of memory: $need GB or more is advised for a $KIND"
for port in 80 443; do
  if (command -v ss >/dev/null && ss -ltn "( sport = :$port )" 2>/dev/null | grep -q ":$port") || \
     (command -v lsof >/dev/null && lsof -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1); then
    warn "port $port is in use: EA Explorer's front door needs it (EAX_HTTP_PORT / EAX_HTTPS_PORT in the settings change it)"
  else ok "port $port free"; fi
done
if [ -z "$CONTAINER" ]; then
  command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || fail "curl or wget is needed the first time (eax fetches its Python), or use --container."
fi

step "2. The settings (work/eaexplorer.env)"
if [ -f work/eaexplorer.env ]; then
  ok "already made: kept as it is (an update or a second run)"
else
  "${EAX[@]}" init "$KIND"
  ok "made: every password strong and random; they are never written to a log"
fi

step "3. The images ($VERSION, from {{REGISTRY}}...)"
"${EAX[@]}" images pull

step "4. Starting EA Explorer (the first start takes several minutes: databases, sign-in, the built-in models)"
"${EAX[@]}" up --wait-all

step "5. Done"
"${EAX[@]}" url || true
"${EAX[@]}" logins --admins --yes
cat <<TEXT

Save the admin and break-glass passwords in your password manager now. To see them again on this machine:
  ${EAX[*]} logins --admins     the admin accounts (Super Admin, Keycloak, break-glass, Jenkins)
  ${EAX[*]} logins              every user name and password
Next:
  ${EAX[*]} test smoke          a quick test (minutes);   ${EAX[*]} test full   everything, backups and DR too (hours)
  ${EAX[*]} jenkins up          Jenkins, to run all of this from a browser
  ${EAX[*]} help                every command
TEXT
