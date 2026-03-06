# OpenWrt Download Page Generator

Generates static `index.html` files for the OpenWrt firmware download server
(`downloads.openwrt.org`).

## How it works

`generate-index.py` takes a path to a `sha256sums` file and generates an
`index.html` in the same directory. It is designed to be called from an external
inotify watcher whenever a `sha256sums` file is created or modified.

```shell
python3 generate-index.py /home/mirror/downloads/releases/24.10.5/targets/ath79/generic/sha256sums
```

For **target directories** (paths matching `/targets/<arch>/<subtarget>/`), the
page splits files into "Image Files" and "Supplementary Files" tables, trims the
common filename prefix for readability, and displays sha256 checksums inline.

For **generic directories**, it produces a simple file listing with name, size,
and date.

## Scripts

| Script                 | Purpose                                                             |
| ---------------------- | ------------------------------------------------------------------- |
| `generate-index.py`    | Target page — image/supplementary file tables with sha256 checksums |
| `generate-homepage.py` | Root landing page from `.versions.json`                             |
| `generate-dirindex.py` | Directory listings via `xsltproc` + `autoindex.xslt`                |

## Requirements

- Python 3.6+ (stdlib only, no external dependencies)
- `xsltproc` (for directory listing pages)

## Deployment

On the production server, nginx serves the download tree directly.
`generate-index.py` is triggered by an inotify watcher on `sha256sums` changes;
`generate-homepage.py` is triggered on `.versions.json` changes. Intermediate
directories use nginx autoindex with `autoindex.xslt` for styled listings.

See `nginx-snippet.conf` for the full nginx configuration.

## Testing

```bash
./test.sh
open docs/releases/24.10.5/targets/mediatek/filogic/index.html
```

`test.sh` builds a complete static site in `docs/` from the sample data in
`data/` (5 devices). It runs all three generators and uses `xsltproc` with
`autoindex.xslt` for intermediate directory pages. The output in `docs/` is
gitignored.

## Demo

A CI workflow deploys the generated site to GitHub Pages on every push to
`staging`. Set the Pages source to "GitHub Actions" in repository settings.
