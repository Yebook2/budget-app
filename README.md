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

## 실행 로그와 시간 측정

기본 실행에서는 명령 결과만 표시합니다. macOS/Linux에서는 환경 변수
`BUDGET_APP_LOG=1`을 설정하면 실행 로그와 소요 시간이 표준 오류로 출력됩니다.

```sh
BUDGET_APP_LOG=1 python -m budget_app list --limit 3
```

실행 로그 예시입니다. 실제 시간은 데이터와 실행 환경에 따라 달라집니다.

```text
[INFO] 명령 실행 시작
[INFO] 실행시간 0.003초
[INFO] 명령 실행 종료 (코드 0)
```

CLI 진입 함수 `main`에는 `@log_execution`, `@measure_execution`,
`@handle_errors`를 바깥쪽부터 순서대로 적용합니다. 로깅은 시작과 종료 코드를
표시하고, 시간 측정은 단조 증가 시계인 `perf_counter()`로 성공 및 실패 경로의
경과 시간을 기록합니다. 예외 처리는 사용자에게 원인과 힌트를 출력하고
종료 코드 1을 반환합니다. 인자 파서의 도움말과 인자 오류는 각각 0과 2를
유지합니다. 로그에는 명령 인자, 거래 금액, 메모 등 입력값을 기록하지 않습니다.

## 영구 저장 형식 선택

| 기준 | JSONL | CSV |
| --- | --- | --- |
| 구조 | 행마다 키와 값을 가진 JSON 객체. 정수와 태그 배열을 그대로 표현 | 헤더를 공유하는 평평한 표. 금액을 정수로 바꾸고 태그를 분리하는 규칙 필요 |
| 스트리밍 | 한 줄씩 읽어 거래 객체로 변환. 실제 개행은 문자열 안에서 이스케이프 | `csv.DictReader`로 레코드 단위 처리. 따옴표로 감싼 메모의 개행은 여러 물리적 줄에 걸칠 수 있음 |
| 임의 접근 | 가변 길이 레코드. ID나 날짜로 바로 찾으려면 별도 위치 인덱스 필요 | 가변 길이 레코드. 인용된 개행을 고려한 위치 인덱스 필요 |
| 크기 | 행마다 키를 반복하므로 이 데이터 모델에서 저장 공간이 더 들 수 있음 | 열 이름을 한 번만 기록해 같은 구조의 행을 간결하게 저장 |
| 호환성 | Python 표준 `json`으로 읽고 쓰기 쉬움. 스프레드시트에서는 보통 변환 필요 | 스프레드시트와 다른 가계부에서 교환하기 쉬움. 헤더와 인코딩 규칙 합의 필요 |

거래는 정수 금액과 태그 배열을 보존해야 하므로 JSONL을 영구 형식으로 선택했습니다.
CSV는 가계부 내역을 다른 도구와 주고받을 때 사용합니다. 두 형식 모두 ID 검색
인덱스가 없으면 순차 탐색이 필요하며, 수정·삭제는 임시 파일을 완성한 뒤 교체합니다.

## 거래 10만 건 프로파일링

macOS arm64 Apple M5 Pro와 Python 3.13.17에서 합성 거래 100,000건
(14,509,721바이트)을 측정했습니다. 거래 날짜는 2024년에 분산시켰고,
출력을 폐기한 실제 CLI 프로세스의 3회 경과 시간 중앙값과 별도 cProfile
실행 1회의 시간을 기록했습니다. 두 시간의 차이에는 프로파일러 오버헤드가 포함됩니다.

| 명령 | 실제 경과 시간 중앙값 | cProfile 총 시간 | 주요 관측 |
| --- | ---: | ---: | --- |
| `list --limit 10` | 0.522초 | 1.217초 | 100,000건을 SQLite로 전달. `executemany` 누적 1.199초에는 제너레이터의 읽기·직렬화 포함. SQLite 호출 자체 0.101초, `_asdict_inner` 자체 0.192초 |
| `search --from 2024-01-01 --to 2024-01-31 --category food` | 0.233초 | 0.534초 | 3,006건이 일치했지만 원본 100,000건을 읽고 검증. `transactions` 누적 0.465초 |
| `summary --month 2024-01` | 0.216초 | 0.511초 | 8,471건을 집계하기 위해 원본 전체를 읽음. `transactions` 누적 0.465초 |

아래 명령은 임시 폴더에서 같은 형태의 합성 데이터를 생성하고, CLI 경과
시간과 cProfile 상위 호출을 출력합니다.

```sh
python profile_budget.py
```

개선 우선순위는 아래와 같습니다.

1. 제한된 최신순 조회에는 크기 N의 힙을 사용합니다. 파일은 한 번 읽되 상위 N건만
   유지해 SQLite 삽입과 JSON 재직렬화를 줄입니다. 날짜가 같을 때의 저장 순서와
   빈 결과를 회귀 검증합니다.
2. 반복적인 기간 검색은 원본 위치를 기록하는 날짜 인덱스를 검토합니다.
   검색 패턴에 따라 날짜·카테고리 복합 인덱스도 비교합니다. 원자적 교체 후
   인덱스가 이전 파일을 가리키지 않도록 원본 버전을 확인하고 필요 시 재구축합니다.
3. 수십만 건을 반환하는 검색의 임시 정렬은 5,000건 단위 삽입과 인덱스 생성
   시점 변경을 각각 비교합니다. 현재 측정에서는 JSON 처리 비용이 확인됐으므로,
   병렬 I/O는 더 큰 파일과 느린 저장장치에서 읽기 시간이 지배적일 때 검토합니다.
   개행 경계의 중복·누락과 동일 날짜 순서를 확인합니다.

변경 전후는 동일한 생성 데이터로 비교하고, 100,000건과 1,000,000건에서
경과 시간과 최대 메모리를 기록합니다.
