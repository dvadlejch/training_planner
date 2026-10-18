"""Remove generated build output and caches while preserving local application data."""

import os
import shutil
import stat
from pathlib import Path

CACHE_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXCLUDED_NAMES = {
    ".git",
    ".venv",
    ".venv-build",
    ".tools",
    "node_modules",
    "data",
    "build",
    "dist",
}


def is_link(path: Path) -> bool:
    """Recognize symbolic links and Windows junctions without traversing them."""
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def contains_data(path: Path) -> bool:
    """Protect data directories, SQLite files/sidecars and linked directories."""
    name = path.name.lower()
    if is_link(path) or name == "data":
        return True
    if any(
        name.endswith(extension) or f"{extension}-" in name or f"{extension}." in name
        for extension in (".db", ".sqlite", ".sqlite3")
    ):
        return True
    return path.is_dir() and any(contains_data(child) for child in path.iterdir())


def remove_generated(root: Path, path: Path) -> None:
    """Delete only verified workspace output, retaining any subtree with user data."""
    if not path.exists() and not path.is_symlink():
        return
    # Check the resolved absolute target before every recursive deletion. A link
    # resolving outside the workspace is preserved as well as links within it.
    if is_link(path):
        print(f"Preserved linked path: {path}")
        return
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"Refusing to clean outside the workspace: {resolved}")
    if contains_data(path):
        print(f"Preserved output containing data or links: {path}")
        return
    if path.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()
    print(f"Removed: {path}")


def clean(root: Path) -> None:
    """Clean build trees, frontend output and source caches without removing tools."""
    root = root.resolve(strict=True)
    for name in ("build", "dist"):
        directory = root / name
        if directory.is_dir() and not is_link(directory):
            # Keep data-bearing installations/test results intact while removing
            # their sibling intermediates, specs and installer executables.
            for child in directory.iterdir():
                remove_generated(root, child)
            if not any(directory.iterdir()):
                directory.rmdir()
    for relative in (
        "frontend/dist",
        "frontend/node_modules/.cache",
        "frontend/node_modules/.vite",
    ):
        remove_generated(root, root / relative)
    for directory_name, children, _ in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        for name in children[:]:
            child = directory / name
            if name in CACHE_NAMES:
                remove_generated(root, child)
                children.remove(name)
            elif name.lower() in EXCLUDED_NAMES or is_link(child):
                children.remove(name)


if __name__ == "__main__":
    clean(Path(__file__).resolve().parents[2])
