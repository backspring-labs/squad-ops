import unittest

from tally.ledger import Ledger


class LedgerChecks(unittest.TestCase):
    def test_adds_to_a_counter(self):
        ledger = Ledger()
        ledger.add("apples")
        self.assertEqual(ledger.add("apples", 2), 3)

    def test_an_unknown_counter_reads_zero(self):
        self.assertEqual(Ledger().get("pears"), 0)

    def test_refuses_a_negative_amount(self):
        with self.assertRaises(ValueError):
            Ledger().add("apples", -1)

    def test_loads_entries_and_totals_them(self):
        ledger = Ledger()
        ledger.load(["apples:3", "", "pears:2"])
        self.assertEqual(ledger.counters(), {"apples": 3, "pears": 2})
        self.assertEqual(ledger.total(), 5)
