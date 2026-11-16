#!/usr/bin/env bash
# EA Explorer installer for Linux and macOS (phase 36, D502). Needs nothing but this file: it asks for the repository
# link and the version, downloads EA Explorer from there (the release archive with curl, no git needed; a shallow
# clone when git is here), checks it, and then runs its deployment wizard (./eax.sh deploy).
#
#   curl -fsSL <repository's raw address>/eax-deploy.sh -o eax-deploy.sh && bash eax-deploy.sh
#
# Options (each is asked when not given):
#   --repo URL          the repository link (the public GitHub repository EA Explorer comes from)
#   --channel C         prod (its published releases) or rc (its published pre-releases too)
#   --version TAG       a published release's tag, e.g. v5.6.0 (instead of choosing; never a branch or a commit)
#   --folder DIR        where to put it (default ~/eaexplorer)
#   --no-deploy         download and check only; run ./eax.sh deploy yourself later
# Anything after -- is passed to the wizard (e.g. -- --web, -- --console --kind server).
set -euo pipefail

REPO="${EAX_REPO:-}"; CHANNEL=""; REF=""; FOLDER="${EAX_FOLDER:-$HOME/eaexplorer}"; DEPLOY=1; PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    --version) REF="$2"; shift 2 ;;
    --folder) FOLDER="$2"; shift 2 ;;
    --no-deploy) DEPLOY=0; shift ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --) shift; PASS=("$@"); break ;;
    *) echo "Unknown option $1 (--help lists them)"; exit 2 ;;
  esac
done

ask() {   # ask "question" default -> the answer
  local a
  read -r -p "$1${2:+ [$2]}: " a </dev/tty || a=""
  printf '%s' "${a:-$2}"
}
say() { printf '%s\n' "$*"; }

say "EA Explorer installer: downloads EA Explorer and starts its deployment wizard."
[ -n "$REPO" ] || REPO=$(ask "Repository link" "https://github.com/gauravvermaea/EA-Explorer")
[ -n "$REPO" ] || { say "A repository link is needed."; exit 2; }
REPO="${REPO%/}"; REPO="${REPO%.git}"

# R5.6-U2: versions come only from the repository's published GitHub Releases, newest first; never the main branch
if [ -z "$REF" ]; then
  if [ -z "$CHANNEL" ]; then
    say "Which channel?"
    say "  1  Prod     published releases   [default]"
    say "  2  RC       published pre-releases too, for testing before a release"
    case "$(ask "Choose" 1)" in 2|rc) CHANNEL=rc ;; *) CHANNEL=prod ;; esac
  fi
  [[ "$REPO" =~ github\.com[/:]([^/]+)/([^/]+)$ ]] || { say "The repository must be on github.com: its Releases page lists the versions."; exit 2; }
  json=$(curl -fsSL -H "Accept: application/vnd.github+json" \
         "${EAX_GITHUB_API:-https://api.github.com}/repos/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/releases?per_page=100" 2>/dev/null) || json=""
  # each release's tag, whether it is a draft, then whether it is a pre-release
  list=$(printf '%s' "$json" | grep -oE '"tag_name": *"[^"]*"|"draft": *(true|false)|"prerelease": *(true|false)' \
         | sed -E 's/.*"tag_name": *"([^"]*)"/T \1/; s/.*"draft": *(true|false)/D \1/; s/.*"prerelease": *(true|false)/P \1/' \
         | awk -v ch="$CHANNEL" '$1=="T"{t=$2; d="false"} $1=="D"{d=$2} $1=="P"{ if (d=="false" && t ~ /^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$/ && (ch=="rc" || ($2=="false" && t !~ /-rc\./))) print t; t="" }' \
         | sort -V -r | head -15 || true)
  if [ -z "$list" ]; then
    say "No published release could be read from GitHub (it cannot be reached, its limit on calls without a sign-in is"
    say "reached, or nothing is published yet): nothing is offered. Try again later, or give --version vX.Y.Z."
    exit 1
  fi
  say "Published releases on $CHANNEL (newest first):"; i=0
  while IFS= read -r t; do i=$((i + 1)); say "  $i  $t"; done <<< "$list"
  pick=$(ask "Choose" 1)
  if [[ "$pick" =~ ^[0-9]+$ ]]; then REF=$(printf '%s\n' "$list" | sed -n "${pick}p"); else REF="$pick"; fi
fi
[ -n "$REF" ] || { say "A version is needed."; exit 2; }
[[ "$REF" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || { say "$REF is not a release: give a published release's tag such as v5.6.0 (never a branch or a commit)."; exit 2; }
CHANNEL="${CHANNEL:-$(case "$REF" in *-rc.*) echo rc ;; *) echo prod ;; esac)}"

if [ -e "$FOLDER" ] && [ -n "$(ls -A "$FOLDER" 2>/dev/null)" ]; then
  if [ -f "$FOLDER/eax.sh" ]; then
    say "$FOLDER holds EA Explorer already. To move it to a newer version use its updates (./eax.sh update);"
    say "to deploy it again: cd $FOLDER && ./eax.sh deploy"
  else
    say "$FOLDER is not empty: choose another folder with --folder."
  fi
  exit 1
fi
mkdir -p "$FOLDER"

# the address of the release archive (GitHub, GitLab; EAX_ARCHIVE_URL for anything else, e.g. https://host/{repo}/{ref}.tar.gz)
archive_url() {
  if [ -n "${EAX_ARCHIVE_URL:-}" ]; then printf '%s' "${EAX_ARCHIVE_URL//\{repo\}/$REPO}" | sed "s#{ref}#$REF#g"; return; fi
  if [[ "$REPO" =~ ^(https?://|git@)github\.com[/:]([^/]+)/([^/]+)$ ]]; then
    o="${BASH_REMATCH[2]}"; n="${BASH_REMATCH[3]}"
    if [[ "$REF" =~ ^[0-9a-f]{7,40}$ ]]; then printf 'https://github.com/%s/%s/archive/%s.tar.gz' "$o" "$n" "$REF"
    elif [[ "$REF" =~ ^v[0-9] ]]; then printf 'https://github.com/%s/%s/archive/refs/tags/%s.tar.gz' "$o" "$n" "$REF"
    else printf 'https://github.com/%s/%s/archive/refs/heads/%s.tar.gz' "$o" "$n" "$REF"; fi
  elif [[ "$REPO" =~ ^(https?://|git@)gitlab\.com[/:]([^/]+)/([^/]+)$ ]]; then
    printf 'https://gitlab.com/%s/%s/-/archive/%s/%s-%s.tar.gz' "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "$REF" "${BASH_REMATCH[3]}" "$REF"
  fi
}

say "Downloading EA Explorer $REF from $REPO into $FOLDER ..."
if command -v git >/dev/null 2>&1 && [ -z "${EAX_NO_GIT:-}" ] && [ -z "${EAX_ARCHIVE_URL:-}" ]; then
  METHOD="git clone --depth 1"
  git clone --quiet --depth 1 --branch "$REF" "$REPO" "$FOLDER" 2>/dev/null || {
    # a commit is not a branch: fetch that one commit
    git -C "$FOLDER" init -q && git -C "$FOLDER" remote add origin "$REPO" && git -C "$FOLDER" fetch -q --depth 1 origin "$REF" \
      && git -C "$FOLDER" checkout -q FETCH_HEAD; }
else
  URL=$(archive_url)
  [ -n "$URL" ] || { say "Without git only GitHub and GitLab addresses can be downloaded (or set EAX_ARCHIVE_URL)."; rmdir "$FOLDER" 2>/dev/null || true; exit 1; }
  METHOD="archive $URL"
  tmp=$(mktemp)
  curl -fsSL "$URL" -o "$tmp" || { say "Could not download $URL"; rm -f "$tmp"; rmdir "$FOLDER" 2>/dev/null || true; exit 1; }
  tar -xzf "$tmp" -C "$FOLDER" --strip-components=1
  rm -f "$tmp"
fi

# the check: is this EA Explorer?
for f in eax.sh eaxpy.sh docker-compose.yml eaxcli/deploy.py services/api/version.toml deploy/templates/eaexplorer.server.env; do
  [ -f "$FOLDER/$f" ] || { say "The download does not look like EA Explorer ($f is missing): check the link and the version."; exit 1; }
done
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$FOLDER/services/api/version.toml" | head -1)
chmod +x "$FOLDER/eax.sh" "$FOLDER/eaxpy.sh" "$FOLDER/eax-deploy.sh" 2>/dev/null || true
mkdir -p "$FOLDER/work"
cat > "$FOLDER/work/install.json" <<EOF
{"repo": "$REPO", "channel": "$CHANNEL", "ref": "$REF", "version": "$VERSION", "method": "$METHOD", "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
say "EA Explorer $VERSION ($REF) is in $FOLDER."
if [ "$DEPLOY" = 1 ]; then
  cd "$FOLDER"
  exec bash ./eax.sh deploy ${PASS[@]+"${PASS[@]}"}
fi
say "Next: cd $FOLDER && ./eax.sh deploy"
