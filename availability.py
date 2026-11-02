"""Fictitious sandbox module (Dev Factory lot 2): availability of the units of a demo guest house.

Data and rules are invented for the validation of the Dev Factory; they describe no real establishment.
"""
from datetime import date


def available(unit: str, start: date, end: date, bookings: dict[str, list[tuple[date, date]]]) -> str:
    """'available', 'unavailable' or 'not_configured' for the nights [start, end) of `unit`."""
    raise NotImplementedError("to be written by the developer agent (ticket T1)")
