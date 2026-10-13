import argparse
import asyncio
import logging
from app.config import Settings
from app.models import make_session_factory
from app.workers import Worker

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--once", action="store_true"); parser.add_argument("--dry-run", action="store_true", help="preview qualified Google Sheets rows without writing"); args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    if args.once: settings.worker_mode = "scheduled"
    asyncio.run(Worker(settings, make_session_factory(settings)).run(dry_run=args.dry_run))

if __name__ == "__main__": main()

