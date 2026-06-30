"""Text processing utilities shared across chatview."""

import re


def normalize_error(msg: str) -> str:
    """Normalize error message for grouping: strip paths, numbers, hashes."""
    s = msg.strip()
    # Remove file paths
    s = re.sub(r"(/[^\s:]+)", "<path>", s)
    # Remove line numbers
    s = re.sub(r"line \d+", "line N", s, flags=re.IGNORECASE)
    # Remove hex addresses
    s = re.sub(r"0x[0-9a-f]+", "0xN", s, flags=re.IGNORECASE)
    return s[:150]
