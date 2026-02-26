# OpenWrt Download Page Generator

Generates static `index.html` files for the OpenWrt firmware download server
(`downloads.openwrt.org`).

## How it works

`generate-index.py` takes a path to a `sha256sums` file and generates an
`index.html` for that directory. It is designed to be called from an inotify
watcher whenever a `sha256sums` file is created or modified.

```shell
python3 generate-index.py --output-root /home/mirror/generated \
  /home/mirror/downloads/releases/24.10.5/targets/ath79/generic/sha256sums
```

The `--output-root` flag separates generated HTML/JSON from the download data
tree, so `rsync --delete` on the data directory won't remove generated pages.
Without `--output-root`, files are written alongside the data.

For **target directories** (paths matching `/targets/<arch>/<subtarget>/`), the
page splits files into "Image Files" and "Supplementary Files" tables, trims the
common filename prefix for readability, and displays sha256 checksums inline.

For **generic directories** (e.g. `/releases/24.10.5/targets/mediatek/`), it
produces a simple file listing with name, size, and date.

In addition to the target page itself, the script:
- Generates all **parent directory pages** up to the anchor directory (e.g.
  `releases/`)
- Generates **`.overview.json`** and **`.targets.json`** at the release root by
  aggregating per-target `profiles.json` files

Two HTML files are written per directory: `index.html` (for mirrors) and
`index.main.html` (for the primary server, includes a Fastly CDN footer). Nginx
is configured to prefer `index.main.html`.

## Scripts

| Script                 | Purpose                                                                  |
| ---------------------- | ------------------------------------------------------------------------ |
| `generate-index.py`    | Target pages, parent directory pages, `.overview.json`/`.targets.json`   |
| `generate-homepage.py` | Root landing page from `.versions.json`                                  |

## Requirements

- Python 3.6+ (stdlib only, no external dependencies)

## Deployment

On the production server, nginx uses a two-root overlay: generated HTML/JSON
from `/home/mirror/generated/` with a `try_files` fallback to
`/home/mirror/downloads/` for actual files. This lets `rsync --delete` manage
the data directory without affecting generated pages.

`generate-index.py` is triggered by an inotify watcher on `sha256sums` changes;
`generate-homepage.py` is triggered on `.versions.json` changes. See
`inotify-example.sh` for a sample watcher script and `nginx-snippet.conf` for
the full nginx configuration.

## Testing

```bash
./test.sh
open docs/generated/releases/24.10.5/targets/mediatek/filogic/index.html
```

`test.sh` builds a complete static site in `docs/` from the sample data in
`data/` (5 devices). The output in `docs/` is gitignored.

To test with a local nginx server:

```bash
./test.sh serve
# opens http://localhost:8080
```

## Demo

A CI workflow deploys the generated site to GitHub Pages on every push to
`staging`. Set the Pages source to "GitHub Actions" in repository settings.
