#!/usr/bin/env python3
"""Interactively delete small subfolders from the media library.

For each path in SCAN_FOLDERS, lists its immediate subfolders (one level down,
never deeper) under MAX_SIZE_BYTES as "Category > Title" with sizes, and deletes
nothing until you confirm. The scan folders themselves, anything outside them,
and symlinks are never touched. No CLI args — edit the constants and run it.
Written after an unguarded `rm -rf` cleanup once wiped the library.
"""

from __future__ import annotations

import os
import shutil
import sys

# --- Configuration ---------------------------------------------------------
# Full paths to scan; their immediate subfolders are the delete candidates.
# List only video folders — a small folder there is junk (a real film/episode
# is gigabytes), whereas small folders in books/music are normal.
SCAN_FOLDERS = [
    "/mnt/media/movies",
    "/mnt/media/tv",
    "/mnt/media/anime",
    "/mnt/media/anime-movies",
    "/mnt/media/gay",
    "/mnt/media/xmas",
]
MAX_SIZE_BYTES = 100 * 1024 * 1024               # offer subfolders smaller than this
IGNORE = {"@eaDir", "#recycle", ".Trash-1000"}   # skip these names (thumbs/recycle/trash)
# ---------------------------------------------------------------------------

# The only directories whose direct children may be deleted.
PARENTS = {os.path.realpath(p) for p in SCAN_FOLDERS}


def human(n: float) -> str:
    """Byte count as '0 B', '84.0 MB', '1.2 GB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def dir_size(path: str) -> int:
    """Bytes under path (no symlinks), stopping once over MAX_SIZE_BYTES."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass  # vanished/unreadable — skip, don't abort the scan
            if total >= MAX_SIZE_BYTES:
                return total
    return total


def crumb(path: str) -> str:
    """'Category > Title' label from a candidate path."""
    cat, title = os.path.basename(os.path.dirname(path)), os.path.basename(path)
    return f"{cat[:1].upper()}{cat[1:]} > {title}"


def is_candidate(path: str) -> bool:
    """True only for a direct child of a scan folder (never deeper, never the folder itself)."""
    return os.path.dirname(os.path.realpath(path)) in PARENTS


def scan(folder: str):
    """Yield (size, path) for each small immediate subfolder of folder."""
    with os.scandir(folder) as entries:
        for e in entries:
            if e.name not in IGNORE and e.is_dir(follow_symlinks=False):
                size = dir_size(e.path)
                if size < MAX_SIZE_BYTES:
                    yield size, e.path


def delete(path: str) -> None:
    """rmtree one subfolder, re-checking the safety rules first."""
    reason = (
        "not a scan-folder subfolder" if not is_candidate(path)
        else "is a symlink" if os.path.islink(path)
        else "no longer under threshold" if dir_size(path) >= MAX_SIZE_BYTES
        else None
    )
    if reason:
        print(f"  SKIP  {crumb(path)}  ({reason})")
        return
    try:
        shutil.rmtree(path)
        print(f"  DEL   {crumb(path)}")
    except OSError as exc:
        print(f"  FAIL  {crumb(path)}  ({exc})")


def main() -> None:
    print(f"Threshold: {human(MAX_SIZE_BYTES)}\n")
    found = []
    for folder in SCAN_FOLDERS:
        if os.path.isdir(folder):
            found.extend(scan(folder))
        else:
            print(f"  (skip — not found: {folder})")
    found.sort()
    if not found:
        print("Nothing under threshold.")
        return

    width = max(len(human(sz)) for sz, _ in found)
    for i, (sz, p) in enumerate(found, 1):
        print(f"  {i:>3}.  {human(sz):>{width}}   {crumb(p)}")

    if not sys.stdin.isatty():
        print("\nNot an interactive terminal — nothing deleted.")
        return

    choice = input("\nDelete these? [a]ll / [s]tep through each / [q]uit: ").strip().lower()
    print()
    if choice == "a":
        for _, p in found:
            delete(p)
    elif choice == "s":
        for sz, p in found:
            if input(f"Delete {human(sz)}  {crumb(p)} ? [y/N]: ").strip().lower() == "y":
                delete(p)
            else:
                print(f"  kept  {crumb(p)}")
    else:
        print("Quit — nothing deleted.")


if __name__ == "__main__":
    main()
