#!/usr/bin/env python3
"""
generate-index.py - Generate a static HTML directory index for an OpenWrt
download directory containing a sha256sums file.

Usage:
    generate-index.py [--output-root DIR] /path/to/sha256sums

Generates index.html alongside the sha256sums file, or under --output-root
if specified.  Intended to be called from an inotify hook or similar.
"""

import fcntl
import html
import json
import os
import re
import sys
import time
from collections import Counter

# When set via --output-root, generated files (HTML, JSON) go to
# OUTPUT_ROOT/<virt_path>/ instead of alongside the source data.  Keeps
# generated output separate from the rsync-managed download tree so
# rsync --delete won't remove them.
OUTPUT_ROOT = ""

# Static assets served from the download root as dotfiles
BASE_URL = os.environ.get("BASE_URL", "")
STYLE_PATH = f"{BASE_URL}/.style.css"
LOGO_PATH = f"{BASE_URL}/.logo.svg"
SEARCH_PATH = f"{BASE_URL}/.search.js"
LOGO_IMG = f'<img src="{LOGO_PATH}" width="40" height="48" alt="OpenWrt">'

FOOTER_MAIN_HTML = '<footer>Open Source Downloads supported by <a href="https://www.fastly.com/">Fastly CDN</a>.</footer>'

COPY_SCRIPT = """<script>
function copyHash(el){var h=el.parentNode.title;if(!h||h==='-')return;
navigator.clipboard.writeText(h).then(function(){
el.dataset.orig=el.textContent;el.textContent='Copied!';
setTimeout(function(){el.textContent=el.dataset.orig},1500)})}</script>"""

# Metafile patterns for target directories
METAFILE_RE = re.compile(
    r"packages|config\.seed|\.buildinfo|manifest|"
    r"lede-imagebuilder|lede-sdk|"
    r"[Oo]pen[Ww]rt-[Ii]mage[Bb]uilder|[Oo]pen[Ww]rt-[Ss][Dd][Kk]|"
    r"[Oo]pen[Ww]rt-[Tt]oolchain|"
    r"md5sums|sha256sums"
)

HIDDEN_RE = re.compile(
    r"^/releases/\d\d\.\d\d-SNAPSHOT/?$|"
    r"^/releases/faillogs/?$|"
    r"^/packages-\d\d\.\d\d/?$|"
    r"/\.[^/]+$|"
    r"index(\.main)?\.html$"
)

TARGET_RE = re.compile(
    r"/targets/[^/]+/[^/]+/?$|"
    r"/(backfire|kamikaze)/[^/]+/[^/]+/?$|"
    r"/(attitude_adjustment|barrier_breaker|chaos_calmer)/[^/]+/[^/]+/[^/]+/?$"
)


def read_checksums(directory):
    """Read sha256sums (or md5sums fallback), return (type_label, {name: hash})."""
    sums = {}
    for name, label in [("sha256sums", "sha256sum"), ("md5sums", "md5sum")]:
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                m = re.match(r"^([a-f0-9]+) [* ](.+)$", line)
                if m:
                    sums[m.group(2)] = m.group(1)
                    continue
                m = re.match(r"^SHA256\((.+)\)= ([a-f0-9]+)$", line)
                if m:
                    sums[m.group(1)] = m.group(2)
        if sums:
            return label, sums
    return "sha256sum", {}


def find_prefix(entries, virt_path):
    """Find the most common image filename prefix based on target/subtarget."""
    m = re.search(r"/([^0-9][^/]+)/([^/]+)/?$", virt_path)
    if m:
        target, subtarget = m.group(1), m.group(2)
    else:
        m = re.search(r"/([^/]+)/?$", virt_path)
        target = m.group(1) if m else ""
        subtarget = ""

    prefixes = Counter()
    for entry in entries:
        base = os.path.basename(entry)
        if subtarget:
            i = base.find(f"-{target}-{subtarget}-")
            if i > 0:
                prefixes[base[: i + len(f"-{target}-{subtarget}-")]] += 1
                continue
        i = base.find(f"-{target}-")
        if i > 0:
            prefixes[base[: i + len(f"-{target}-")]] += 1

    prefix = prefixes.most_common(1)[0][0] if prefixes else ""
    tuple_name = f"{target}/{subtarget}" if subtarget else target
    return prefix, tuple_name


def format_size(nbytes):
    """Format bytes into human-readable size."""
    if nbytes >= 1073741824:
        return f"{nbytes / 1073741824:.1f} GB"
    if nbytes >= 1048576:
        return f"{nbytes / 1048576:.1f} MB"
    if nbytes >= 1024:
        return f"{nbytes / 1024:.1f} KB"
    return f"{nbytes} B"


def file_info(path):
    """Return (size_str, date_str) for a file."""
    try:
        st = os.stat(path)
    except OSError:
        return "-", "-"
    date = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
    if os.path.isdir(path):
        return "-", date
    return format_size(st.st_size), date


def breadcrumb(virt_path):
    parts = [p for p in virt_path.split("/") if p]
    if not parts:
        return f'{LOGO_IMG} Index of <a href="/"><em>(root)</em></a> /'

    pieces = []
    for i, part in enumerate(parts):
        href = "/" + "/".join(parts[: i + 1]) + "/"
        pieces.append(f'<a href="{href}">{html.escape(part)}</a>')

    root = '<a href="/"><em>(root)</em></a>'
    return f"{LOGO_IMG} Index of {root} / {' / '.join(pieces)} /"


def header(virt_path):
    return (
        f"<!DOCTYPE html>\n<html><head>\n"
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<link rel="stylesheet" href="{STYLE_PATH}">\n'
        f"<title>Index of {html.escape(virt_path)}</title></head>\n"
        f"<body>\n<h1>{breadcrumb(virt_path)}</h1>\n<hr>"
    )


def row(name, is_dir, checksum, size, date):
    """Render one <tr>. name is the displayed label, href is always the full basename."""
    return row_with_href(name, name, is_dir, checksum, size, date)


def row_with_href(display, href, is_dir, checksum, size, date):
    if is_dir:
        href_str = html.escape(href) + "/"
        label = html.escape(display) + "/"
        size = "-"
        checksum = "-"
    else:
        href_str = html.escape(href)
        label = html.escape(display)

    if checksum and checksum != "-":
        chk_td = (
            f'<td class="sh" title="{checksum}">'
            f'<span class="chk" onclick="copyHash(this)">{checksum}</span></td>'
        )
    else:
        chk_td = f'<td class="sh">-</td>'
    return (
        f'  <tr><td class="n"><a href="{href_str}">{label}</a></td>'
        f'{chk_td}<td class="s">{size}</td><td class="d">{date}</td></tr>'
    )



def generate_target_page(directory, virt_path, entries, checksums, checktype, footer=""):
    prefix, tuple_name = find_prefix(entries, virt_path)

    images, metas = [], []
    for e in entries:
        base = os.path.basename(e)
        if prefix and base.startswith(prefix) and not METAFILE_RE.search(base):
            images.append(e)
        else:
            metas.append(e)

    lines = [header(virt_path)]

    lines.append(
        f"  <h2>Image Files</h2>\n"
        f"  <p>These are the image files for the <b>{html.escape(tuple_name)}</b> target.\n"
        f"  Check that the {checktype} of the file you downloaded matches the {checktype} below.<br/>\n"
        f"  <i>Shortened image file names below have the same prefix: "
        f"<code>{html.escape(prefix)}...</code></i></p>"
    )

    lines.append("<table>")
    lines.append(
        f'  <tr><th class="n">Image for your Device</th><th class="sh">{checktype}</th>'
        f'<th class="s">File Size</th><th class="d">Date</th></tr>'
    )
    for e in images:
        base = os.path.basename(e)
        size, date = file_info(e)
        display = base[len(prefix):] if prefix and base.startswith(prefix) else base
        chk = checksums.get(base, "-")
        lines.append(row_with_href(display, base, os.path.isdir(e), chk, size, date))
    lines.append("</table>")

    lines.append(
        f"  <h2>Supplementary Files</h2>\n"
        f"  <p>These are supplementary resources for the <b>{html.escape(tuple_name)}</b> target.\n"
        f"  They include build tools, the imagebuilder, {checktype}, GPG signature file, "
        f"and other useful files.</p>"
    )

    lines.append("<table>")
    lines.append(
        f'  <tr><th class="n">Filename</th><th class="sh">{checktype}</th>'
        f'<th class="s">File Size</th><th class="d">Date</th></tr>'
    )
    for e in metas:
        base = os.path.basename(e)
        size, date = file_info(e)
        chk = checksums.get(base, "-")
        lines.append(row_with_href(base, base, os.path.isdir(e), chk, size, date))
    lines.append("</table>")

    if footer:
        lines.append(footer)
    lines.append(COPY_SCRIPT)
    lines.append("</body></html>")
    return "\n".join(lines)


SEARCH_HTML = (
    '<div id="device-search" hidden>'
    '<input id="ds-input" type="text" placeholder="Search for your device (e.g. Archer C7, GL-MT6000)...">'
    '<p id="ds-status" hidden></p>'
    '<div id="ds-results"></div>'
    '</div>'
)


def generate_directory_page(directory, virt_path, entries, footer=""):
    lines = [header(virt_path)]
    if virt_path.rstrip("/").endswith("/targets"):
        lines.append(SEARCH_HTML)
    lines.append("<table>")
    lines.append(
        '  <tr><th class="n">File Name</th>'
        '<th class="s">File Size</th><th class="d">Date</th></tr>'
    )
    for e in entries:
        base = os.path.basename(e)
        size, date = file_info(e)
        is_dir = os.path.isdir(e)
        if is_dir:
            lines.append(
                f'  <tr><td class="n"><a href="{html.escape(base)}/">'
                f"{html.escape(base)}/</a></td>"
                f'<td class="s">-</td><td class="d">{date}</td></tr>'
            )
        else:
            lines.append(
                f'  <tr><td class="n"><a href="{html.escape(base)}">'
                f"{html.escape(base)}</a></td>"
                f'<td class="s">{size}</td><td class="d">{date}</td></tr>'
            )
    lines.append("</table>")
    if footer:
        lines.append(footer)
    if virt_path.rstrip("/").endswith("/targets"):
        lines.append(f'<script src="{SEARCH_PATH}"></script>')
    lines.append("</body></html>")
    return "\n".join(lines)


def list_entries(directory, virt_path):
    """List visible entries, dirs first, then alphabetical."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []

    entries = []
    for name in names:
        if name in (".", ".."):
            continue
        if HIDDEN_RE.search(virt_path + name):
            continue
        entries.append(os.path.join(directory, name))

    entries.sort(key=lambda e: (not os.path.isdir(e), os.path.basename(e).lower()))
    return entries


def virt_path_for(directory):
    """Derive the virtual URL path from a physical directory path."""
    parts = directory.rstrip("/").split("/")
    virt_start = 0
    for i, p in enumerate(parts):
        if p in ("releases", "snapshots", "backfire", "kamikaze",
                 "attitude_adjustment", "barrier_breaker", "chaos_calmer"):
            virt_start = i
            break
    return "/" + "/".join(parts[virt_start:]) + "/"


def output_dir_for(source_dir):
    """Map a source directory to its output directory.

    When OUTPUT_ROOT is set, output goes to OUTPUT_ROOT/<virt_path>.
    Otherwise, output goes alongside the source data.
    """
    if not OUTPUT_ROOT:
        return source_dir
    virt = virt_path_for(source_dir)
    return os.path.join(OUTPUT_ROOT, virt.strip("/"))


def atomic_write(out_dir, filename, content):
    """Atomically write a file, creating directories as needed."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def generate_for_directory(directory):
    """Generate index.html and index.main.html for a single directory."""
    if not directory.endswith("/"):
        directory += "/"

    virt_path = virt_path_for(directory)
    checktype, checksums = read_checksums(directory)
    entries = list_entries(directory, virt_path)

    if TARGET_RE.search(virt_path):
        gen = lambda f="": generate_target_page(directory, virt_path, entries, checksums, checktype, footer=f)
    else:
        gen = lambda f="": generate_directory_page(directory, virt_path, entries, footer=f)

    out_dir = output_dir_for(directory)
    atomic_write(out_dir, "index.html", gen())
    atomic_write(out_dir, "index.main.html", gen(FOOTER_MAIN_HTML))


ANCHOR_DIRS = {"releases", "snapshots", "backfire", "kamikaze",
               "attitude_adjustment", "barrier_breaker", "chaos_calmer"}


def find_release_root(directory):
    """Find the release root and anchor directory from a target directory path.

    For /home/mirror/downloads/releases/24.10.5/targets/mediatek/filogic/
    returns ("/home/mirror/downloads/releases/24.10.5",
             "/home/mirror/downloads/releases")

    For snapshots, the release root IS the anchor dir.
    """
    parts = os.path.realpath(directory).rstrip("/").split("/")
    for i, p in enumerate(parts):
        if p in ANCHOR_DIRS:
            anchor = "/".join(parts[:i + 1])
            if p in ("releases",):
                # release root is one level deeper: releases/<version>/
                if i + 1 < len(parts):
                    return "/".join(parts[:i + 2]), anchor
            elif p in ("snapshots",):
                return anchor, anchor
            else:
                # legacy codenames: codename/<version>/
                if i + 1 < len(parts):
                    return "/".join(parts[:i + 2]), anchor
            return anchor, anchor
    return None, None


def generate_parent_pages(directory, release_root, anchor_dir):
    """Walk up from directory's parent to anchor_dir, regenerating dir pages."""
    directory = os.path.realpath(directory).rstrip("/")
    release_root = os.path.realpath(release_root).rstrip("/")
    anchor_dir = os.path.realpath(anchor_dir).rstrip("/")

    current = os.path.dirname(directory)
    while len(current) >= len(anchor_dir) and current.startswith(anchor_dir):
        generate_for_directory(current)
        if current == anchor_dir:
            break
        current = os.path.dirname(current)


def atomic_write_json(out_dir, filename, data):
    """Atomically write a JSON file."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def generate_json_files(release_root):
    """Generate .targets.json and .overview.json from profiles.json files."""
    targets_dir = os.path.join(release_root, "targets")
    if not os.path.isdir(targets_dir):
        return

    profiles_data = []
    for arch in sorted(os.listdir(targets_dir)):
        arch_dir = os.path.join(targets_dir, arch)
        if not os.path.isdir(arch_dir):
            continue
        for subtarget in sorted(os.listdir(arch_dir)):
            pj = os.path.join(arch_dir, subtarget, "profiles.json")
            if not os.path.isfile(pj):
                continue
            try:
                with open(pj, encoding="utf-8") as f:
                    profiles_data.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue

    if not profiles_data:
        return

    # .targets.json: {target: arch_packages}
    targets = {}
    for pd in profiles_data:
        targets[pd["target"]] = pd["arch_packages"]

    # .overview.json: {release, profiles: [{id, titles, target}]}
    overview = {
        "release": profiles_data[0]["version_number"],
        "profiles": [],
    }
    for pd in profiles_data:
        target = pd["target"]
        for pid, pdata in pd.get("profiles", {}).items():
            overview["profiles"].append({
                "id": pid,
                "titles": pdata.get("titles", []),
                "target": target,
            })

    out_dir = output_dir_for(release_root)
    atomic_write_json(out_dir, ".targets.json", targets)
    atomic_write_json(out_dir, ".overview.json", overview)


def main():
    global OUTPUT_ROOT

    args = sys.argv[1:]
    if "--output-root" in args:
        idx = args.index("--output-root")
        OUTPUT_ROOT = os.path.abspath(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if len(args) != 1:
        print(f"Usage: {sys.argv[0]} [--output-root DIR] /path/to/sha256sums",
              file=sys.stderr)
        sys.exit(1)

    sha256sums_path = os.path.abspath(args[0])
    if not os.path.isfile(sha256sums_path):
        print(f"Error: {sha256sums_path} is not a file", file=sys.stderr)
        sys.exit(1)

    directory = os.path.dirname(sha256sums_path)

    # Find release root for locking and parent page generation
    release_root, anchor_dir = find_release_root(directory)

    # Single lock per release serializes concurrent inotify events
    lock_fd = None
    if release_root:
        lock_dir = output_dir_for(release_root)
        os.makedirs(lock_dir, exist_ok=True)
        lock_path = os.path.join(lock_dir, ".lock")
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

    try:
        # 1. Generate the target page
        generate_for_directory(directory)

        if release_root:
            # 2. Regenerate parent directory pages
            generate_parent_pages(directory, release_root, anchor_dir)

            # 3. Generate .overview.json and .targets.json
            generate_json_files(release_root)
    finally:
        if lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()


if __name__ == "__main__":
    main()
