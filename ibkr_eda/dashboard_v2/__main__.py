"""CLI entry point: python -m ibkr_eda.dashboard_v2"""

from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(description="IBKR Portfolio Analytics Dashboard V2")
    parser.add_argument("--port", type=int, default=5051)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--csv", default=None, help="Path to trades CSV")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from ibkr_eda.dashboard_v2.app import create_app

    app = create_app(csv_path=args.csv)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
