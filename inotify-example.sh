#!/bin/bash
# Example inotify watcher for the OpenWrt download server.
#
# Watches for sha256sums file changes and triggers page generation.
# Generated HTML/JSON goes to a separate output root, keeping it
# independent from the rsync-managed data tree.
# Requires: inotifywait (from inotify-tools)
#
# Usage:
#   ./inotify-example.sh /home/mirror/downloads /home/mirror/generated

DOWNLOADS="${1:?Usage: $0 /path/to/downloads /path/to/generated}"
OUTPUT_ROOT="${2:?Usage: $0 /path/to/downloads /path/to/generated}"
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

inotifywait -m -r -e close_write,moved_to \
    --include 'sha256sums$' \
    "$DOWNLOADS" |
while read -r dir event file; do
    echo "[$(date -Is)] ${event}: ${dir}${file}"
    python3 "$SCRIPT_DIR/generate-index.py" --output-root "$OUTPUT_ROOT" "${dir}${file}" &
done
