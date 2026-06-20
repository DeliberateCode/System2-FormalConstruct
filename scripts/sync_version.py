#!/usr/bin/env python3
"""Sync the version from VERSION to every version-bearing file.

VERSION is the single source of truth (the build reads it via hatch). This
script propagates it to the plugin/overlay/marketplace manifests and to the
package's ``__version__`` string.

Usage:
  python3 scripts/sync_version.py           # write VERSION to all files
  python3 scripts/sync_version.py --check    # verify files match VERSION (CI)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
version = (ROOT / "VERSION").read_text().strip()

_PY_VERSION_RE = re.compile(r"""(__version__\s*=\s*["'])([^"']*)(["'])""")


def _json_handlers(rel, accessor, mutator):
    """Build (label, get, set) handlers for a version field in a JSON file."""
    path = ROOT / rel

    def get():
        return accessor(json.loads(path.read_text()))

    def set_():
        data = json.loads(path.read_text())
        mutator(data)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return rel, get, set_


def _python_handlers(rel):
    """Build (label, get, set) handlers for a module's ``__version__`` string."""
    path = ROOT / rel

    def get():
        match = _PY_VERSION_RE.search(path.read_text())
        return match.group(2) if match else None

    def set_():
        text = path.read_text()
        new_text, count = _PY_VERSION_RE.subn(rf"\g<1>{version}\g<3>", text, count=1)
        if count != 1:
            raise SystemExit(f"Could not find a unique __version__ in {rel}")
        path.write_text(new_text)

    return rel, get, set_


MANIFESTS = [
    _json_handlers(
        "plugin/system2.overlay.json",
        lambda d: d["version"],
        lambda d: d.update({"version": version}),
    ),
    _json_handlers(
        "plugin/.claude-plugin/plugin.json",
        lambda d: d["version"],
        lambda d: d.update({"version": version}),
    ),
    _json_handlers(
        ".claude-plugin/marketplace.json",
        lambda d: d["plugins"][0]["version"],
        lambda d: d["plugins"][0].update({"version": version}),
    ),
    _python_handlers("formalconstruct/__init__.py"),
]


if "--check" in sys.argv:
    errors = [
        f"  {label}: found {get()!r}, expected {version!r}"
        for label, get, _ in MANIFESTS
        if get() != version
    ]
    if errors:
        print(f"Version mismatch (VERSION={version!r}):")
        print("\n".join(errors))
        print("Run 'make sync-version' and commit the result.")
        sys.exit(1)
    print(f"OK: all version files consistent with VERSION ({version}).")
else:
    for _, _, set_ in MANIFESTS:
        set_()
    print(f"Synced version {version} to all version files.")
