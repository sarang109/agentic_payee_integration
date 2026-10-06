"""Output layout, run metadata and manifests shared by all experiments."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(ROOT, "results")
RAW = os.path.join(RESULTS, "raw")
TABLES = os.path.join(RESULTS, "tables")
FIGURES = os.path.join(RESULTS, "figures")
for d in (RESULTS, RAW, TABLES, FIGURES):
    os.makedirs(d, exist_ok=True)

SEED = int(os.environ.get("MERIDIAN_SEED", "7"))
QUICK = os.environ.get("MERIDIAN_QUICK", "0") == "1"


def git_rev() -> str:
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
                                       text=True).strip()
    except Exception:
        return "uncommitted"


def environment() -> Dict[str, Any]:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "git": git_rev(),
        "seed": SEED,
        "quick": QUICK,
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for mod in ("numpy", "scipy", "pandas", "cryptography", "sentence_transformers", "agentdojo"):
        try:
            m = __import__(mod)
            env[mod] = getattr(m, "__version__", "?")
        except Exception:
            env[mod] = None
    return env


def write_csv(name: str, rows: Iterable[Dict] | pd.DataFrame) -> str:
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    path = os.path.join(RAW, f"{name}.csv")
    df.to_csv(path, index=False)
    return path


def write_json(name: str, obj: Any, folder: str = RAW) -> str:
    path = os.path.join(folder, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=str)
    return path


def write_table(name: str, df: pd.DataFrame, title: str, note: Optional[str] = None, index: bool = True) -> str:
    path = os.path.join(TABLES, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"### {title}\n\n")
        fh.write(df.to_markdown(index=index))
        fh.write("\n")
        if note:
            fh.write(f"\n{note}\n")
    df.to_csv(os.path.join(TABLES, f"{name}.csv"), index=index)
    return path


def manifest() -> str:
    """SHA-256 of every raw output, table and figure."""
    entries: List[Dict[str, Any]] = []
    for folder in (RAW, TABLES, FIGURES):
        for fn in sorted(os.listdir(folder)):
            p = os.path.join(folder, fn)
            if os.path.isfile(p):
                with open(p, "rb") as fh:
                    entries.append({"path": os.path.relpath(p, ROOT), "sha256": hashlib.sha256(fh.read()).hexdigest(),
                                    "bytes": os.path.getsize(p)})
    out = os.path.join(RESULTS, "MANIFEST.sha256.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"environment": environment(), "files": entries}, fh, indent=2)
    return out


class Timer:
    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self) -> "Timer":
        self.t0 = time.perf_counter()
        print(f"[{time.strftime('%H:%M:%S')}] {self.label} ...", flush=True)
        return self

    def __exit__(self, *exc) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {self.label} done in {time.perf_counter() - self.t0:.1f}s", flush=True)
