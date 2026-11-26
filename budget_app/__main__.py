"""명령줄 입력과 결과 출력."""

import argparse
import csv
import logging
import os
import sqlite3
import sys
from collections.abc import Callable, Iterable
from functools import wraps
from pathlib import Path
from time import perf_counter

from .models import Transaction, parse_tags, positive, valid_date, valid_month
from .service import Ledger
from .storage import LedgerStore


LOGGER = logging.getLogger("budget_app")


def log_execution(command: Callable[[], int]) -> Callable[[], int]:
    @wraps(command)
    def wrapped() -> int:
        LOGGER.info("명령 실행 시작")
        exit_code = 1
        try:
            exit_code = command()
            return exit_code
        except SystemExit as error:
            if isinstance(error.code, int):
                exit_code = error.code
            raise
        finally:
            LOGGER.info("명령 실행 종료 (코드 %d)", exit_code)

    return wrapped


def measure_execution(command: Callable[[], int]) -> Callable[[], int]:
    @wraps(command)
    def wrapped() -> int:
        started = perf_counter()
        try:
            return command()
        finally:
            LOGGER.info("실행시간 %.3f초", perf_counter() - started)

    return wrapped


def handle_errors(command: Callable[[], int]) -> Callable[[], int]:
    @wraps(command)
    def wrapped() -> int:
        try:
            return command()
        except (EOFError, KeyboardInterrupt):
            print("\n[오류] 입력이 중단되었습니다. 명령을 다시 실행하세요.", file=sys.stderr)
            return 1
        except (ValueError, OSError, csv.Error, sqlite3.Error, KeyError, TypeError) as error:
            print(f"[오류] {error}\n[힌트] --help와 입력값, 파일 경로 및 형식을 확인하세요.", file=sys.stderr)
            return 1

    return wrapped


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="python -m budget_app", description="나만의 용돈 기입장")
    app.add_argument("--data-dir", type=Path, default=Path("data"), help="저장 폴더 (기본값 ./data)")
    commands = app.add_subparsers(dest="command", required=True)
    commands.add_parser("add", help="대화형으로 거래 추가")
    listing = commands.add_parser("list", help="최근 거래 조회")
    listing.add_argument("--limit", default="10", metavar="N", help="최대 조회 건수 (기본값 10)")
    search = commands.add_parser("search", help="조건으로 거래 검색")
    export = commands.add_parser("export", help="기간별 거래를 CSV로 저장")
    for command in (search, export):
        command.add_argument("--from", dest="start", metavar="YYYY-MM-DD")
        command.add_argument("--to", dest="end", metavar="YYYY-MM-DD")
    search.add_argument("--category")
    search.add_argument("--type", choices=("income", "expense"))
    search.add_argument("--q", help="메모 키워드")
    search.add_argument("--tag")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--month", metavar="YYYY-MM")
    importing = commands.add_parser("import", help="CSV 거래 가져오기")
    importing.add_argument("--from", dest="source", type=Path, required=True)
    update = commands.add_parser("update", help="지정한 옵션의 거래 필드 수정")
    delete = commands.add_parser("delete", help="ID로 거래 삭제")
    for command in (update, delete):
        command.add_argument("--id", required=True)
    update.add_argument("--type", choices=("income", "expense"))
    for field in ("date", "category", "amount", "memo", "tags"):
        update.add_argument("--" + field)
    summary = commands.add_parser("summary", help="월별 수입, 지출 및 예산 조회")
    summary.add_argument("--month", required=True, metavar="YYYY-MM")
    summary.add_argument("--top", default="3", metavar="N")
    budget = commands.add_parser("budget", help="월 예산 설정 및 조회")
    budget_actions = budget.add_subparsers(dest="action", required=True)
    for action in ("set", "get"):
        budget_action = budget_actions.add_parser(action)
        budget_action.add_argument("--month", required=True, metavar="YYYY-MM")
        if action == "set":
            budget_action.add_argument("--amount", required=True)
    categories = commands.add_parser("category", help="카테고리 추가, 조회 및 삭제")
    category_actions = categories.add_subparsers(dest="action", required=True)
    for action in ("add", "list", "remove"):
        category_actions.add_parser(action)
    return app


def show_rows(rows: Iterable[Transaction]) -> None:
    count = 0
    for row in rows:
        tags = ", ".join(row.tags)
        print(f"{row.id} | {row.date} | {row.type:7} | {row.category} | {row.amount:,} | {row.memo} | {tags}")
        count += 1
    if count == 0:
        print("거래 데이터 없음")


def date_range(args: argparse.Namespace) -> tuple[str | None, str | None]:
    start = valid_date(args.start) if args.start is not None else None
    end = valid_date(args.end) if args.end is not None else None
    if start and end and start > end:
        raise ValueError("--from은 --to와 같거나 앞선 날짜여야 합니다.")
    return start, end


def manage_categories(ledger: Ledger, action: str) -> None:
    names = ledger.store.categories()
    if action == "list":
        for name in sorted(names):
            print(f"- {name}")
        if not names:
            print("등록된 카테고리 없음. category add로 등록하세요.")
        return

    name = input("카테고리명: ").strip()
    if not name:
        raise ValueError("카테고리명을 입력하세요.")
    if action == "remove":
        ledger.remove_category(name)
        print(f"[삭제 완료] category={name}")
    else:
        if name in names:
            raise ValueError(f"이미 등록된 카테고리입니다: {name}. category list에서 확인하세요.")
        names.add(name)
        ledger.store.save_categories(names)
        print(f"[저장 완료] category={name}")


def show_summary(ledger: Ledger, month: str, top: int) -> None:
    count, income, expense, totals = ledger.summary(month)
    if not count:
        print(f"{month} 거래 데이터 없음")
    print(f"총 수입: {income:,}원\n총 지출: {expense:,}원\n잔액: {income - expense:,}원")
    budget = ledger.store.budgets().get(month)
    if budget is not None:
        print(f"예산: {budget:,}원 (사용률 {expense / budget:.1%})")
        if expense > budget:
            print(f"[경고] 예산을 {expense - budget:,}원 초과했습니다.")
    if totals:
        print(f"\n지출 TOP {top}")
        ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        for index, (category, amount) in enumerate(ranked[:top], 1):
            print(f"{index}) {category} {amount:,}원")


@log_execution
@measure_execution
@handle_errors
def main() -> int:
    args = parser().parse_args()
    store = LedgerStore(args.data_dir)
    ledger = Ledger(store)
    match args.command:
        case "add":
            known = store.categories()
            if not known:
                raise ValueError("category add로 카테고리를 먼저 등록하세요.")
            date = valid_date(input("날짜(YYYY-MM-DD): ").strip())
            kind = input("타입(income/expense): ").strip()
            if kind not in {"expense", "income"}:
                raise ValueError("거래 유형은 income 또는 expense로 입력하세요.")
            print("등록된 카테고리: " + ", ".join(sorted(known)))
            category = input("카테고리: ").strip()
            ledger.validate_category(category, known)
            amount = positive(input("금액(양수 정수): ").strip())
            memo = input("메모(선택): ")
            tags = parse_tags(input("태그(쉼표로 구분, 선택): "))
            row = ledger.add(date=date, type=kind, category=category, amount=amount, memo=memo, tags=tags)
            print(f"[저장 완료] id={row.id}")
        case "list":
            show_rows(ledger.newest(store.transactions(), positive(args.limit)))
        case "search":
            start, end = date_range(args)
            rows = ledger.matching(start=start, end=end, category=args.category,
                                   kind=args.type, query=args.q, tag=args.tag)
            show_rows(ledger.newest(rows))
        case "summary":
            show_summary(ledger, valid_month(args.month), positive(args.top))
        case "budget":
            month = valid_month(args.month)
            budgets = store.budgets()
            if args.action == "set":
                budgets[month] = positive(args.amount)
                store.save_budgets(budgets)
                print(f"[저장 완료] {month} 예산 {budgets[month]:,}원")
            elif month in budgets:
                print(f"{month} 예산 {budgets[month]:,}원")
            else:
                print(f"{month} 예산이 설정되어 있지 않습니다.")
        case "category":
            manage_categories(ledger, args.action)
        case "update":
            changes = {field: getattr(args, field) for field in
                       ("date", "type", "category", "amount", "memo", "tags")
                       if getattr(args, field) is not None}
            if not changes:
                raise ValueError("수정할 필드를 옵션으로 하나 이상 지정하세요. update --help를 확인하세요.")
            if "amount" in changes:
                changes["amount"] = positive(changes["amount"])
            if "tags" in changes:
                changes["tags"] = parse_tags(changes["tags"])
            ledger.change(args.id, changes)
            print(f"[수정 완료] id={args.id}")
        case "delete":
            ledger.change(args.id, None)
            print(f"[삭제 완료] id={args.id}")
        case "import":
            count = ledger.import_csv(args.source)
            print(f"[완료] {count}건을 가져왔습니다.")
        case "export":
            start, end = date_range(args)
            month = valid_month(args.month) if args.month is not None else None
            if (start is None) != (end is None) or not (month or start):
                raise ValueError("--month 또는 --from과 --to를 함께 지정하세요.")
            count = ledger.export_csv(args.out, ledger.matching(start=start, end=end, month=month))
            print(f"[완료] {args.out} ({count}건)")
    return 0


if __name__ == "__main__":
    if os.environ.get("BUDGET_APP_LOG") == "1":
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    sys.exit(main())
