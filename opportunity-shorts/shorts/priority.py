"""Conservative stipend ranking without changing published source facts."""
import re
from datetime import date


def compensation(text):
    text = (text or '').lower().strip()
    if re.search(r'\bunpaid\b|\bno stipend\b|\bvolunteer\b', text):
        return 0, 0.0
    # Compare only explicit INR amounts with an explicit pay period.
    if not re.search(r'₹|\binr\b|\brs\.?', text):
        return 1, 0.0
    values = []
    for number, suffix in re.findall(r'(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|lpa|k)?', text):
        amount = float(number.replace(',', ''))
        amount *= 100000 if suffix in ('lakh', 'lac', 'lpa') else 1000 if suffix == 'k' else 1
        values.append(amount)
    if not values:
        return 1, 0.0
    amount = min(values)  # Rank ranges by their disclosed lower bound.
    if amount == 0:
        return (0, 0.0) if max(values) == 0 else (1, 0.0)
    if re.search(r'year|annual|annum|lpa', text):
        amount /= 12
    elif not re.search(r'month|monthly', text):
        return 1, 0.0
    return 2, amount


def priority_key(row, today=None, urgent_days=3):
    row = dict(row)
    today = today or date.today()
    tier, amount = compensation(row.get('stipend_text'))
    try:
        deadline = date.fromisoformat(row.get('deadline') or '')
    except ValueError:
        deadline = date.max
    urgent = tier == 2 and 0 <= (deadline - today).days <= urgent_days
    return (-tier, -int(urgent), -amount, deadline, -(row.get('score') or 0),
            str(row.get('posted_at') or ''), row['id'])
