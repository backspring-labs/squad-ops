import unittest

from tally.parse import parse_entry


class ParseChecks(unittest.TestCase):
    def test_reads_a_plain_entry(self):
        self.assertEqual(parse_entry("apples:3"), ("apples", 3))

    def test_rejects_a_line_without_an_amount(self):
        with self.assertRaises(ValueError):
            parse_entry("apples")

    # Fails today: names keep the spaces around them (issue 12).
    def test_strips_spaces_around_the_name(self):
        self.assertEqual(parse_entry(" apples : 3"), ("apples", 3))
