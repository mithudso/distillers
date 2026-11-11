#!/usr/bin/env python3
"""Archive older workflow-log sections; refuse while an editor swap file exists."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 200_000


def atomic_write(path: Path, text: str, before_replace=None) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        tmp = Path(out.name)
        try:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        if before_replace is not None:
            before_replace()
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def check_swaps(root: Path) -> None:
    for name in ("memory.md", "prompts.md"):
        if any(root.glob(f".{name}.sw?")) or any(root.glob(f"{name}.sw?")):
            raise ValueError(f"refusing rotation: active editor swap for {name}")


def version_starts(text: str) -> list[int]:
    starts, offset, fence_char, fence_length = [], 0, None, 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_length = marker[0], len(marker)
            elif (marker[0] == fence_char and len(marker) >= fence_length
                  and not line[fence.end():].strip()):
                fence_char, fence_length = None, 0
        elif fence_char is None and re.fullmatch(r"## (?:Prompt )?v\d+(?:\.\d+)*(?: -[^\n]*)?", line.rstrip("\r\n")):
            starts.append(offset)
        offset += len(line)
    return starts


def rotate(root: Path, limit: int = LIMIT) -> list[str]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    check_swaps(root)
    rotated = []
    for name in ("memory.md", "prompts.md"):
        path = root / name
        if not path.exists() or path.stat().st_size <= limit:
            continue
        if path.is_symlink():
            raise ValueError(f"refusing rotation of symlink: {name}")
        text = path.read_text(encoding="utf-8")
        identity = path.stat()
        starts = version_starts(text)
        if len(starts) < 2:
            raise ValueError(f"{name} has no older version section to rotate")
        header, latest = text[:starts[0]], text[starts[-1]:]
        archive_dir = root / "docs" / "archive"
        if not archive_dir.resolve().is_relative_to(root.resolve()):
            raise ValueError("archive directory must remain inside the repository")
        check_swaps(root)
        archive_dir.mkdir(parents=True, exist_ok=True)
        # Preserve the complete original inode: even a late append remains archived.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=path.stem + "-", suffix=".md", dir=archive_dir, delete=False) as out:
            archive = Path(out.name)
        archive.unlink()
        os.link(path, archive)

        def unchanged():
            check_swaps(root)
            current = path.stat()
            if ((current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino)
                    or path.read_text(encoding="utf-8") != text):
                raise ValueError(f"{name} changed during rotation; original snapshot retained")

        atomic_write(path, header + latest, before_replace=unchanged)
        rotated.append(str(archive.relative_to(root)))
    return rotated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        result = rotate(ROOT)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print("Archived: " + ", ".join(result) if result else "Workflow logs are below the rotation limit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
