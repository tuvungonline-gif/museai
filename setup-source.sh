#!/usr/bin/env bash
# Download the reviewed upstream version into this checkout without overwriting this fork's files.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
upstream_sha="46d217189d13aeee690b6211f8a87674d70e4536"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
git -C "$temp_dir" init -q
git -C "$temp_dir" remote add origin https://github.com/huwanbin/Muse-Canvas.git
git -C "$temp_dir" fetch -q --depth 1 origin "$upstream_sha"
test "$(git -C "$temp_dir" rev-parse FETCH_HEAD)" = "$upstream_sha"
git -C "$temp_dir" archive "$upstream_sha" | tar --skip-old-files -x -C "$repo_dir"
printf 'Muse Canvas source %s installed. Set .env, then install muse2api/requirements.txt.\n' "$upstream_sha"
