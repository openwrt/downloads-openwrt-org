#!/usr/bin/env python3
"""
generate-homepage.py - Generate the root index.html for the OpenWrt download
server from .versions.json.

Usage:
    generate-homepage.py /path/to/.versions.json

Generates index.html in the same directory as the given .versions.json file.
"""

import html
import json
import os
import re
import sys

STYLE_PATH = "/.style.css"
LOGO_PATH = "/.logo.svg"
LOGO_IMG = f'<img src="{LOGO_PATH}" width="48" height="58" alt="OpenWrt">'

FOOTER_HTML = (
    '<footer>Open Source Downloads supported by '
    '<a href="https://www.fastly.com/">Fastly CDN</a>.</footer>'
)

# Legacy codename releases not in .versions.json
LEGACY_RELEASES = [
    ("Chaos Calmer 15.05.1", "chaos_calmer/15.05.1/"),
    ("Chaos Calmer 15.05", "chaos_calmer/15.05/"),
    ("Barrier Breaker 14.07", "barrier_breaker/14.07/"),
    ("Attitude Adjustment 12.09", "attitude_adjustment/12.09/"),
    ("Backfire 10.03.1", "backfire/10.03.1/"),
    ("Backfire 10.03", "backfire/10.03/"),
    ("Kamikaze 8.09.2", "kamikaze/8.09.2/"),
    ("Kamikaze 8.09.1", "kamikaze/8.09.1/"),
    ("Kamikaze 8.09", "kamikaze/8.09/"),
    ("Kamikaze 7.09", "kamikaze/7.09/"),
    ("Kamikaze 7.07", "kamikaze/7.07/"),
    ("Kamikaze 7.06", "kamikaze/7.06/"),
    ("Whiterussian 0.9", "whiterussian/0.9/"),
]



def brand_name(version):
    """Return 'LEDE' for 17.01.x, 'OpenWrt' otherwise."""
    return "LEDE" if version.startswith("17.01.") else "OpenWrt"


def major_minor(version):
    """Extract major.minor from a version string like '24.10.5' -> '24.10'."""
    m = re.match(r"(\d+\.\d+)\.", version)
    return m.group(1) if m else version


def is_rc(version):
    return "-rc" in version


def version_link(version, archive=False):
    """Return (label, href) for a version."""
    label = f"{brand_name(version)} {version}"
    if archive:
        href = f"//archive.openwrt.org/releases/{version}/targets/"
    else:
        href = f"releases/{version}/targets/"
    return label, href


def group_versions_by_series(versions):
    """Group versions by major.minor series, preserving input order."""
    series = {}
    order = []
    for v in versions:
        mm = major_minor(v)
        if mm not in series:
            series[mm] = []
            order.append(mm)
        series[mm].append(v)
    return [(mm, series[mm]) for mm in order]


def generate(data):
    stable = data["stable_version"]
    upcoming = data.get("upcoming_version", "")
    all_versions = data["versions_list"]

    stable_mm = major_minor(stable)

    # Everything except the hero versions (stable, upcoming) goes to archive
    hero = {stable, upcoming} - {""}
    archive_versions = [v for v in all_versions if v not in hero]

    lines = []

    # HTML head
    lines.append(
        '<!DOCTYPE html>\n<html lang="en"><head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<link rel="stylesheet" href="{STYLE_PATH}">\n'
        '<title>OpenWrt Downloads</title></head>\n'
        '<body>\n'
    )

    # Header
    lines.append(
        '<div class="hp-header">\n'
        f'  <div class="hp-logo">{LOGO_IMG}</div>\n'
        '  <div>\n'
        '    <h1>OpenWrt Downloads</h1>\n'
        '    <p class="hp-subtitle">Firmware images, SDKs and toolchains '
        'for every supported device.</p>\n'
        '  </div>\n'
        '</div>\n'
        '<hr>'
    )

    # Stable release - hero card
    lines.append(
        '<div class="hp-cards">\n'
        '  <div class="hp-card hp-card-primary">\n'
        '    <div class="hp-card-badge">Stable</div>\n'
        f'    <h2><a href="releases/{he(stable)}/targets/">'
        f'OpenWrt {he(stable)}</a></h2>\n'
        f'    <p>The current recommended release for all users.</p>\n'
        f'    <a class="hp-btn" href="releases/{he(stable)}/targets/">Download</a>\n'
        '  </div>\n'
    )

    # Upcoming release card (if present)
    if upcoming:
        lines.append(
            '  <div class="hp-card hp-card-upcoming">\n'
            '    <div class="hp-card-badge">Upcoming</div>\n'
            f'    <h2><a href="releases/{he(upcoming)}/targets/">'
            f'OpenWrt {he(upcoming)}</a></h2>\n'
            f'    <p>Release candidate &mdash; '
            f'{he(major_minor(upcoming))} will succeed {he(stable_mm)}.</p>\n'
            f'    <a class="hp-btn hp-btn-secondary" '
            f'href="releases/{he(upcoming)}/targets/">Download RC</a>\n'
            '  </div>\n'
        )

    # Snapshots card
    lines.append(
        '  <div class="hp-card">\n'
        '    <div class="hp-card-badge">Development</div>\n'
        '    <h2><a href="snapshots/targets/">Snapshots</a></h2>\n'
        '    <p>Automated daily builds from the development master branch.</p>\n'
        '    <a class="hp-btn hp-btn-secondary" href="snapshots/targets/">Browse snapshots</a>\n'
        '  </div>\n'
        '</div>\n'
    )

    # Release archive
    if archive_versions:
        lines.append('<div class="hp-section">\n  <h3>Release Archive</h3>\n')
        lines.append(
            '  <p>Older releases &mdash; generally out of date and no longer '
            'maintained.</p>\n'
        )

        grouped = group_versions_by_series(archive_versions)
        lines.append('  <div class="hp-archive">\n')
        for mm, versions in grouped:
            # Only show final releases by default, skip RCs
            finals = [v for v in versions if not is_rc(v)]
            if not finals:
                continue
            bname = brand_name(finals[0])
            lines.append(f'    <details class="hp-series">\n')
            lines.append(
                f'      <summary>{he(bname)} {he(mm)} '
                f'<span class="hp-series-count">'
                f'{len(finals)} release{"s" if len(finals) != 1 else ""}'
                f'</span></summary>\n'
            )
            lines.append('      <ul>\n')
            for v in finals:
                label, href = version_link(v, archive=True)
                lines.append(
                    f'        <li><a href="{he(href)}">{he(label)}</a></li>\n'
                )
            lines.append('      </ul>\n    </details>\n')

        # Legacy codename releases
        lines.append('    <details class="hp-series">\n')
        lines.append(
            '      <summary>Legacy Codename Releases '
            f'<span class="hp-series-count">{len(LEGACY_RELEASES)} releases'
            '</span></summary>\n'
        )
        lines.append('      <ul>\n')
        for label, path in LEGACY_RELEASES:
            href = f"//archive.openwrt.org/{path}"
            lines.append(
                f'        <li><a href="{he(href)}">{he(label)}</a></li>\n'
            )
        lines.append('      </ul>\n    </details>\n')
        lines.append('  </div>\n</div>\n')

    lines.append(FOOTER_HTML)
    lines.append('\n</body></html>')

    return "".join(lines)


def he(s):
    """Shorthand for html.escape."""
    return html.escape(str(s))


def main():
    # Parse optional --output flag
    args = sys.argv[1:]
    output_path = None
    if "--output" in args:
        idx = args.index("--output")
        output_path = os.path.abspath(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if len(args) != 1:
        print(
            f"Usage: {sys.argv[0]} /path/to/.versions.json [--output /path/to/index.html]",
            file=sys.stderr,
        )
        sys.exit(1)

    json_path = os.path.abspath(args[0])
    if not os.path.isfile(json_path):
        print(f"Error: {json_path} is not a file", file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    content = generate(data)

    if output_path is None:
        output_path = os.path.join(os.path.dirname(json_path), "index.html")
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, output_path)


if __name__ == "__main__":
    main()
