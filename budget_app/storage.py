"""JSONL 저장 및 같은 디렉터리에서의 원자적 파일 교체."""

import json
import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, TextIO

from .models import Transaction


@contextmanager
def atomic_writer(path: Path) -> Iterator[TextIO]:
    """쓰기와 검증이 끝난 파일만 기존 파일과 교체한다."""
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class LedgerStore:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.transaction_path = directory / "transactions.jsonl"
        self.category_path = directory / "categories.jsonl"
        self.budget_path = directory / "budgets.jsonl"
        for path in (self.transaction_path, self.category_path, self.budget_path):
            if not path.exists():
                self.write(path, ())

    @staticmethod
    def read(path: Path) -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("JSON 객체가 필요합니다.")
                except ValueError as error:
                    raise ValueError(f"{path.name} {number}행의 JSONL 형식이 잘못되었습니다.") from error
                yield record

    @staticmethod
    def write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
        with atomic_writer(path) as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def transactions(self) -> Iterator[Transaction]:
        for row in self.read(self.transaction_path):
            try:
                yield Transaction(**row)
            except (TypeError, ValueError, AttributeError) as error:
                raise ValueError(f"transactions.jsonl의 거래 데이터가 잘못되었습니다. {error}") from error

    def save_transactions(self, rows: Iterable[Transaction]) -> None:
        self.write(self.transaction_path, (asdict(row) for row in rows))

    def categories(self) -> set[str]:
        return {row["name"] for row in self.read(self.category_path)}

    def save_categories(self, names: set[str]) -> None:
        self.write(self.category_path, ({"name": name} for name in sorted(names)))

    def budgets(self) -> dict[str, int]:
        return {row["month"]: row["amount"] for row in self.read(self.budget_path)}

    def save_budgets(self, budgets: dict[str, int]) -> None:
        self.write(
            self.budget_path,
            ({"month": month, "amount": amount} for month, amount in sorted(budgets.items())),
        )
