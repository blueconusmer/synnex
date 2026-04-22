from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Payload = dict[str, Any]


@dataclass
class Agent:
    name: str
    slug: str
    description: str

    def run(self, context: Payload) -> Payload:
        raise NotImplementedError
