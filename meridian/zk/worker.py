"""Python client for the Node proof worker (zk/js/worker.mjs)."""

from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKER = os.path.join(ROOT, "zk", "js", "worker.mjs")
BUILD = os.path.join(ROOT, "zk", "build")


def available() -> bool:
    return (shutil.which("node") is not None and os.path.exists(WORKER)
            and os.path.exists(os.path.join(BUILD, "membership_final.zkey"))
            and os.path.isdir(os.path.join(ROOT, "zk", "js", "node_modules")))


class ZKWorker:
    def __init__(self) -> None:
        if not available():
            raise RuntimeError("zk toolchain missing: run zk/setup.sh")
        self.proc = subprocess.Popen(["node", WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def call(self, op: str, **kw: Any) -> Dict[str, Any]:
        with self._lock:
            rid = next(self._ids)
            self.proc.stdin.write(json.dumps({"id": rid, "op": op, **kw}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("zk worker exited")
        res = json.loads(line)
        if "error" in res:
            raise RuntimeError(res["error"])
        return res

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def __enter__(self) -> "ZKWorker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


_shared: Optional[ZKWorker] = None


def shared() -> ZKWorker:
    global _shared
    if _shared is None or _shared.proc.poll() is not None:
        _shared = ZKWorker()
    return _shared
