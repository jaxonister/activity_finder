"""Command-line interface for activity_finder."""

import argparse
import logging
import sys

from activity_finder.cache import AppCache
from activity_finder.finder import AppInfoFinder

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Resolve Android app labels to launch activities"
    )
    parser.add_argument("label", help="App label to search for")
    parser.add_argument("--aapt", help="Path to aapt binary")
    parser.add_argument("--db", default="apps.db", help="SQLite DB path (default: apps.db)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    cache = None if args.no_cache else AppCache(db_path=args.db)
    try:
        finder = AppInfoFinder(aapt=args.aapt, cache=cache)
        results = finder.resolve_label_to_package(args.label)
        if results:
            logger.info("Found %d match(es)", len(results))
            for r in results:
                print("{label}\t{package}\t{activity}".format(**r))
        else:
            logger.warning("Not found: no app matched label '%s'", args.label)
    finally:
        if cache:
            cache.close()


if __name__ == "__main__":
    main()
