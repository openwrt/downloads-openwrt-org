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
DATAROOT="$DOCROOT/data"
GENROOT="$DOCROOT/generated"
TARGETDIR="$DATAROOT/releases/24.10.5/targets/mediatek/filogic"
PKGDIR="$DATAROOT/releases/24.10.5/packages/aarch64_cortex-a53/base"

# Clean previous output
rm -rf "$DOCROOT"
mkdir -p "$TARGETDIR" "$PKGDIR"

# Copy source data into the target directory
for f in "$DATADIR"/openwrt-* "$DATADIR"/config.buildinfo "$DATADIR"/feeds.buildinfo \
         "$DATADIR"/sha256sums "$DATADIR"/profiles.json; do
    [ -e "$f" ] || continue
    cp -f "$f" "$TARGETDIR/" 2>/dev/null || true
done

# Copy package data
cp -a "$DATADIR"/packages/aarch64_cortex-a53/base/* "$PKGDIR/"

# Copy static assets to the generated root (served as overlay)
mkdir -p "$GENROOT"
cp style.css "$GENROOT/.style.css"
cp openwrt_logo.svg "$GENROOT/.logo.svg"
cp search.js "$GENROOT/.search.js"

# Generate target page + parent directory pages + JSON files
python3 generate-index.py --output-root "$GENROOT" "$TARGETDIR/sha256sums"

# Generate package page + parent directory pages
python3 generate-index.py --output-root "$GENROOT" "$PKGDIR/sha256sums"

# Generate homepage
python3 generate-homepage.py --output-root "$GENROOT" "$DATADIR/.versions.json"

echo "Generated pages in $DOCROOT/"

if [ "${1:-}" = "serve" ]; then
    echo ""
    echo "Starting nginx on http://localhost:8080 ..."
    echo "Press Ctrl-C to stop."
    podman run --rm -p 8080:8080 \
        -v "$(pwd)/$GENROOT:/srv/generated:ro" \
        -v "$(pwd)/$DATAROOT:/srv/data:ro" \
        -v "$(pwd)/test-nginx.conf:/etc/nginx/nginx.conf:ro" \
        docker.io/nginx:mainline
fi
