from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from typing import Iterator, Sequence
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.apple_service as apple_service_module
from services.apple_service import AppleStoreService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the Apple Lookup API for a single Apple ID and print the raw JSON payload."
    )
    parser.add_argument("apple_id", help="Apple ID to query")
    return parser


@contextmanager
def _suppress_apple_service_logs() -> Iterator[None]:
    original_loggers = {
        "log_info": apple_service_module.log_info,
        "log_warning": apple_service_module.log_warning,
        "log_error": apple_service_module.log_error,
    }
    try:
        apple_service_module.log_info = lambda _message: None
        apple_service_module.log_warning = lambda _message: None
        apple_service_module.log_error = lambda _message: None
        yield
    finally:
        apple_service_module.log_info = original_loggers["log_info"]
        apple_service_module.log_warning = original_loggers["log_warning"]
        apple_service_module.log_error = original_loggers["log_error"]


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    service = AppleStoreService()

    try:
        with _suppress_apple_service_logs():
            payload = service.lookup_raw(args.apple_id, verbose=False)
    except requests.exceptions.RequestException as error:
        print(f"Apple Lookup request failed: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Apple Lookup failed: {error}", file=sys.stderr)
        return 1

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
