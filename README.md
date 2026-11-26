# 나만의 용돈 기입장

Python 3.10 이상에서 실행하는 콘솔 가계부입니다. Python 표준 라이브러리만 사용합니다.

## 실행

압축을 풀고 이 README가 있는 폴더에서 실행합니다.

```sh
python -m budget_app --help
python -m budget_app category add
python -m budget_app add
python -m budget_app list --limit 3
```

첫 실행 시 저장 파일 세 개를 생성합니다. 카테고리가 비어 있으면 `category add`로 먼저 등록합니다. 예를 들어 `food`를 등록한 다음 `add`에서 날짜 `2024-01-15`, 타입 `expense`, 카테고리 `food`, 금액 `15000`, 메모 `점심`, 태그 `meal`을 순서대로 입력합니다. 저장 성공 메시지에서 거래 ID를 확인할 수 있습니다.

기본 저장 위치는 실행 폴더의 `./data`입니다. 다른 위치를 사용하려면 명령 앞에 `--data-dir`을 지정합니다.

```sh
python -m budget_app --data-dir ./practice list
```

## 명령 예시

```sh
python -m budget_app list
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
python -m budget_app budget set --month 2024-01 --amount 10000
python -m budget_app budget get --month 2024-01
python -m budget_app summary --month 2024-01 --top 3

python -m budget_app category list
python -m budget_app category remove

python -m budget_app update --id ID --amount 18000 --memo "친구와 점심" --tags "meal,weekend"
python -m budget_app delete --id ID

python -m budget_app import --from input.csv
python -m budget_app export --out january.csv --month 2024-01
python -m budget_app export --out week.csv --from 2024-01-15 --to 2024-01-21
```

- `ID` 자리에는 `add`나 `list`에서 확인한 실제 ID를 넣습니다. `update`는 옵션 방식이며, 지정한 필드만 수정합니다. `--memo ""`와 `--tags ""`로 각각 값을 비울 수 있습니다.
- `list`는 기본 10건을 표시합니다. `list`와 `search`는 거래 날짜의 내림차순이며, 날짜가 같으면 저장 순서가 최근인 거래를 먼저 표시합니다.
- `search`는 지정한 모든 조건에 일치하는 거래를 찾습니다. 날짜 경계는 포함하며, 메모는 대소문자 구분 없이 부분 일치, 태그는 정확히 일치하는 항목을 찾습니다.
- `summary`의 잔액은 해당 월의 수입에서 지출을 뺀 값입니다. 예산 사용률은 해당 월 지출을 예산으로 나눈 값입니다. 지출이 예산을 초과하면 경고가 표시됩니다.
- `category add`와 `category remove`는 대화형입니다. 거래에 사용 중인 카테고리는 삭제가 제한됩니다.
- 각 명령과 하위 명령에서 `--help`를 사용할 수 있습니다. 정상 종료 코드는 0이며 입력이나 실행 오류는 0 이외의 코드로 종료합니다.

## 저장 파일

각 파일은 UTF-8 JSONL 형식으로, 한 줄에 JSON 객체 하나가 들어갑니다.

| 파일 | 저장 필드 |
| --- | --- |
| `transactions.jsonl` | `id`, `type`, `date`, `amount`, `category`, `memo`, `tags` |
| `categories.jsonl` | `name` |
| `budgets.jsonl` | `month`, `amount` |

거래 조회와 집계는 제너레이터로 JSONL을 한 줄씩 읽습니다. 최신순 조회에서는 SQLite 임시 저장소로 정렬합니다. 영구 데이터는 위의 JSONL 세 파일에 저장됩니다. 변경 시 같은 폴더의 임시 파일에 완성본을 쓰고 원자적으로 교체합니다. 같은 저장 폴더에 대한 쓰기 명령은 한 번에 하나씩 실행합니다.

## CSV 스키마

UTF-8과 헤더 행이 필요합니다. 가져오기 전에 CSV에서 사용하는 카테고리를 등록합니다.

| 열 | 필수 | 형식 |
| --- | --- | --- |
| `date` | 예 | `YYYY-MM-DD` |
| `type` | 예 | `income` 또는 `expense` |
| `category` | 예 | 등록된 카테고리 |
| `amount` | 예 | 양수 정수 |
| `memo` | 선택 | 문자열 |
| `tags` | 선택 | 쉼표로 구분한 문자열 |

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,점심,"meal,weekend"
```

가져오기는 새 거래 ID를 발급합니다. 유효하지 않은 행이 있으면 해당 CSV의 반영을 취소하고 오류를 표시합니다. 같은 CSV를 다시 가져오면 별도 거래로 추가됩니다. 내보내기는 월 또는 시작일과 종료일을 받아 해당 기간의 거래를 CSV로 저장합니다.

## 코드 구성

| 모듈 | 역할 |
| --- | --- |
| `models.py` | `Transaction` 데이터 클래스와 공통 입력 검증 |
| `storage.py` | `LedgerStore`의 파일 초기화, 스트리밍 읽기 및 원자적 쓰기 |
| `service.py` | `Ledger`의 거래 변경, 검색, 월별 집계 및 CSV 처리 |
| `__main__.py` | CLI, 대화형 입력, 결과 출력 및 `handle_errors` 데코레이터 |

예를 들어 `transactions() -> Iterator[Transaction]`은 호출자가 거래를 하나씩 소비할 수 있음을 보여주고, `save_transactions(rows: Iterable[Transaction])`은 저장소가 목록과 제너레이터를 모두 받을 수 있음을 명시합니다. `handle_errors`는 CLI 전반의 오류 출력과 종료 코드 처리를 한곳에 둡니다.
