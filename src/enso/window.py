"""
enso.window
===========
The Fourier analysis window: which months of a record are filtered.

Ported from el_nino/src/el_nino/pipeline.py (behaviour unchanged). The
window is set only in config.yaml (``filter.window``); the site has no
browser-side window selector.
"""

from __future__ import annotations

import numpy as np


def _ym(year: int, month: int) -> int:
    """Serial month index, so windows can be compared as plain integers."""
    return int(year) * 12 + int(month)


def parse_month(value) -> int | None:
    """Parse a ``YYYY-MM`` window bound into a serial month index.

    ``None`` and the empty string mean "not specified" and are passed
    through as ``None`` so the caller can apply its own default.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    parts = text.replace("/", "-").split("-")
    if len(parts) < 2:
        raise ValueError(f"window bound must look like 'YYYY-MM', got {value!r}")
    year, month = int(parts[0]), int(parts[1])
    if not 1 <= month <= 12:
        raise ValueError(f"window month must be in 1..12, got {value!r}")
    return _ym(year, month)


def format_month(ym: int) -> str:
    """Inverse of :func:`parse_month`: a serial month index as ``YYYY-MM``."""
    year, month = divmod(int(ym) - 1, 12)
    return f"{year:04d}-{month + 1:02d}"


def cycle_start_month(end_ym: int) -> int:
    """Calendar month a window must start in to span whole 12-month cycles.

    A record running from month ``m`` to month ``m-1`` covers every calendar
    month the same number of times, which is what the monthly climatology and
    the endpoint phase of the sine expansion both want.
    """
    end_month = (int(end_ym) - 1) % 12 + 1
    return end_month % 12 + 1


def default_start_ym(end_ym: int, base_year: int = 1975) -> int:
    """First month of the default window for a record ending at ``end_ym``.

    The window starts in ``base_year``, in the calendar month that *follows*
    the end month, so it spans a whole number of complete 12-month seasonal
    cycles.  With an end of August 2026 this gives September 1975: 612
    observations, exactly 51 full years, every calendar month equally
    represented in the climatology.
    """
    return _ym(base_year, cycle_start_month(end_ym))


def _first_cycle_start_at_or_after(record_first: int, end_ym: int) -> int:
    """Earliest whole-cycle start month that the record actually contains."""
    month = cycle_start_month(end_ym)
    candidate = _ym((record_first - 1) // 12, month)
    while candidate < record_first:
        candidate += 12
    return candidate


def resolve_fourier_window(
    IYR: np.ndarray,
    MES: np.ndarray,
    start=None,
    end=None,
    base_year: int = 1975,
) -> dict:
    """Turn a requested window into concrete bounds for one dataset.

    ``start`` and ``end`` are ``YYYY-MM`` strings (or ``None``).  Both are
    honoured exactly as given (nothing is silently moved) and then clipped
    to the record actually available, so a window wider than a station's
    record simply falls back to that record's own first and last month.

    Returns a dict with the resolved serial-month bounds, their labels, and
    a list of human-readable notes: whether the request was clipped, and
    whether the window spans a whole number of seasonal cycles.  A window
    whose start month is not ``end month + 1`` joins two different phases of
    the annual cycle at the endpoints of the sine expansion, which biases
    the detrending; that is reported, not corrected.
    """
    IYR = np.asarray(IYR)
    MES = np.asarray(MES)
    if len(IYR) == 0:
        raise ValueError("cannot resolve a Fourier window for an empty record")

    record_first = _ym(int(IYR[0]), int(MES[0]))
    record_last = _ym(int(IYR[-1]), int(MES[-1]))

    requested_end = parse_month(end)
    end_ym = record_last if requested_end is None else requested_end

    requested_start = parse_month(start)
    if requested_start is None:
        start_ym = default_start_ym(min(end_ym, record_last), base_year)
    else:
        start_ym = requested_start

    notes: list[str] = []
    clipped_end = min(end_ym, record_last)
    if start_ym < record_first:
        # The request reaches back beyond this record. Rather than starting at
        # whatever calendar month the record happens to open with, start at
        # the first month that still gives whole 12-month cycles: the same
        # rule the default start uses, applied to this record's own beginning.
        clipped_start = _first_cycle_start_at_or_after(record_first, clipped_end)
        notes.append(
            f"start moved to {format_month(clipped_start)}: the record begins "
            f"{format_month(record_first)} and this is its first whole-cycle start"
        )
    else:
        clipped_start = start_ym
    if clipped_end != end_ym:
        notes.append(
            f"end clipped to {format_month(clipped_end)} (record ends then)"
        )
    if clipped_end - clipped_start < 11:
        # One complete seasonal cycle is the hard floor: the monthly
        # climatology needs every calendar month at least once.
        raise ValueError(
            "Fourier window must span at least 12 months; got "
            f"{format_month(clipped_start)}..{format_month(clipped_end)}"
        )

    start_month = (clipped_start - 1) % 12 + 1
    end_month = (clipped_end - 1) % 12 + 1
    whole_cycles = start_month == end_month % 12 + 1
    if not whole_cycles:
        notes.append(
            "window does not span whole 12-month cycles "
            f"(starts in month {start_month}, ends in month {end_month}); "
            "the sine expansion joins different phases of the seasonal cycle "
            "at its endpoints and the monthly climatology is unbalanced"
        )

    return {
        "start_ym": clipped_start,
        "end_ym": clipped_end,
        "start": format_month(clipped_start),
        "end": format_month(clipped_end),
        "requested_start": None if requested_start is None else format_month(requested_start),
        "requested_end": None if requested_end is None else format_month(requested_end),
        "n_months": clipped_end - clipped_start + 1,
        "whole_cycles": bool(whole_cycles),
        "notes": notes,
    }


def select_fourier_window(
    IYR: np.ndarray,
    MES: np.ndarray,
    data: np.ndarray,
    start=None,
    end=None,
    base_year: int = 1975,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Slice a continuous monthly record down to the requested window.

    The window is an explicit input (config.yaml ``filter.window``). When no
    start is given, :func:`default_start_ym` makes the window span whole
    12-month seasonal cycles.
    """
    IYR = np.asarray(IYR)
    MES = np.asarray(MES)
    data = np.asarray(data)

    if not (len(IYR) == len(MES) == len(data)):
        raise ValueError("IYR, MES, and data must have the same length")
    if len(MES) < 2:
        raise ValueError("at least two monthly observations are required")
    if np.any((MES < 1) | (MES > 12)):
        raise ValueError("MES values must be calendar months in 1..12")
    serial_month = IYR.astype(np.int64) * 12 + MES.astype(np.int64)
    if np.any(np.diff(serial_month) != 1):
        raise ValueError(
            "IYR and MES must form a continuous monthly calendar; "
            "missing months must be reconstructed before Fourier analysis"
        )

    window = resolve_fourier_window(IYR, MES, start, end, base_year)
    keep = (serial_month >= window["start_ym"]) & (serial_month <= window["end_ym"])
    return IYR[keep], MES[keep], data[keep], window
