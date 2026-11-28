#!/usr/bin/env bash
# The eax container's start (D976): EAX_HOME is the deploy folder, mounted at the same path as on the machine.
#   __shell__   a shell in the folder, eax on the path
#   anything else: eax with those words
set -euo pipefail
HOME_DIR="${EAX_HOME:-$PWD}"
if [ ! -f "$HOME_DIR/eax.sh" ]; then
  echo "This is not an EA Explorer deploy folder: no eax.sh in $HOME_DIR."
  echo "Run the eax wrapper from the deploy folder (./eax ...), which mounts it here."
  exit 2
fi
cd "$HOME_DIR"
if [ "${1:-}" = "__shell__" ]; then
  echo "EA Explorer's eax, in a container: $(docker --version), $(python3 --version)."
  echo "The deploy folder: $HOME_DIR. Try: eax status, eax logins --admins, eax test smoke, eax help. Leave with exit."
  export PS1="eax:\w\$ "
  exec bash --noprofile --norc -i
fi
exec bash "$HOME_DIR/eax.sh" "$@"
