"""Generate synthetic transactions and profile normal CLI entry points."""

import cProfile
from datetime import date, timedelta
import io
import json
from pathlib import Path
import pstats
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter


def main() -> None:
    with TemporaryDirectory() as directory:
        data = Path(directory)
        path = data / "transactions.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for index in range(100_000):
                row = {
                    "id": str(index),
                    "date": (date(2024, 1, 1) + timedelta(days=(index * 37) % 366)).isoformat(),
                    "type": "income" if index % 8 == 0 else "expense",
                    "amount": 1000 + index % 5000,
                    "category": ("food", "transport", "salary")[index % 3],
                    "memo": "sample transaction",
                    "tags": ["sample"],
                }
                stream.write(json.dumps(row) + "\n")
        print(f"Python {sys.version.split()[0]}, {path.stat().st_size:,} bytes")
        for args in [
            ("list", "--limit", "10"),
            ("search", "--from", "2024-01-01", "--to", "2024-01-31", "--category", "food"),
            ("summary", "--month", "2024-01"),
        ]:
            command = ["-m", "budget_app", "--data-dir", directory, *args]
            print(" ".join(args), flush=True)
            for _ in range(3):
                started = perf_counter()
                subprocess.run([sys.executable, *command], stdout=subprocess.DEVNULL, check=True)
                print(f"wall {perf_counter() - started:.3f}s")
            output = data / "profile.stats"
            subprocess.run(
                [sys.executable, "-m", "cProfile", "-o", str(output), *command],
                stdout=subprocess.DEVNULL,
                check=True,
            )
            report = io.StringIO()
            pstats.Stats(str(output), stream=report).strip_dirs().sort_stats("tottime").print_stats(11)
            print(report.getvalue())


if __name__ == "__main__":
    main()
