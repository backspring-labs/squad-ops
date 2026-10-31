"""python3 -m tally serve --host HOST --port PORT"""

import argparse
import sys

from tally.server import make_server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tally")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="serve the ledger over HTTP")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)

    server = make_server(args.host, args.port)
    print(f"tally serving on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
