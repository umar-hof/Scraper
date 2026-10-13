"""Import operator-supplied seeds without synchronizing Google Sheets."""
import argparse
import asyncio
import csv
from pathlib import Path

from app.config import Settings
from app.manual_seed import load_manual_seeds
from app.models import QualifiedLead, make_session_factory
from app.sheets import HEADERS, lead_row
from app.workers import Worker


async def run(input_path: str, output_path: str) -> None:
    settings = Settings(worker_mode="scheduled")
    seeds = load_manual_seeds(input_path)
    session = make_session_factory(settings)()
    try:
        worker = Worker(settings, make_session_factory(settings))
        results = []
        for seed in seeds:
            results.append((seed, await worker.process_manual_seed(seed, session)))
        source_urls = [seed.source_url for seed, status in results]
        qualified = session.query(QualifiedLead).filter(QualifiedLead.qualification_status == "Qualified", QualifiedLead.source_url.in_(source_urls)).all()
        with Path(output_path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(lead_row(lead) for lead in qualified)
        for seed, status in results:
            print(f"row={seed.row_number} company={seed.company_name!r} status={status}")
        print(f"qualified_rows_exported={len(qualified)} output={output_path}")
        print("google_sheets_sync=disabled")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv")
    parser.add_argument("--output", default="manual_qualified.csv")
    args = parser.parse_args()
    asyncio.run(run(args.input_csv, args.output))


if __name__ == "__main__":
    main()
