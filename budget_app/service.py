"""CRUD, 검색, 월별 집계와 CSV 입출력."""

import csv
import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from dataclasses import asdict, replace
from itertools import chain
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import Transaction, parse_tags, positive
from .storage import LedgerStore, atomic_writer

FIELDS = ("date", "type", "category", "amount", "memo", "tags")
REQUIRED = FIELDS[:4]


class Ledger:
    def __init__(self, store: LedgerStore) -> None:
        self.store = store

    def validate_category(self, name: str, known: set[str]) -> None:
        if name not in known:
            raise ValueError(f"등록되지 않은 카테고리입니다: {name}. category add로 등록하세요.")

    def add(self, **fields: Any) -> Transaction:
        row = Transaction(id=str(uuid4()), **fields)
        self.validate_category(row.category, self.store.categories())
        self.store.save_transactions(chain(self.store.transactions(), (row,)))
        return row

    def change(self, transaction_id: str, changes: dict[str, Any] | None) -> None:
        def rows() -> Iterator[Transaction]:
            found = False
            for row in self.store.transactions():
                if row.id != transaction_id:
                    yield row
                    continue
                found = True
                if changes is not None:
                    updated = replace(row, **changes)
                    self.validate_category(updated.category, self.store.categories())
                    yield updated
            if not found:
                raise ValueError(f"거래 ID를 찾을 수 없습니다: {transaction_id}. list에서 확인하세요.")

        self.store.save_transactions(rows())

    def matching(
        self, *, start: str | None = None, end: str | None = None,
        month: str | None = None, category: str | None = None,
        kind: str | None = None, query: str | None = None, tag: str | None = None,
    ) -> Iterator[Transaction]:
        keyword = query.casefold() if query else ""
        for row in self.store.transactions():
            if start and row.date < start or end and row.date > end:
                continue
            if month and not row.date.startswith(month + "-"):
                continue
            if category is not None and row.category != category or kind and row.type != kind:
                continue
            if keyword not in row.memo.casefold() or tag is not None and tag not in row.tags:
                continue
            yield row

    @staticmethod
    def newest(rows: Iterator[Transaction], limit: int | None = None) -> Iterator[Transaction]:
        # SQLite 임시 파일에 정렬을 위임해 전체 거래를 메모리에 쌓지 않는다.
        with closing(sqlite3.connect("")) as db:
            db.execute("CREATE TABLE records (day TEXT, payload TEXT)")
            db.execute("CREATE INDEX chronological ON records (day)")
            db.executemany(
                "INSERT INTO records VALUES (?, ?)",
                ((row.date, json.dumps(asdict(row), ensure_ascii=False)) for row in rows),
            )
            cursor = db.execute(
                "SELECT payload FROM records ORDER BY day DESC, rowid DESC LIMIT ?",
                (-1 if limit is None else limit,),
            )
            for (payload,) in cursor:
                yield Transaction(**json.loads(payload))

    def remove_category(self, name: str) -> None:
        names = self.store.categories()
        self.validate_category(name, names)
        if any(self.matching(category=name)):
            raise ValueError("거래에서 사용 중인 카테고리입니다. 해당 거래를 먼저 수정하거나 삭제하세요.")
        names.remove(name)
        self.store.save_categories(names)

    def summary(self, month: str) -> tuple[int, int, int, Counter[str]]:
        count = income = expense = 0
        totals: Counter[str] = Counter()
        for row in self.matching(month=month):
            count += 1
            if row.type == "income":
                income += row.amount
            else:
                expense += row.amount
                totals[row.category] += row.amount
        return count, income, expense, totals

    def import_csv(self, source: Path) -> int:
        known = self.store.categories()
        count = 0
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames or []
            if not set(REQUIRED).issubset(headers) or len(headers) != len(set(headers)):
                raise ValueError("CSV 헤더에 date,type,category,amount가 각각 한 번씩 필요합니다.")

            def incoming() -> Iterator[Transaction]:
                nonlocal count
                for record in reader:
                    try:
                        if None in record or any(record[field] is None for field in REQUIRED):
                            raise ValueError("열 개수가 CSV 헤더와 일치해야 합니다.")
                        category = record["category"].strip()
                        self.validate_category(category, known)
                        transaction = Transaction(
                            id=str(uuid4()), date=record["date"].strip(),
                            type=record["type"].strip(), category=category,
                            amount=positive(record["amount"].strip()),
                            memo=record.get("memo") or "", tags=parse_tags(record.get("tags") or ""),
                        )
                    except ValueError as error:
                        raise ValueError(f"CSV {reader.line_num}행: {error}") from error
                    count += 1
                    yield transaction

            self.store.save_transactions(chain(self.store.transactions(), incoming()))
        return count

    def export_csv(self, target: Path, rows: Iterator[Transaction]) -> int:
        if target.resolve() in {
            self.store.transaction_path.resolve(),
            self.store.category_path.resolve(),
            self.store.budget_path.resolve(),
        }:
            raise ValueError("저장 파일과 다른 CSV 출력 경로를 지정하세요.")
        count = 0
        with atomic_writer(target) as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            for row in rows:
                writer.writerow((row.date, row.type, row.category, row.amount, row.memo, ",".join(row.tags)))
                count += 1
        return count
