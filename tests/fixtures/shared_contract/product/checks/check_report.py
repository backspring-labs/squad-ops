import unittest

from tally.ledger import Ledger
from tally.report import summarize


class ReportChecks(unittest.TestCase):
    def test_an_empty_ledger_has_no_top_counter(self):
        self.assertEqual(summarize(Ledger()), {"total": 0, "counters": 0, "top": None})

    def test_names_the_largest_counter(self):
        ledger = Ledger()
        ledger.load(["apples:3", "pears:5"])
        self.assertEqual(summarize(ledger), {"total": 8, "counters": 2, "top": "pears"})
