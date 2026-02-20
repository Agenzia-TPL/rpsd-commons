"""
Utility functions for rpsd-storage.

Provides UUID7-based object ID generation with bit-flipping for
reverse chronological sorting in ascending lexicographic order.
"""

from edwh_uuid7 import uuid7


def flip_uuid(uuid_str: str) -> str:
    """
    XOR-flip a UUID string to invert its sort order.

    Smart about formatting direction:
    - Input with dashes (real UUID) -> output without dashes
      (flipped object_id)
    - Input without dashes (flipped object_id) -> output with
      dashes (recovered UUID7)

    This ensures flipped IDs never look like real UUIDs, and
    recovering always produces a proper UUID format.

    The function is self-inverse: applying it twice returns the
    original value.

    Args:
        uuid_str: UUID string, with or without dashes.

    Returns:
        The XOR-flipped string with toggled dash formatting.
    """
    max_128 = (1 << 128) - 1
    has_dashes = "-" in uuid_str
    hex_str = uuid_str.replace("-", "")
    inverted_int = int(hex_str, 16) ^ max_128
    result = format(inverted_int, "032x")
    if has_dashes:
        # Input was a real UUID -> return dashless flipped ID
        return result
    # Input was a flipped ID -> return dashed UUID
    return f"{result[:8]}-{result[8:12]}-{result[12:16]}-{result[16:20]}-{result[20:]}"


def generate_object_id() -> str:
    """
    Generate a flipped UUID7 object ID.

    Uses UUID7 for time-ordered generation, then XOR-flips the
    bits so that newer IDs sort first in ascending lexicographic
    order. This is important for S3 listing, which only supports
    ascending order.

    Returns:
        A 32-character dashless hex string
        (e.g., "ff1a2b3c4d5e6f789a0bcdef01234567").
    """
    return flip_uuid(str(uuid7()))
