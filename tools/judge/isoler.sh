#!/usr/bin/env bash
# Runs a command in the judge's container (tools/judge/Dockerfile.base), without network, on a disposable
# work folder: this is how the CI runs everything that executes the PR's code (original tests,
# differential tests, fuzzing). The same protections as tools/judge/judge.py: network cut, read-only
# file system, no privilege, user 65534. The only visible folder is <workdir>, mounted on
# /travail; the host never runs again anything the container leaves there.
#
# Usage: tools/judge/isoler.sh <image> <workdir> [--pids N] [--memoire M] -- <command> [arguments…]
#   <image>    the image's label (python3 tools/judge/judge.py --tooling <base> --image-only)
#   <workdir>  work folder; prepare it with fresh COPIES (cp -a base pr …) for each
#              step: a previous step may have written anything there.
# The exit code is the command's.
set -euo pipefail

if [ $# -lt 4 ]; then
  sed -n '2,14p' "$0" >&2
  exit 2
fi
image="$1"
travail="$(cd "$2" && pwd)"
shift 2
pids=512
memoire=6g
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  case "$1" in
    --pids) pids="$2"; shift 2 ;;
    --memoire) memoire="$2"; shift 2 ;;
    *) echo "isoler.sh: unknown option: $1" >&2; exit 2 ;;
  esac
done
[ "${1:-}" = "--" ] || { echo "isoler.sh: « -- » expected before the command" >&2; exit 2; }
shift

# The container runs as user 65534: it must be able to write in its work copy.
chmod -R a+rwX "$travail"
exec docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --pids-limit "$pids" --memory "$memoire" --memory-swap "$memoire" \
  --tmpfs /tmp:rw,noexec,nosuid,size=1g -e HOME=/tmp -e LC_ALL=C.UTF-8 \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  --mount "type=bind,source=$travail,target=/travail" -w /travail \
  "$image" "$@"
