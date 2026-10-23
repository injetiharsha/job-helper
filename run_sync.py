import sys
import argparse

# Safe utf-8 output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.engine import JobHelperEngine

def main():
    parser = argparse.ArgumentParser(description="Job Helper: Recruitment Lifecycle Sync")
    parser.add_argument("--since", help="Force scan starting from specific date (e.g. '01-Oct-2026')")
    args = parser.parse_args()

    engine = JobHelperEngine()
    engine.run(force_since_date=args.since)

if __name__ == "__main__":
    main()
