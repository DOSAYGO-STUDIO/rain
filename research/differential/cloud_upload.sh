#!/usr/bin/env bash
# Credentials come exclusively from the caller's SSH configuration/agent.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo 'Usage: cloud_upload.sh SSH_HOST_ALIAS [NCPU]' >&2
  exit 2
fi
host=$1
ncpu=${2:-32}
[[ "$host" =~ ^[a-zA-Z0-9_@.:-]+$ && "$host" != -* ]] || exit 2
[[ "$ncpu" =~ ^[1-9][0-9]*$ ]] || exit 2
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bundle=$(mktemp -t rain-cloud.XXXXXXXX)
trap 'rm -f -- "$bundle"' EXIT
python3 "$here/cloud_bundle.py" "$bundle"
remote="rain-smhasher3-$(date -u +%Y%m%dT%H%M%SZ)-$$"
ssh "$host" "mkdir -m 700 '$remote'"
scp "$bundle" "$host:$remote/bundle.tar.gz"
ssh "$host" "cd '$remote' && tar xzf bundle.tar.gz && python3 -c 'import subprocess; log=open(\"build-and-run.log\", \"w\"); p=subprocess.Popen([\"bash\", \"cloud_build.sh\", \"$ncpu\"], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True); print(\"Remote build/run PID:\", p.pid)'"
echo "Remote directory: $remote"
echo "Inspect build-and-run.log and results/ there. Copy results off before the VM is deleted."
