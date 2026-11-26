"""거래 모델과 공통 입력 검증."""

import re
from dataclasses import dataclass
from datetime import date


def valid_date(value: str) -> str:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력하세요.")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("달력에 존재하는 날짜를 입력하세요. 예: 2024-01-15") from error
    return value


def valid_month(value: str) -> str:
    valid_date(value + "-01")
    return value


def positive(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
        raise ValueError("금액과 개수는 1 이상의 정수로 입력하세요.")
    return int(value)


def parse_tags(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        valid_date(self.date)
        if self.type not in {"income", "expense"}:
            raise ValueError("거래 유형은 income 또는 expense로 입력하세요.")
        if type(self.amount) is not int or self.amount <= 0:
            raise ValueError("금액은 1 이상의 정수로 입력하세요.")
        if not self.category.strip():
            raise ValueError("카테고리명을 입력하세요.")
        if not isinstance(self.memo, str) or not isinstance(self.tags, (list, tuple)):
            raise ValueError("메모 또는 태그 형식이 올바르지 않습니다.")
        if any(not isinstance(tag, str) for tag in self.tags):
            raise ValueError("태그는 문자열이어야 합니다.")
        object.__setattr__(self, "tags", tuple(self.tags))
