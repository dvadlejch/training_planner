"""Launch the packaged local app, or initialize its executable-relative database."""

import argparse
import socket
import sqlite3
import sys
import webbrowser
from pathlib import Path

import uvicorn

from training_planner.api.app import create_app
from training_planner.storage.db import connect


def application_directory() -> Path:
    """Locate persistent files outside PyInstaller's bundled runtime directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def frontend_directory() -> Path:
    """Find release assets in the bundle, or a development checkout's build."""
    if getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent / "web"
    return application_directory() / "frontend" / "dist"


def initialize_database(path: Path) -> None:
    """Create missing tables without deleting or replacing existing records."""
    connection = connect(path)
    connection.close()


class BrowserServer(uvicorn.Server):
    """Open the browser only after the local server successfully starts."""

    def __init__(self, config: uvicorn.Config, open_browser: bool) -> None:
        super().__init__(config)
        self.open_browser = open_browser

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        """Announce the bound address and optionally open the calendar."""
        await super().startup(sockets=sockets)
        if self.started and sockets:
            url = f"http://127.0.0.1:{sockets[0].getsockname()[1]}"
            print(f"Training Planner: {url}\nPress Ctrl+C here to quit.", flush=True)
            if self.open_browser:
                try:
                    webbrowser.open(url)
                except webbrowser.Error:
                    print(
                        "Could not open your browser. Open the address above manually."
                    )


def main(argv: list[str] | None = None) -> int:
    """Run the local app; return a nonzero exit code for setup or launch failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-db", action="store_true", help="Initialize and exit")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    database = application_directory() / "data" / "training.db"
    try:
        # Packaged data always belongs to this installation, even if the shell has
        # TRAINING_PLANNER_DB set for an unrelated development checkout.
        initialize_database(database)
        if args.init_db:
            print(f"Database ready: {database}")
            return 0
        frontend = frontend_directory()
        if not (frontend / "index.html").is_file():
            raise OSError(
                f"Built interface missing: {frontend}. Rebuild the application."
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            # Reserving the port before startup prevents opening an unrelated app
            # in the browser when another process already owns the port.
            listener.bind(("127.0.0.1", args.port))
            config = uvicorn.Config(
                create_app(database, frontend),
                loop="asyncio",
                http="h11",
                ws="none",
                lifespan="on",
            )
            BrowserServer(config, not args.no_browser).run(sockets=[listener])
        return 0
    except (OSError, sqlite3.Error) as exc:
        print(
            f"Training Planner could not start: {exc}\n"
            f"Database: {database}\n"
            "Choose a writable installation folder. If the port is occupied, "
            "close the running app or choose another --port.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
