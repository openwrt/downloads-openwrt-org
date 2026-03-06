#!/bin/bash

# Test script: builds the docs/ directory from data/ and source assets,
# generates index pages, and optionally starts nginx via podman.
#
# To run:
#   cd <main directory of repo>
#   ./test.sh          # generate only
#   ./test.sh serve    # generate + start nginx on http://localhost:8080

set -e
cd "$(dirname "$0")"

DATADIR="data"
DOCROOT="docs"
TARGETDIR="$DOCROOT/releases/24.10.5/targets/mediatek/filogic"

# Clean previous output
rm -rf "$DOCROOT"
mkdir -p "$TARGETDIR"

# Copy source data into the target directory
for f in "$DATADIR"/openwrt-* "$DATADIR"/config.buildinfo "$DATADIR"/feeds.buildinfo \
         "$DATADIR"/sha256sums "$DATADIR"/profiles.json; do
    [ -e "$f" ] || continue
    cp -f "$f" "$TARGETDIR/" 2>/dev/null || true
done

# Place .overview.json at the release level
cp -f "$DATADIR/.overview.json" "$DOCROOT/releases/24.10.5/.overview.json"

# Copy static assets to the document root
cp style.css "$DOCROOT/.style.css"
cp openwrt_logo.svg "$DOCROOT/.logo.svg"
cp autoindex.xslt "$DOCROOT/.autoindex.xslt"
cp search.js "$DOCROOT/.search.js"

# Generate pages
python3 generate-index.py "$TARGETDIR/sha256sums"
python3 generate-homepage.py "$DATADIR/.versions.json" --output "$DOCROOT/index.html"

# Generate directory listings for intermediate directories
# (on the real server nginx+xslt handles these, but for static hosting we need HTML)
python3 generate-dirindex.py autoindex.xslt "$DOCROOT/releases" /releases/
python3 generate-dirindex.py autoindex.xslt "$DOCROOT/releases/24.10.5" /releases/24.10.5/
python3 generate-dirindex.py autoindex.xslt "$DOCROOT/releases/24.10.5/targets" /releases/24.10.5/targets/
python3 generate-dirindex.py autoindex.xslt "$DOCROOT/releases/24.10.5/targets/mediatek" /releases/24.10.5/targets/mediatek/

echo "Generated pages in $DOCROOT/"

if [ "${1:-}" = "serve" ]; then
    echo ""
    echo "Starting nginx on http://localhost:8080 ..."
    echo "Press Ctrl-C to stop."
    podman run --rm -p 8080:8080 \
        -v "$(pwd)/$DOCROOT:/srv:ro" \
        -v "$(pwd)/test-nginx.conf:/etc/nginx/nginx.conf:ro" \
        docker.io/nginx:mainline
fi
