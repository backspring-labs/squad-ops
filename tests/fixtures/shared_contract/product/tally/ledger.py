"""A ledger of named counters."""

from tally.parse import parse_entry


class Ledger:
    def __init__(self):
        self._counts = {}

    def add(self, name, amount=1):
        if amount < 0:
            raise ValueError("amounts are never negative")
        self._counts[name] = self._counts.get(name, 0) + amount
        return self._counts[name]

    def get(self, name):
        return self._counts.get(name, 0)

    def counters(self):
        return dict(sorted(self._counts.items()))

    def total(self):
        return sum(self._counts.values())

    def load(self, lines):
        for line in lines:
            if line.strip():
                self.add(*parse_entry(line))
