"""Entry point: python -m ibkr_eda.dashboard"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="IBKR Trade Dashboard")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--source", choices=["csv", "live"], default="csv")
    parser.add_argument(
        "--csv", dest="csv_path", default=None,
        help="Path to CSV file (default: auto-detect from data/)",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    from ibkr_eda.dashboard.app import create_app

    app = create_app(data_source=args.source, csv_path=args.csv_path)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
