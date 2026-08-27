#!/usr/bin/env python3
"""Evidence-trajectory precedent store (episodic memory + retrieval).

依据(出处): _deliverables/deep-study/notes/reflexion.md §2 (episodic memory with
             capacity cap Omega ~= 1-3; experience reused across trials),
             官方实现: https://github.com/noahshinn/reflexion (NeurIPS'23);
             retrieval-side pattern: OpenScholar-style evidence retrieval (deep
             study note: retrieval-augmented agents), paper: OpenScholar (Nature 2025).
We store method-trajectory PRECEDENTS (published-review method records), not raw
outcomes — the memory is a method library with bounded capacity and kNN query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from metawingman.agent.scrutiny import feature_vector


@dataclass
class PrecedentStore:
    capacity: int = 64
    _items: list[dict[str, Any]] = field(default_factory=list)

    def register(self, signal: dict[str, Any], design: str, poolable: bool,
                 living: bool, note: str = "") -> None:
        self._items.append({"signal": {k: v for k, v in signal.items()},
                            "design_selection": design, "poolable": bool(poolable),
                            "living": bool(living), "note": note})
        if len(self._items) > self.capacity:
            # bounded memory: drop the oldest (episodic window)
            self._items = self._items[-self.capacity:]

    def retrieve(self, signal: dict[str, Any], k: int = 3) -> list[dict[str, Any]]:
        if not self._items:
            return []
        q = feature_vector(signal)
        scored = [(float(np.linalg.norm(q - feature_vector(it["signal"]))), it)
                  for it in self._items]
        scored.sort(key=lambda x: x[0])
        return [it for _d, it in scored[:k]]

    def __len__(self) -> int:
        return len(self._items)

    def stats(self) -> dict[str, Any]:
        return {"capacity": self.capacity, "size": len(self._items)}
