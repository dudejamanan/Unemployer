from __future__ import annotations

from typing import List

from ..models import Opportunity


class Source:
    name = "base"
    closes_missing = False     # True only when a fetch returns the board's COMPLETE open-job list

    def key(self, cfg: dict) -> str:
        raise NotImplementedError

    def fetch(self, client, cfg: dict) -> List[Opportunity]:
        raise NotImplementedError


def first(*vals, default=""):
    for v in vals:
        if v:
            return v
    return default
