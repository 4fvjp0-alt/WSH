# NH35A / NH38A 일본 정품 가격 추적기

- `node watch_mod/price_tracker/track.js` : AliExpress 한국(원화) 검색 → `history.json` 기록 → `chart.png`·`chart.html`·`latest.md` 갱신 → (설정 시) 텔레그램 전송
- 예약 작업이 4시간마다 새 세션에서 실행하고, 결과를 이 브랜치에 커밋·푸시해요.
- 텔레그램: 클라우드 환경 변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 설정 + 네트워크 허용 도메인 `api.telegram.org`
- "검증된 정품 최저가" = 제목에 정품/일본/TMI 표기, 중국산·대체품 제외, 평점 4.7 이상, 판매 100개 이상인 상품 중 최저가
