from datetime import date
from shorts.priority import compensation, priority_key


def test_monthly_compensation_normalization():
    assert compensation('INR 1000-50000 / monthly') == (2, 1000)
    assert compensation('₹55,000 per month') == (2, 55000)
    assert compensation('INR 6 LPA') == (2, 50000)
    assert compensation('Unpaid') == (0, 0)
    assert compensation('$5000/month') == (1, 0)
    assert compensation('INR 5000') == (1, 0)
    assert compensation('Not disclosed') == (1, 0)


def test_paid_deadline_and_unpaid_order():
    today = date(2026, 10, 12)
    def row(id, stipend, deadline=None):
        return dict(id=id, stipend_text=stipend, deadline=deadline)
    rows = [row('unpaid', 'Unpaid', '2026-10-12'), row('unknown', ''),
            row('low', 'INR 5000/month'), row('high', 'INR 55000/month'),
            row('urgent', 'INR 20000/month', '2026-10-13')]
    assert [r['id'] for r in sorted(rows, key=lambda r: priority_key(r, today))] == ['urgent', 'high', 'low', 'unknown', 'unpaid']
