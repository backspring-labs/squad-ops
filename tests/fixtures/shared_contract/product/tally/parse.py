"""Reading ledger entries from text."""


def parse_entry(line):
    """Return (name, amount) from a line such as "apples:3"."""
    name, _, amount = line.partition(":")
    if not name or not amount:
        raise ValueError(f"not an entry: {line!r}")
    return name, int(amount)
