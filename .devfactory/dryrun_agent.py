"""Deterministic stand-in for the agent (validation P2, NO AI call): writes a fixed change in the work tree.

Run as the isolated agent user under the network lock, exactly where the real agent runs.
"""
import json
import os

FIXED = '''"""Fictitious sandbox module (Dev Factory P2 dry run)."""
from datetime import date


def available(unit: str, start: date, end: date, bookings: dict[str, list[tuple[date, date]]]) -> str:
    if unit not in bookings:
        return "not_configured"
    if start >= end:
        raise ValueError("empty stay")
    overlaps = any(b_start < end and start < b_end for b_start, b_end in bookings[unit])
    return "unavailable" if overlaps else "available"
'''
ACCEPTANCE = '''from datetime import date
from availability import available


def test_dry_run_overlap_is_unavailable():
    bookings = {"U-DEMO-1": [(date(2027, 1, 10), date(2027, 1, 12))]}
    assert available("U-DEMO-1", date(2027, 1, 11), date(2027, 1, 13), bookings) == "unavailable"
'''

if __name__ == "__main__":
    if os.environ["ROLE"] == "developer":
        with open("availability.py", "w", encoding="utf-8") as f:
            f.write(FIXED)
    else:
        os.makedirs("tests/acceptance", exist_ok=True)
        with open("tests/acceptance/test_dry_run.py", "w", encoding="utf-8") as f:
            f.write(ACCEPTANCE)
        with open(".devfactory-verdicts.json", "w", encoding="utf-8") as f:
            json.dump([{"criterion": "chevauchement → indisponible (dry run)", "status": "pass"}], f)
    print("dry run change written")
