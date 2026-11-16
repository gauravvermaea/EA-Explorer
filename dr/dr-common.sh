#!/usr/bin/env bash
# dr-common.sh: what eax-dr.sh and eax-drill.sh share (R5.6-B2), sourced from the same folder. Each script sets INSTALL
# (the installation's folder) and LOG (its log file) before it uses these. Bash, standard tools, curl, sha256sum.

RESULTS=()      # "ok|FAILED<TAB>step<TAB>seconds<TAB>detail"
command -v sha256sum >/dev/null 2>&1 || sha256sum() { shasum -a 256 "$@"; }    # macOS

say() { printf '%s\n' "$*"; printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >>"$LOG"; }

# step "name" command...: shown as it runs, timed, kept; a step that fails stops the script (the caller's trap writes the
# report). The command runs in this shell (a function's settings stay), its output also kept for the detail.
step() {
  local name=$1; shift
  say ""; say "> $name"
  local t0=$SECONDS rc tmp last
  tmp=$(mktemp)
  "$@" > >(tee "$tmp") 2>&1 && rc=0 || rc=$?
  wait $! 2>/dev/null || true
  cat "$tmp" >>"$LOG"
  last=$(grep -v '^    ' "$tmp" | grep . | tail -n 1)
  rm -f "$tmp"
  local s=$((SECONDS - t0))
  if [ "$rc" -eq 0 ]; then
    RESULTS+=("ok	$name	$s	$last"); say "  ok   $name ($s s)${last:+: $last}"
  else
    RESULTS+=("FAILED	$name	$s	$last"); say "  FAIL $name: ${last:-exit $rc}"; exit 1
  fi
}

# eax args...: one eax command in the installation, waited for, its lines shown (indented) as they come; its JSON answer
# (when it gives one) in EAX_JSON
eax() {
  local tmp rc
  tmp=$(mktemp)
  (cd "$INSTALL" && "$BASH" ./eax.sh "$@") 2>&1 | tee "$tmp" | while IFS= read -r l; do printf '    %s\n' "$l"; done
  rc=${PIPESTATUS[0]}
  EAX_JSON=$(grep '^[[:space:]]*{' "$tmp" | tail -n 1)
  rm -f "$tmp"
  if [ "$rc" -ne 0 ]; then echo "./eax.sh $* failed: $(json_get error "$EAX_JSON" || echo "exit $rc")"; return 1; fi
}

# json_get key json: one top-level value of a JSON line (python3 when there, else a plain match for strings/numbers)
json_get() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys
d=json.loads(sys.argv[2] or "{}"); v=d.get(sys.argv[1])
if v is None or v == "": sys.exit(1)
print(" ".join(map(str, v)) if isinstance(v, list) else v)' "$1" "$2" 2>/dev/null
  else
    printf '%s' "$2" | grep -o "\"$1\": *\(\"[^\"]*\"\|[0-9.]*\)" | head -n 1 | sed 's/^[^:]*: *//; s/^"//; s/"$//' | grep .
  fi
}

# backup_whole folder: every file SHA256SUMS lists, as it says; prints how many
backup_whole() {
  local f=$1
  [ -f "$f/SHA256SUMS" ] || { echo "$f has no SHA256SUMS: not a whole infrastructure backup"; return 1; }
  local n
  n=$(grep -c . "$f/SHA256SUMS") || { echo "SHA256SUMS in $f lists no file"; return 1; }
  (cd "$f" && sha256sum --quiet -c SHA256SUMS) >/dev/null 2>&1 || { echo "a file of $f is missing or does not match its checksum"; return 1; }
  echo "$n files, each matching its checksum"
}

# code_whole folder version: a copy of EA Explorer's code (eax drill code, a pack's code/): every file CODE.sha256 lists,
# as it says, and services/api/version.toml of that version; prints how many files
code_whole() {
  local f=$1 have n
  [ -f "$f/CODE.sha256" ] || { echo "$f has no CODE.sha256: not a copy of EA Explorer's code (eax drill code makes one)"; return 1; }
  have=$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' "$f/services/api/version.toml" 2>/dev/null)
  [ -n "$have" ] || { echo "$f has no services/api/version.toml: not EA Explorer's code"; return 1; }
  [ "$have" = "$2" ] || { echo "the code is of version $have, not $2"; return 1; }
  n=$(grep -c . "$f/CODE.sha256")
  (cd "$f" && sha256sum --quiet -c CODE.sha256) >/dev/null 2>&1 || { echo "a file of the code in $f is missing or does not match its checksum"; return 1; }
  echo "$n files, each matching its checksum"
}

# release_published repo version: the version is a published (not draft) release on the repository's GitHub Releases
release_published() {
  [[ "$1" =~ github\.com[/:]([^/]+)/([^/.]+)(\.git)?/?$ ]] || { echo "$1 is not a github.com repository"; return 1; }
  local api=${EAX_GITHUB_API:-https://api.github.com} body
  body=$(curl -fsSL -H "Accept: application/vnd.github+json" "$api/repos/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/releases/tags/v$2" 2>/dev/null) \
    || { echo "v$2 is not a published release of $1 (or GitHub cannot be reached): publish it first"; return 1; }
  printf '%s' "$body" | grep -q '"draft": *true' && { echo "v$2 of $1 is still a draft: publish it first"; return 1; }
  return 0
}

# report file title result extra...: the steps as a Markdown table
report() {
  local file=$1 title=$2 result=$3; shift 3
  {
    printf '# %s\n\n**%s**\n\n' "$title" "$result"
    for x in "$@"; do printf '%s\n' "$x"; done
    printf '\n| | Step | Seconds | Detail |\n| --- | --- | --- | --- |\n'
    for r in ${RESULTS[@]+"${RESULTS[@]}"}; do IFS=$'\t' read -r a b c d <<<"$r"; printf '| %s | %s | %s | %s |\n' "$a" "$b" "$c" "${d//|//}"; done
  } >"$file"
}
