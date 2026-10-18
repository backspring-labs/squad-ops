# Tally

A ledger of named counters, served over HTTP.

```
python3 tools/build.py
python3 -m tally serve --host 0.0.0.0 --port 18407
```

`GET /admin` needs `TALLY_ADMIN_TOKEN` in the server's environment; without it, the route answers 503.
