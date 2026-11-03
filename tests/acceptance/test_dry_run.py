from datetime import date
from availability import available


def test_dry_run_overlap_is_unavailable():
    bookings = {"U-DEMO-1": [(date(2027, 1, 10), date(2027, 1, 12))]}
    assert available("U-DEMO-1", date(2027, 1, 11), date(2027, 1, 13), bookings) == "unavailable"
