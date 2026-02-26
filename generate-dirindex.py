#!/usr/bin/env python3
"""
generate-dirindex.py - Generate a static directory listing index.html.

Generates nginx-style autoindex XML for a directory and transforms it
through autoindex.xslt using xsltproc.  This keeps the XSLT as the
single source of truth for directory listing markup.

Usage:
    generate-dirindex.py XSLT_PATH DIRECTORY VIRTUAL_PATH
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr


def generate_xml(directory):
    """Generate nginx autoindex-compatible XML for a directory."""
    entries = sorted(os.listdir(directory))
    lines = ['<?xml version="1.0"?>', "<list>"]

    for name in entries:
        if name.startswith(".") or name == "index.html":
            continue
        full = os.path.join(directory, name)
        st = os.stat(full)
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        mtime_str = mtime.strftime("%Y-%m-%dT%H:%M:%SZ")

        if os.path.isdir(full):
            lines.append(f"<directory mtime={quoteattr(mtime_str)}>"
                         f"{escape(name)}</directory>")
        else:
            lines.append(f"<file mtime={quoteattr(mtime_str)} "
                         f"size=\"{st.st_size}\">{escape(name)}</file>")

    lines.append("</list>")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} XSLT_PATH DIRECTORY VIRTUAL_PATH",
              file=sys.stderr)
        sys.exit(1)

    xslt_path = sys.argv[1]
    directory = sys.argv[2]
    vpath = sys.argv[3]

    xml = generate_xml(directory)

    result = subprocess.run(
        ["xsltproc", "--stringparam", "path", vpath, xslt_path, "-"],
        input=xml, capture_output=True, text=True, check=True,
    )

    index_path = os.path.join(directory, "index.html")
    tmp_path = index_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)
    os.replace(tmp_path, index_path)


if __name__ == "__main__":
    main()
