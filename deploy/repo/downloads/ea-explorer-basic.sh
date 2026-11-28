#!/usr/bin/env bash
# EA Explorer {{VERSION}}: the basic install on this computer (the laptop setup, no questions). Run: bash ea-explorer-basic.sh
# Written by the deploy page; it holds no password.
set -euo pipefail
FOLDER="$HOME/ea-explorer"
TARBALL="{{DEPLOY_REPO}}/archive/refs/heads/main.tar.gz"
step() { printf '\n\033[36m== %s\033[0m\n' "$*"; }
stop() { printf '\033[31mSTOPPED: %s\033[0m\n' "$*"; exit 1; }
OS="$(uname -s)"

step "1 of 7: this computer"
if [ "$OS" = Linux ]; then
  mem=$(awk '/MemTotal/ {print int($2/1048576)}' /proc/meminfo)
else
  mem=$(( $(sysctl -n hw.memsize) / 1073741824 ))
fi
free=$(df -Pk "$HOME" | awk 'NR==2 {print int($4/1048576)}')
echo "   memory: $mem GB   free disk: $free GB"
[ "$mem" -ge 15 ] || echo "   warn: 16 GB of memory or more is advised"
[ "$free" -ge 30 ] || stop "only $free GB free: EA Explorer needs about 30 GB."
command -v curl >/dev/null || stop "curl is missing: install it (sudo apt install curl, or your system's way) and run this again."

step "2 of 7: Docker"
if ! command -v docker >/dev/null; then
  if [ "$OS" = Linux ]; then
    echo "Docker is missing: installing it with Docker's own installer (it asks for your password)..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
  elif command -v brew >/dev/null; then
    echo "Docker Desktop is missing: installing it with Homebrew..."
    brew install --cask docker
    open -a Docker
  else
    stop "Docker Desktop is needed: https://docs.docker.com/desktop/setup/install/mac-install/ (install it, start it, run this again)."
  fi
fi
# docker(): Docker, through sudo until the docker group applies (a new sign-in)
if docker info >/dev/null 2>&1; then D=""; elif [ "$OS" = Linux ] && sudo docker info >/dev/null 2>&1; then D="sudo -E"; else
  [ "$OS" = Linux ] && { sudo systemctl start docker 2>/dev/null || true; D="sudo -E"; } || { open -a Docker 2>/dev/null || true; D=""; }
  for i in $(seq 1 60); do $D docker info >/dev/null 2>&1 && break; sleep 3; done
  $D docker info >/dev/null 2>&1 || stop "Docker does not answer: start it and run this again."
fi
$D docker compose version >/dev/null 2>&1 || stop "Docker Compose is missing (the docker-compose-plugin package)."
echo "   Docker is running."

step "3 of 7: getting EA Explorer"
if [ ! -f "$FOLDER/eax.sh" ]; then
  mkdir -p "$FOLDER"
  curl -fsSL "$TARBALL" | tar -xz --strip-components=1 -C "$FOLDER"
else
  echo "   already here: $FOLDER"
fi
cd "$FOLDER"
export EAX_NONINTERACTIVE=1 EAX_NO_BROWSER=1

step "4 of 7: the settings (laptop)"
[ -f work/eaexplorer.env ] && echo "   kept: the settings are already there" || $D bash ./eax.sh init laptop --password

step "5 of 7: the images (the first time takes a while)"
$D bash ./eax.sh images pull --missing

step "6 of 7: starting EA Explorer (several minutes)"
$D bash ./eax.sh up --wait-all
[ -n "$D" ] && sudo chown -R "$USER" "$FOLDER" 2>/dev/null || true

step "7 of 7: the smoke test (a few minutes)"
if $D bash ./eax.sh test smoke; then echo "   the smoke test passed"; else echo "   the smoke test found a problem: its report is in $FOLDER/work/tests (and on the Self-test screen)"; fi

URL=$($D bash ./eax.sh url 2>/dev/null | sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g' | grep -oE 'https?://localhost[^ ,)]*' | head -1 || true)
URL="${URL:-https://localhost}"
printf '\n\033[32mEA Explorer is running at %s\033[0m\n\nSign in with these (laptop passwords: for trying it out only):\n\n' "$URL"
$D bash ./eax.sh logins
cat <<TEXT

Later, in $FOLDER:  ./eax.sh stop   ./eax.sh up   ./eax.sh logins
If the browser warns about the certificate: ./eax.sh trust (once).
TEXT
(command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1) || (command -v open >/dev/null && open "$URL") || true

printf '\nRun the full test now? It tests everything, backups and DR included, and takes a few hours. [y/N] '
read -r ANSWER || ANSWER=n
case "$ANSWER" in
  y|Y|yes|YES) $D bash ./eax.sh test full ;;
  *) echo "Later, in $FOLDER: ./eax.sh test full" ;;
esac
