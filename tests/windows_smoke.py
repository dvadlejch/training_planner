"""Smoke-test a real Windows bundle without modifying its distribution folder.

Run with: python tests/windows_smoke.py dist/TrainingPlanner
Only the standard library is needed, so package builds need no test dependencies.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen


def smoke_test(package: Path) -> None:
    """Verify packaged assets, API writes, database location and repeated setup.

    Copy to a path with spaces and launch from an unrelated working directory.
    Set a conflicting development database override to ensure installation data
    cannot be redirected. All runtime data stays in the temporary copy.
    """
    if (package / "data").exists():
        raise RuntimeError("A distribution must not contain runtime data.")
    with tempfile.TemporaryDirectory(prefix="Training Planner smoke ") as temporary:
        root = Path(temporary)
        installation = root / "selected destination"
        shutil.copytree(package, installation)
        executable = installation / "TrainingPlanner.exe"
        database = installation / "data" / "training.db"
        environment = {**os.environ, "TRAINING_PLANNER_DB": str(root / "wrong.db")}
        subprocess.run(
            [str(executable), "--init-db"],
            cwd=root,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True,
            timeout=30,
        )
        if not database.is_file() or (root / "wrong.db").exists():
            raise RuntimeError("Database was not created beside the executable.")
        log = root / "server.log"
        with log.open("w") as output:
            process = subprocess.Popen(
                [str(executable), "--no-browser", "--port", "0"],
                cwd=root,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 30
                while True:
                    content = log.read_text()
                    match = re.search(
                        r"Training Planner: (http://127\.0\.0\.1:\d+)", content
                    )
                    if match:
                        url = match[1]
                        break
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(
                            f"Packaged server failed to start:\n{content}"
                        )
                    time.sleep(0.1)
                with urlopen(f"{url}/api/health", timeout=5) as response:
                    assert json.load(response) == {"status": "ok"}
                with urlopen(url, timeout=5) as response:
                    html = response.read().decode()
                    assert '<div id="root">' in html
                assets = re.findall(r'(?:src|href)="(/assets/[^"\s]+)"', html)
                assert assets, "No built frontend assets referenced by index.html"
                for asset in assets:
                    with urlopen(url + asset, timeout=5) as response:
                        assert response.status == 200
                request = Request(
                    f"{url}/api/sessions",
                    data=json.dumps(
                        {"day": date.today().isoformat(), "activity": "gym"}
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=5) as response:
                    assert response.status == 201
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
        subprocess.run(
            [str(executable), "--init-db"],
            cwd=root,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True,
            timeout=30,
        )
        connection = sqlite3.connect(database)
        try:
            assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
        finally:
            connection.close()
        assert not (root / "wrong.db").exists()
    print("Windows bundle smoke test passed.")


if __name__ == "__main__":
    smoke_test(Path(sys.argv[1]).resolve())
