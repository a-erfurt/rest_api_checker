"""Regression checks for lossless timestamp decoding; no SQL or study execution."""

import struct
import unittest

from probe import decode_datetimeoffset


class TimestampTests(unittest.TestCase):
    def test_seventh_fractional_digit_and_positive_offset(self):
        raw = struct.pack("<6hI2h", 2026, 9, 26, 13, 14, 15, 123456700, 5, 45)
        self.assertEqual(decode_datetimeoffset(raw), "2026-09-26T13:14:15.1234567+05:45")

    def test_negative_offset_under_one_hour(self):
        raw = struct.pack("<6hI2h", 2026, 9, 26, 1, 2, 3, 100, 0, -30)
        self.assertEqual(decode_datetimeoffset(raw), "2026-09-26T01:02:03.0000001-00:30")

    def test_zero_offset_and_fraction(self):
        raw = struct.pack("<6hI2h", 2026, 9, 26, 1, 2, 3, 0, 0, 0)
        self.assertEqual(decode_datetimeoffset(raw), "2026-09-26T01:02:03.0000000+00:00")

    def test_no_silent_precision_loss(self):
        raw = struct.pack("<6hI2h", 2026, 9, 26, 1, 2, 3, 123456789, 0, 0)
        with self.assertRaisesRegex(RuntimeError, "100 ns"):
            decode_datetimeoffset(raw)


if __name__ == "__main__":
    unittest.main()
