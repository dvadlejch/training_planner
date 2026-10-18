"""Verify build cleanup never removes installation data or development dependencies."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from training_planner.clean import clean, remove_generated


def write_file(root: Path, relative: str) -> Path:
    """Create a representative artifact or protected file in a temporary workspace."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test contents")
    return path


def test_clean_removes_generated_output_and_caches(tmp_path):
    """Cleanup removes bundles, installers, intermediate files and frontend caches."""
    generated = [
        "build/pyinstaller/TrainingPlanner/Analysis-00.toc",
        "build/TrainingPlanner.spec",
        "dist/TrainingPlanner/TrainingPlanner.exe",
        "dist/TrainingPlanner-Setup-0.1.0.exe",
        "frontend/dist/assets/app.js",
        "frontend/node_modules/.cache/tsconfig.tsbuildinfo",
        "frontend/node_modules/.vite/deps.json",
        "src/training_planner/__pycache__/app.pyc",
        ".pytest_cache/state",
        ".ruff_cache/state",
        ".mypy_cache/state",
    ]
    for relative in generated:
        write_file(tmp_path, relative)
    clean(tmp_path)
    assert all(not (tmp_path / relative).exists() for relative in generated)
    assert not (tmp_path / "build").exists()
    assert not (tmp_path / "dist").exists()
    clean(tmp_path)


def test_clean_preserves_data_and_used_application_folders(tmp_path):
    """Data-bearing bundles and installer test folders survive alongside source data.

    A user may have launched a packaged executable directly from dist. Preserve
    that entire installation, while still deleting a sibling setup executable and
    PyInstaller intermediates. SQLite sidecars must survive with the database.
    """
    protected = [
        "data/training.db",
        "data/training.db-wal",
        "dist/TrainingPlanner/data/training.db",
        "dist/TrainingPlanner/TrainingPlanner.exe",
        "build/installer smoke/selected destination/data/training.db",
        "build/installer smoke/server.log",
        "dist/custom-database.sqlite3",
        "dist/custom-database.sqlite3-shm",
    ]
    for relative in protected:
        write_file(tmp_path, relative)
    artifact = write_file(tmp_path, "dist/TrainingPlanner-Setup-0.1.0.exe")
    intermediate = write_file(tmp_path, "build/pyinstaller/build.toc")
    clean(tmp_path)
    assert all(
        (tmp_path / relative).read_text() == "test contents" for relative in protected
    )
    assert not artifact.exists()
    assert not intermediate.exists()


def test_clean_preserves_source_tools_and_installed_dependencies(tmp_path):
    """Source, Git metadata, downloaded tools and environments remain available."""
    protected = [
        "src/training_planner/app.py",
        "installer/windows.iss",
        "scripts/build-windows.ps1",
        ".git/config",
        ".venv/Lib/__pycache__/library.pyc",
        ".venv-build/Lib/__pycache__/library.pyc",
        ".tools/node/node.exe",
        "frontend/node_modules/react/index.js",
    ]
    for relative in protected:
        write_file(tmp_path, relative)
    clean(tmp_path)
    assert all((tmp_path / relative).is_file() for relative in protected)


def test_clean_rejects_deletion_outside_workspace(tmp_path):
    """The deletion guard refuses an absolute path outside the selected workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = write_file(tmp_path, "outside/important.txt")
    with pytest.raises(ValueError, match="outside the workspace"):
        remove_generated(workspace.resolve(), outside.parent)
    assert outside.is_file()


def test_clean_preserves_linked_output(tmp_path):
    """A link in generated output cannot cause cleanup to follow an external tree."""
    workspace = tmp_path / "workspace"
    output = workspace / "dist" / "TrainingPlanner"
    output.mkdir(parents=True)
    outside = write_file(tmp_path, "outside/important.txt")
    link = output / "linked"
    try:
        link.symlink_to(outside.parent, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or privileges")
    clean(workspace)
    assert outside.is_file()
    assert link.is_symlink()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction behavior")
@pytest.mark.parametrize("relative", ["dist/TrainingPlanner/linked", "build"])
def test_clean_preserves_windows_junctions(tmp_path, relative):
    """Cleanup preserves Windows junctions and the external trees they reference.

    Cover both a junction nested in a generated bundle and a top-level build
    directory junction. Junction creation does not need symlink privileges.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = write_file(tmp_path, "outside/important.txt")
    link = workspace / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "New-Item -ItemType Junction -Path $env:CLEAN_TEST_LINK "
            "-Target $env:CLEAN_TEST_TARGET | Out-Null",
        ],
        env={
            **os.environ,
            "CLEAN_TEST_LINK": str(link),
            "CLEAN_TEST_TARGET": str(outside.parent),
        },
        creationflags=subprocess.CREATE_NO_WINDOW,
        capture_output=True,
        check=True,
    )
    clean(workspace)
    assert outside.read_text() == "test contents"
    assert (link / "important.txt").is_file()
