#!/usr/bin/env python3
"""Fail release builds if Host and User Debian packages own a shared path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def package_paths(package: Path) -> set[str]:
    listing = subprocess.check_output(["dpkg-deb", "--contents", str(package)], text=True)
    paths: set[str] = set()
    for line in listing.splitlines():
        if not line.startswith(("-", "l")):
            continue
        fields = line.split(maxsplit=5)
        if len(fields) == 6:
            paths.add(fields[5].rstrip("/"))
    return paths


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_deb_pair.py HOST.deb USER.deb")
    host, user = (Path(value).resolve() for value in sys.argv[1:])
    for package in (host, user):
        if not package.is_file():
            raise SystemExit(f"Missing package: {package}")
    overlap = package_paths(host) & package_paths(user)
    if overlap:
        raise SystemExit("Host/User Debian path collision: " + ", ".join(sorted(overlap)))
    print("Host/User Debian package paths are disjoint.")


if __name__ == "__main__":
    main()
