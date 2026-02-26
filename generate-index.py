#!/usr/bin/env python3
"""
generate-index.py - Generate a static HTML directory index for an OpenWrt
download directory containing a sha256sums file.

Usage:
    generate-index.py /path/to/sha256sums

Generates index.html in the same directory as the given sha256sums file.
Intended to be called from an inotify hook or similar.
"""

import fcntl
import html
import os
import re
import sys
import time
from collections import Counter

# Static assets served from the download root as dotfiles
STYLE_PATH = "/.style.css"
LOGO_PATH = "/.logo.svg"
LOGO_IMG = f'<img src="{LOGO_PATH}" width="40" height="48" alt="OpenWrt">'

FOOTER_HTML = '<footer>Open Source Downloads supported by <a href="https://www.fastly.com/">Fastly CDN</a>.</footer>'

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
    r"index\.html$"
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


def file_info(path):
    """Return (size_str, date_str) for a file."""
    try:
        st = os.stat(path)
    except OSError:
        return "-", "-"
    date = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
    if os.path.isdir(path):
        return "-", date
    return f"{st.st_size / 1024:.1f} KB", date


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

    chk_td = f'<td class="sh" title="{checksum}">{checksum}</td>'
    return (
        f'  <tr><td class="n"><a href="{href_str}">{label}</a></td>'
        f'{chk_td}<td class="s">{size}</td><td class="d">{date}</td></tr>'
    )



def generate_target_page(directory, virt_path, entries, checksums, checktype):
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

    lines.append(FOOTER_HTML)
    lines.append("</body></html>")
    return "\n".join(lines)


def generate_directory_page(directory, virt_path, entries):
    lines = [header(virt_path)]
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
    lines.append(FOOTER_HTML)
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


def generate_for_directory(directory):
    """Generate index.html for a single directory."""
    if not directory.endswith("/"):
        directory += "/"

    lock_path = os.path.join(directory, ".index.lock")
    lock_fd = open(lock_path, "w")
    fcntl.flock(lock_fd, fcntl.LOCK_EX)

    try:
        virt_path = virt_path_for(directory)
        checktype, checksums = read_checksums(directory)
        entries = list_entries(directory, virt_path)

        if TARGET_RE.search(virt_path):
            content = generate_target_page(directory, virt_path, entries, checksums, checktype)
        else:
            content = generate_directory_page(directory, virt_path, entries)

        index_path = os.path.join(directory, "index.html")
        tmp_path = os.path.join(directory, ".index.html.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, index_path)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /path/to/sha256sums", file=sys.stderr)
        sys.exit(1)

    sha256sums_path = os.path.abspath(sys.argv[1])
    if not os.path.isfile(sha256sums_path):
        print(f"Error: {sha256sums_path} is not a file", file=sys.stderr)
        sys.exit(1)

    directory = os.path.dirname(sha256sums_path)
    generate_for_directory(directory)


if __name__ == "__main__":
    main()
