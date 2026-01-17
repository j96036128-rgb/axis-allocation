#!/usr/bin/env python3
"""
Axis Deal Engine - Mandate Management Server

Run this script to start the mandate management UI.

Usage:
    python serve.py [--port PORT] [--host HOST]

Example:
    python serve.py --port 8080
"""

import argparse
from deal_engine.api import run_server


def main():
    parser = argparse.ArgumentParser(
        description="Axis Deal Engine - Mandate Management Server"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost)"
    )

    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
