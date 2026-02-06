"""Date/month utilities for consistent formatting across calculators and tests."""

import time


def normalize_date(value, output_format='YYYY-MM'):
    """
    Convert date string to requested output format for consistent comparison.

    Accepts flexible input: 'YYYY-M', 'YYYY-MM', or ctime ('Fri Sep 29 00:00:00 2023').

    Args:
        value: Date string in various formats.
        output_format: 'YYYY-MM' (zero-padded month, calculator default) or 'ctime'.

    Returns:
        Date string in the requested format, or value unchanged if parsing fails.
    """
    if not isinstance(value, str):
        return value

    year, month, day = _parse_date(value)
    if year is None:
        return value

    if output_format == 'YYYY-MM':
        return f"{year}-{month:02d}"
    if output_format == 'ctime':
        day = day or 1
        struct = time.struct_time((year, month, day, 0, 0, 0, 0, 0, -1))
        return time.strftime('%a %b %d %H:%M:%S %Y', struct)
    return value


def _parse_date(value):
    """Parse date string to (year, month, day). Returns (None, None, None) on failure."""
    # Try YYYY-M or YYYY-MM
    parts = value.split('-')
    if len(parts) == 2:
        try:
            year, month = int(parts[0]), int(parts[1])
            if 1 <= month <= 12:
                return (year, month, None)
        except (ValueError, TypeError):
            pass

    # Try ctime: 'Fri Sep 29 00:00:00 2023'
    try:
        struct = time.strptime(value.strip(), '%a %b %d %H:%M:%S %Y')
        return (struct.tm_year, struct.tm_mon, struct.tm_mday)
    except ValueError:
        pass
    return (None, None, None)


def normalize_month_key(key):
    """
    Normalize 'YYYY-M' or 'YYYY-MM' to 'YYYY-MM' (zero-padded) for consistent lookup.

    Convenience wrapper around normalize_date(value, 'YYYY-MM').
    """
    return normalize_date(key, 'YYYY-MM')


def expected_for_comparison(tuples, output_format='YYYY-MM'):
    """
    Normalize the first element (date) of each tuple for comparison with calculator output.

    Use when expected tuples have (date_str, val1, val2, ...) and calculator outputs
    dates in a different format.

    Example:
        expected = [('Fri Sep 29 00:00:00 2023', 161280.0, ...), ('2023-9', 40)]
        normalized = expected_for_comparison(expected)  # -> [('2023-09', 161280.0, ...), ...]
    """
    return [(normalize_date(t[0], output_format), *t[1:]) for t in tuples]
