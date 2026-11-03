# 로컬 세션 인계 — NH35A/NH38A 가격 추적 + 텔레그램 채널 전송

로컬 Claude Code 세션(텔레그램 채널이 연결된 세션)에 아래 프롬프트를 그대로 붙여 넣으세요.

---

NH35A / NH38A 일본 정품 무브먼트의 AliExpress 가격을 4시간마다 추적해서, 이 세션에 연결된 텔레그램 채널로 보내 줘.

1. 준비 (처음 한 번)
   - `git clone https://github.com/4fvjp0-alt/WSH && cd WSH && git checkout claude/disk-space-analysis-jONGY` (이미 있으면 `git pull`)
   - `cd watch_mod/price_tracker && npm init -y && npm i playwright && npx playwright install chromium`
2. 실행: `node watch_mod/price_tracker/track.js`
   - AliExpress 한국(원화) 검색 → `history.json` 기록 → `chart.png`, `latest.md` 갱신 → 콘솔에 요약 출력. 최저가면 `ALERT:` 줄이 나와요.
   - 봇 확인(캡차) 화면이 나오면 우회하지 말고 실패만 알려 줘. 가짜 기록은 넣지 마.
3. 결과 전송: 연결된 텔레그램 채널로 `latest.md` 요약(NH38A·NH35A 검증된 정품 최저가, 직전 대비 ▲▼, 기록상 최저, 상품 링크)과 `chart.png`를 보내 줘. `ALERT:`가 있으면 맨 앞에 "🔔 최저가!"를 붙여 줘.
4. 기록 저장: `git add watch_mod/price_tracker && git commit -m "Price tracker update <날짜 시각>" && git push`
5. 반복: 4시간마다 1~4를 반복해 줘 (`/loop 4h` 또는 이 세션의 예약 기능 사용).

---

- 클라우드 예약 작업(4시간마다, 전용 클라우드 세션)이 같은 일을 하고 있어요. 로컬이 잘 돌면 클라우드 쪽은 꺼 달라고 말해 주세요(중복 기록 방지).
