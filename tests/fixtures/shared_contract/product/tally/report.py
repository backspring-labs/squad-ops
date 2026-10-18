"""A summary of the ledger."""


def summarize(ledger):
    counters = ledger.counters()
    top = max(counters, key=counters.get) if counters else None
    return {"total": ledger.total(), "counters": len(counters), "top": top}
