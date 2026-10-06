"""Append-only, hash-chained decision log kept by the payer-side verifier."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from .canon import canonical, sha256


@dataclass
class DecisionLog:
    path: Optional[str] = None
    entries: List[dict] = field(default_factory=list)
    head: str = "0" * 64

    def append(self, record: dict) -> str:
        entry = {"prev": self.head, "record": record}
        self.head = sha256(canonical(entry)).hex()
        entry["hash"] = self.head
        self.entries.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return self.head

    def verify(self) -> bool:
        prev = "0" * 64
        for entry in self.entries:
            body = {"prev": entry["prev"], "record": entry["record"]}
            if entry["prev"] != prev or sha256(canonical(body)).hex() != entry["hash"]:
                return False
            prev = entry["hash"]
        return True
