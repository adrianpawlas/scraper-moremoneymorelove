"""
Entry point for manual or scheduled runs.
Usage:
  python run_scraper.py           # full run
  python run_scraper.py --dry-run
  python run_scraper.py --limit 5
"""
from main import run
import argparse

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)
