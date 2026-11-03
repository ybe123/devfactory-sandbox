"""Fictitious sandbox module (Dev Factory P2 dry run)."""
from datetime import date


def available(unit: str, start: date, end: date, bookings: dict[str, list[tuple[date, date]]]) -> str:
    if unit not in bookings:
        return "not_configured"
    if start >= end:
        raise ValueError("empty stay")
    overlaps = any(b_start < end and start < b_end for b_start, b_end in bookings[unit])
    return "unavailable" if overlaps else "available"
