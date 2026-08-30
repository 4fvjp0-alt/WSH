# 여행 정산 계산기

같이 여행 다녀와서 "누가 누구한테 얼마 보내면 되는지"를 1원 오차 없이 계산해 주는 프로그램입니다.
파이썬 표준 라이브러리만 씁니다. 설치할 것도, 서버도, API 키도 없습니다.

```bash
cd travel-settle
python3 -m settle demo      # 예제 여행으로 바로 확인
```

## 왜 또 정산 앱인가

정산은 "돈이 1원도 안 새는 것"이 전부입니다. 그래서 이 프로그램은
**계산 엔진을 먼저 만들고, 스스로 검증하게 한 다음**, 그 위에 화면을 얹었습니다.

- 모든 금액을 **정수(최소 단위)** 로만 다룹니다. 부동소수점을 쓰지 않으므로 `0.1+0.2` 류의 오차가 없습니다.
- 분배는 유리수로 정확히 계산하고 **최대잔여법**으로 정수에 떨어뜨립니다. 분할 합계는 언제나 원본과 정확히 일치합니다.
- 나머지 1원은 지출마다 **다른 사람에게 회전**시킵니다. 매번 같은 사람이 손해 보지 않습니다.
- 계산할 때마다 **불변식 11개를 스스로 검사**합니다. 하나라도 깨지면 결과를 내놓지 않습니다.
- **무작위 여행 10만 건**으로 폐루프 검증을 돌려 통과했습니다.

## 할 수 있는 것

| 상황 | 지원 |
|------|------|
| 인원 추가·수정, 여러 여행 분리 관리 | ✔ |
| 카드 문자·결제 알림 붙여넣기로 일괄 등록 | ✔ |
| 결제내역 **캡쳐 이미지**로 등록 (Claude Code CLI 활용) | ✔ |
| 수동 등록 (대화형 / 플래그) | ✔ |
| 카테고리 자동 분류 + 학습 | ✔ |
| 결제한 사람 (한 건을 여러 장의 카드로 나눠 결제 포함) | ✔ |
| 균등 / 인분(가중치) / 금액 지정 / 비율 분할 | ✔ |
| **"누가 얼마 더 내기로 했으면 그거 빼고 나누기"** | ✔ |
| 중간 합류·조기 귀가 (참여 기간별 자동 분담) | ✔ |
| 공금(회비) 걷어서 쓰고 남은 돈 환급까지 | ✔ |
| 여행 중 이미 주고받은 돈 반영 | ✔ |
| 다중 통화 + 환율 (엔·달러 결제) | ✔ |
| 취소·환불 (음수 지출) | ✔ |
| 개인 지출 정산 제외 | ✔ |
| 최소 횟수 송금안 (최적해 계산) | ✔ |
| 100원/1000원 단위 반올림 송금 | ✔ |
| 카톡에 붙여넣을 요약, CSV/JSON 내보내기 | ✔ |

## 5분 사용법

```bash
cd travel-settle

# 1) 여행 만들고 사람 넣기
python3 -m settle trip new "제주 3박4일" --start 2025-09-05 --end 2025-09-08 --rounding 100
python3 -m settle member add 민수 지영 현우
python3 -m settle member add 하린 --weight 0.5              # 아이는 0.5인분
python3 -m settle member set 현우 --joined 09-06             # 하루 늦게 합류

# 2) 지출 등록
python3 -m settle expense add --title "흑돼지" --amount 120,000 --payer 민수 --date 09-05
python3 -m settle expense add --title "렌터카" --amount 90000 --payer "지영:60000,현우:30000"
python3 -m settle expense add --title "펜션" --amount 320000 --payer 지영 \
        --split weight --values "민수=1,지영=1,현우=1,하린=0.5"

#    "현우가 미안해서 3만원 더 내기로 함"
python3 -m settle expense add --title "고깃집" --amount 150000 --payer 현우 --extra "현우=30000"

#    기념품은 개인 지출이라 정산에서 제외
python3 -m settle expense add --title "기념품" --amount 40000 --payer 지영 --personal

# 3) 카드 문자 그대로 붙여넣기 (가장 정확하고 빠른 입력 방법)
python3 -m settle import text --payer 민수

# 4) 캡쳐 이미지로 등록
python3 -m settle import image ~/Downloads/결제내역.png --payer 민수

# 5) 정산
python3 -m settle settle
python3 -m settle share          # 카톡에 붙여넣을 요약
python3 -m settle verify         # 검증 결과 보기
```

인자를 생략하면 물어봅니다. `python3 -m settle expense add` 만 쳐도 됩니다.

## "더 내기로 한 금액" 이 계산되는 방식

가장 헷갈리는 부분이라 규칙을 명확히 정해 두었습니다.

```
총액 100,000원 / 4명 / "민수가 40,000원 더 내기로 함"

  1. 먼저 민수 몫으로 40,000원을 떼어 놓는다
  2. 남은 60,000원을 4명이 균등 분할 → 각 15,000원
  3. 민수 부담 = 40,000 + 15,000 = 55,000원
     나머지 세 명  = 각 15,000원
```

즉 **더 내기로 한 금액을 빼고 나머지를 나눈 뒤, 그 사람에게 다시 더합니다.**
지출 건별로도, 여러 건에 걸쳐서도 쓸 수 있습니다.

## 공금(회비)을 다루는 방식

공금은 **"가상 멤버"** 로 모델링했습니다.

- 회비 입금 = `멤버 → 공금` 송금
- 공금 결제 = 결제자가 `공금` 인 지출
- 그러면 **남은 공금 환급이 최종 송금안에 자동으로 들어옵니다** (`공금 → 민수 32,000원`)

덕분에 회비·중간송금·환급이 전부 같은 메커니즘 하나로 처리되고, 수지도 자동으로 검증됩니다.

```bash
python3 -m settle pot in 민수 300000
python3 -m settle pot in 지영 300000
python3 -m settle expense add --title "숙소" --amount 63000 --currency JPY --payer 공금
```

## 폐루프 검증

계산할 때마다 아래 항목을 **엔진이 스스로 검사**합니다. `settle` 실행 시 하나라도 깨지면 자동으로 표시되고,
`verify` 로 항상 볼 수 있습니다.

| 코드 | 검사 내용 |
|------|-----------|
| I1 | 지출별 분할 합계가 각 지출 금액과 정확히 일치 |
| I2 | 지출별 결제액 합계가 각 지출 금액과 정확히 일치 |
| I3 | 전체 결제액 = 전체 부담액 = 총 지출 |
| I4 | 모든 사람의 잔액 합계가 0 |
| I5 | **역검증** — 산출된 송금안을 실제로 적용하면 전원 잔액이 0 |
| I6 | 보내면서 동시에 받는 사람이 없음 |
| I7 | 송금액은 모두 양수이고 송금 횟수가 최소 범위 안 |
| I8 | 반올림 단위를 설정했으면 모든 송금액이 그 배수 |
| I9 | 공금 수지 일치 (걷은 돈 = 쓴 돈 + 남은 돈) |
| I10 | 정산 제외 개인 지출이 정산 총액에 섞이지 않음 |
| X1 | 총액 독립 재계산 일치 (이중 기장) |

그리고 이 불변식들을 **무작위로 생성한 여행**에 대해 반복 검증합니다.
사람이 생각해내지 못한 조합(환불 + 다중 결제자 + 부분 참여 + 다중 통화 + 반올림이 동시에 겹치는 경우 등)은 여기서 잡힙니다.

```bash
python3 -m settle verify --fuzz 20000     # 무작위 여행 2만 건 자가검사
python3 tests/run.py                       # 전체 테스트 (132개)
python3 tests/run.py --fuzz 50000          # 검증 강도 올리기
```

실패하면 시드가 출력되고, 그 시드로 언제든 똑같이 재현됩니다.

## 캡쳐 이미지 등록이 동작하는 방식

별도 OCR 서비스나 API 키를 쓰지 않고, 이미 쓰고 있는 **Claude Code CLI(`claude`)** 를 그대로 호출합니다.
구독 플랜 안에서 동작하고, 이미지가 외부 OCR 업체로 나가지 않습니다.

```
캡쳐 이미지 → claude -p (Read 도구로 이미지 판독) → JSON → 검토 화면 → 장부
```

**추출 결과를 절대 자동 확정하지 않습니다.** 인식 신뢰도가 낮으면 경고를 띄우고,
사람이 확인·수정한 뒤에만 장부에 들어갑니다. 잘못 읽은 금액이 조용히 정산에 섞이는 것보다 한 번 더 묻는 쪽이 낫습니다.

| 환경변수 | 용도 |
|----------|------|
| `TRAVEL_SETTLE_CLAUDE_CMD` | `claude` 실행 경로가 다를 때 |
| `TRAVEL_SETTLE_OCR_TIMEOUT` | 응답 대기 시간(초), 기본 180 |
| `TRAVEL_SETTLE_DATA` | 장부 파일 경로, 기본 `~/.travel-settle/data.json` |

`claude` 가 없으면 안내 메시지를 띄우고 `import text` 를 권합니다.
실제로 **문자 붙여넣기가 이미지보다 훨씬 정확**해서, 카드 문자를 받는다면 그쪽이 주력 입력 경로입니다.

## 명령어 전체

```
trip      new / list / use / show / set / delete
member    add / list / set / remove
rate      set / list                          환율
expense   add / list / show / edit / remove
pot       in                                  회비 입금
transfer  add / list / remove                 이미 주고받은 돈
import    text / image / json
settle                                        정산 결과
share                                         메신저용 요약
verify    [--fuzz N]                          폐루프 검증
export    json <경로> / csv <경로>
demo                                          예제 여행
```

`python3 -m settle <명령> --help` 로 각 옵션을 볼 수 있습니다.

## 구조

정산 엔진은 화면에 전혀 의존하지 않는 순수 모듈입니다. 나중에 웹이나 앱으로 확장할 때 이 부분을 그대로 씁니다.

```
settle/
  money.py        정수 금액 연산, 정확 분배, 반올림, 환산   ← 엔진
  models.py       스키마와 직렬화                          ← 엔진
  split.py        분할 규칙 (균등/가중치/금액지정/비율 + 조정액)  ← 엔진
  engine.py       잔액 집계와 최소 송금 계산                ← 엔진
  invariants.py   폐루프 불변식 검사                        ← 엔진
  fuzz.py         무작위 여행 생성기 (검증용)
  parse_text.py   카드 문자·결제 알림 파서
  ocr_claude.py   캡쳐 이미지 → Claude Code CLI → 거래내역
  category.py     카테고리 자동 분류 + 학습
  store.py        JSON 저장 (원자적 쓰기 + 백업)
  report.py       결과 출력
  textui.py       한글 폭을 고려한 표 정렬
  cli.py          명령행 인터페이스
tests/
  test_money.py test_split.py test_engine.py    단위 테스트
  test_scenarios.py                             현실 상황 19종
  test_property.py                              무작위 폐루프 검증
  test_parse_text.py test_ocr_claude.py
  test_store.py test_cli.py
  run.py                                        전체 실행기
```

## 최소 송금 계산

잔액을 0으로 만드는 송금 조합은 여러 가지인데, 횟수가 적을수록 좋습니다.

- 인원이 12명 이하면 **부분집합 DP**로 "합이 0인 그룹"을 최대한 잘게 쪼갭니다. 그룹이 g개면 송금은 `n-g` 회로 줄어듭니다. 이게 실제 최소 횟수입니다.
- 그보다 많으면 채권자·채무자를 큰 쪽부터 맞물리는 그리디로 계산합니다 (`n-1` 회 이하 보장).

DP가 실제 최적해를 내는지는 완전탐색과 대조해 테스트로 확인합니다.

## 데이터

`~/.travel-settle/data.json` 하나에 전부 들어 있습니다. 쓰기는 임시 파일 후 원자적 교체라 도중에 죽어도 원본이 남고,
덮어쓰기 전 `.bak` 백업을 만듭니다. `export json` 으로 백업하고 `import json` 으로 되돌릴 수 있습니다.

## 라이선스

MIT
