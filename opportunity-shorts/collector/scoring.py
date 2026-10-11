from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .filters import is_early_career


def score(opp, today: Optional[date] = None, priority_companies=()) -> float:
    """Rule-based ranking: higher = better candidate for a Short. Tune freely."""
    today = today or date.today()
    pri = {c.lower() for c in priority_companies or []}
    s = 0.0
    if opp.is_india:
        s += 30
    elif opp.is_remote:
        s += 10
    if opp.opp_type == "internship":
        s += 20
    elif is_early_career(opp):
        s += 15
    if opp.stipend_text:
        s += 10
    if opp.verified:
        s += 15
    if opp.company and opp.company.lower() in pri:
        s += 15
    if opp.batch_years:
        s += 5
    if opp.deadline:
        try:
            days = (date.fromisoformat(opp.deadline) - today).days
            if days < 0:
                s -= 100
            elif days <= 3:
                s += 20
            elif days <= 7:
                s += 12
            elif days <= 14:
                s += 6
        except ValueError:
            pass
    if opp.posted_at:
        try:
            age = (today - datetime.fromisoformat(opp.posted_at.replace("Z", "+00:00")).date()).days
            if age <= 3:
                s += 10
            elif age <= 14:
                s += 5
        except ValueError:
            pass
    return s
