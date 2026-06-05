# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
"""
Tests for rpsd_storage.utils - object ID generation utilities.
"""

import time

from rpsd_storage.utils import flip_uuid, generate_object_id


class TestFlipUuid:
    """Tests for the flip_uuid function."""

    def test_dashed_input_returns_dashless(self):
        """Flipping a dashed UUID returns a dashless string."""
        input_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = flip_uuid(input_uuid)
        assert "-" not in result
        assert len(result) == 32

    def test_dashless_input_returns_dashed(self):
        """Flipping a dashless string returns a dashed UUID."""
        input_hex = "aaf17bff1d64be2b58e9bb99aabbffff"
        result = flip_uuid(input_hex)
        assert "-" in result
        parts = result.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    def test_is_self_inverse(self):
        """Applying flip_uuid twice returns the original."""
        original = "550e8400-e29b-41d4-a716-446655440000"
        flipped = flip_uuid(original)
        restored = flip_uuid(flipped)
        assert restored == original

    def test_changes_value(self):
        """Flipped value is different from the original."""
        original = "550e8400-e29b-41d4-a716-446655440000"
        flipped = flip_uuid(original)
        # Compare without dashes since formats differ
        assert flipped != original.replace("-", "")

    def test_all_zeros_to_all_fs(self):
        """Flipping all-zero UUID gives all-f hex."""
        all_zeros = "00000000-0000-0000-0000-000000000000"
        result = flip_uuid(all_zeros)
        assert result == "ffffffffffffffffffffffffffffffff"

    def test_all_fs_to_all_zeros(self):
        """Flipping all-f hex gives all-zero UUID."""
        all_fs = "ffffffffffffffffffffffffffffffff"
        result = flip_uuid(all_fs)
        assert result == ("00000000-0000-0000-0000-000000000000")


class TestGenerateObjectId:
    """Tests for the generate_object_id function."""

    def test_returns_string(self):
        """generate_object_id returns a string."""
        result = generate_object_id()
        assert isinstance(result, str)

    def test_returns_dashless_hex(self):
        """Result is a 32-char dashless hex string."""
        result = generate_object_id()
        assert "-" not in result
        assert len(result) == 32

    def test_is_valid_hex(self):
        """All characters are valid hex digits."""
        result = generate_object_id()
        hex_chars = set("0123456789abcdef")
        assert all(c in hex_chars for c in result)

    def test_unique_ids(self):
        """Sequential calls produce unique IDs."""
        ids = [generate_object_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_newer_id_sorts_first(self):
        """A newer ID should have a smaller string value
        (sort first in ascending order)."""
        id1 = generate_object_id()
        time.sleep(0.01)
        id2 = generate_object_id()
        # id2 is newer, so it should be "smaller"
        assert id2 < id1

    def test_roundtrip_recovers_uuid7(self):
        """Can recover a proper dashed UUID7 from a generated
        object_id via flip_uuid."""
        object_id = generate_object_id()
        recovered = flip_uuid(object_id)
        # Recovered should be a dashed UUID
        assert "-" in recovered
        parts = recovered.split("-")
        assert len(parts) == 5
        # Flipping again should give back the object_id
        assert flip_uuid(recovered) == object_id
