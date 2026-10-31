import json
import threading
import unittest
import urllib.error
import urllib.request

from tally.server import ASSETS, make_server


class ServerChecks(unittest.TestCase):
    def setUp(self):
        self.server = make_server("127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, method="GET"):
        req = urllib.request.Request(self.base + path, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_answers_its_health_check(self):
        self.assertEqual(self.request("/healthz"), (200, b"ok\n"))

    def test_an_unknown_path_is_not_found(self):
        self.assertEqual(self.request("/nowhere")[0], 404)

    def test_counts_by_name(self):
        self.request("/counters/apples", method="POST")
        status, body = self.request("/counters/apples", method="POST")
        self.assertEqual((status, json.loads(body)), (200, {"name": "apples", "count": 2}))

    def test_serves_the_mark_unchanged(self):
        self.assertEqual(self.request("/mark.png"), (200, (ASSETS / "mark.png").read_bytes()))
