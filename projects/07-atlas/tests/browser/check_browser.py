"""Run optional Chromium/axe checks against a disposable, synthetic local index."""

import os
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import uvicorn

from pp_atlas import Document, Engine, Principal
from pp_atlas.api import Identity, create_app


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="atlas-browser-") as root:
        engine = Engine(root)
        engine.upsert_many(
            "docs",
            [
                Document(
                    f"runbooks/{number:02d}",
                    f"Recovery procedure {number + 1:02d}",
                    "WAL recovery replays committed records. <img src=x onerror=alert(1)>",
                    metadata={"type": "runbook"},
                )
                for number in range(23)
            ]
            + [Document("private", "Restricted incident", "hidden", frozenset({"user:admin"}))],
        )
        app = create_app(engine, {"synthetic-reader-token": Identity(Principal("docs", "reader"))})
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]})
            thread.start()
            try:
                environment = {**os.environ, "ATLAS_BROWSER_URL": f"http://127.0.0.1:{port}"}
                subprocess.run(
                    ["node", str(Path(__file__).with_name("search.cjs"))],
                    env=environment,
                    check=True,
                    timeout=120,
                )
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                if thread.is_alive():
                    raise RuntimeError("browser test server did not stop")


if __name__ == "__main__":
    main()
