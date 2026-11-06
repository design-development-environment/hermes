#!/usr/bin/env python3
"""Hermes V4 file actions. Access follows the current Linux user's permissions."""

import argparse
import os
import sys
from pathlib import Path

MAX_READ_BYTES = 1_000_000


def resolve_path(value):
    return Path(value).expanduser().resolve()


def list_files(path):
    if not path.is_dir():
        sys.exit(f"Not a directory: {path}")

    try:
        for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            kind = "DIR " if item.is_dir() else "FILE"
            print(f"{kind}  {item}")
    except PermissionError:
        sys.exit(f"Permission denied: {path}")


def search_names(root, query, limit):
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    count = 0
    query = query.casefold()

    def on_error(error):
        print(f"Skipped inaccessible location: {error.filename}", file=sys.stderr)

    for current, dirs, files in os.walk(root, onerror=on_error, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
        for name in dirs + files:
            if query in name.casefold():
                print(Path(current) / name)
                count += 1
                if count >= limit:
                    print(f"Result limit reached: {limit}")
                    return

    if count == 0:
        print("No matching names found.")


def read_file(path):
    if not path.is_file():
        sys.exit(f"Not a regular file: {path}")

    size = path.stat().st_size
    if size > MAX_READ_BYTES:
        sys.exit(
            f"File is {size} bytes. Maximum per read is {MAX_READ_BYTES} bytes."
        )

    try:
        # Bound the actual read as well: a file may grow after stat().
        with path.open('rb') as stream:
            data = stream.read(MAX_READ_BYTES + 1)
        if len(data) > MAX_READ_BYTES:
            sys.exit(f"Maximum per read is {MAX_READ_BYTES} bytes.")
        print(data.decode('utf-8'), end="")
    except UnicodeDecodeError:
        sys.exit("File is not UTF-8 text; refusing to display binary content.")
    except PermissionError:
        sys.exit(f"Permission denied: {path}")


def write_file(path, content, overwrite, parents):
    existed = path.exists()
    if existed and not overwrite:
        sys.exit(f"File already exists: {path}. Use --overwrite to replace it.")

    if existed and path.is_dir():
        sys.exit(f"Cannot write to a directory: {path}")

    if not path.parent.exists():
        if parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            sys.exit(f"Parent directory does not exist: {path.parent}")

    if existed:
        print(f"WARNING: this will replace existing content: {path}")
        answer = input('Type REPLACE to confirm: ')
        if answer != "REPLACE":
            sys.exit("Cancelled.")

    # A path absent at the safety check must still use exclusive creation even
    # when --overwrite was supplied. Otherwise a racing creator could lose data.
    with path.open('w' if existed else 'x', encoding='utf-8') as stream:
        stream.write(content)
    print(f"{'Updated' if existed else 'Created'}: {path}")


def delete_file(path):
    if not path.exists() and not path.is_symlink():
        sys.exit(f"Path does not exist: {path}")

    if path.is_dir() and not path.is_symlink():
        sys.exit("Directory deletion is disabled in this version.")

    print(f"WARNING: permanently delete this path: {path}")
    answer = input('Type DELETE to confirm: ')
    if answer != "DELETE":
        sys.exit("Cancelled.")

    path.unlink()
    print(f"Deleted: {path}")


def main():
    parser = argparse.ArgumentParser(description="Hermes file actions")
    sub = parser.add_subparsers(dest="action", required=True)

    ls = sub.add_parser("list", help="List a directory")
    ls.add_argument("path", nargs="?", default="~")

    search = sub.add_parser("search", help="Search file and directory names")
    search.add_argument("root")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=100)

    read = sub.add_parser("read", help="Read a UTF-8 text file")
    read.add_argument("path")

    write = sub.add_parser("write", help="Create or update a text file")
    write.add_argument("path")
    write.add_argument("content")
    write.add_argument("--overwrite", action="store_true")
    write.add_argument("--parents", action="store_true")

    delete = sub.add_parser("delete", help="Delete a file or symlink")
    delete.add_argument("path")

    args = parser.parse_args()

    try:
        if args.action == "list":
            list_files(resolve_path(args.path))
        elif args.action == "search":
            if args.limit < 1:
                sys.exit("--limit must be at least 1")
            search_names(resolve_path(args.root), args.query, args.limit)
        elif args.action == "read":
            read_file(resolve_path(args.path))
        elif args.action == "write":
            write_file(
                resolve_path(args.path), args.content,
                args.overwrite, args.parents,
            )
        elif args.action == "delete":
            # Preserve the final symlink so deletion unlinks it, not its target.
            delete_file(Path(os.path.abspath(os.path.expanduser(args.path))))
    except PermissionError:
        sys.exit("Permission denied. No elevated permissions were attempted.")
    except OSError as exc:
        sys.exit(f"File operation failed: {exc}")


if __name__ == "__main__":
    main()
