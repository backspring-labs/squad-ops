import os
import unittest

from tally.ledger import Ledger
from tally.notify import send_digest

SMTP_HOST = os.environ.get("TALLY_SMTP_HOST")


@unittest.skipUnless(SMTP_HOST, "needs a mail server: set TALLY_SMTP_HOST")
class NotifyChecks(unittest.TestCase):
    def test_sends_the_digest(self):
        ledger = Ledger()
        ledger.add("apples", 3)
        send_digest(ledger, SMTP_HOST, "ops@localhost")
