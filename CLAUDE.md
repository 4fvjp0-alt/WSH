# 수업 필기 정리 규칙 (notes/)

이 저장소의 `notes/` 폴더는 사용자의 열전달 등 수업 필기를 정리한 PDF를 보관한다.
사용자가 필기 스캔 PDF를 올리면 아래 방식으로 정리한다.

## 스타일
- `notes/_template/note_template.html`의 디자인을 그대로 따른다:
  A4 모눈 노트 배경, 손글씨 폰트(본문 Gaegu, 메모 Nanum Pen Script), 남색 본문,
  색깔 손글씨 해설·포스트잇, 형광펜, 손그림 SVG 그래프.
- 필기 내용을 순서대로 깔끔하게 옮기고, 중간중간 이해를 돕는 해설을 자세히 단다
  (왜 그런지, 숫자의 출처, 직관적 비유, 예시 계산).
- 필기의 오류는 고쳐 쓰고 주황 점선 "⚠ 필기 수정" 박스로 표시한다.
  판독이 불확실한 부분은 "확인 필요"로 표시한다.
- 마지막 쪽에 한 장 요약 + 자주 하는 실수 + 문제 풀이 순서를 넣는다.

## 폰트 / 렌더링
- 폰트는 github.com/google/fonts 의 ofl/gaegu, ofl/nanumpenscript TTF를 내려받아
  HTML과 같은 폴더의 `fonts/`에 둔다 (저장소에는 커밋하지 않음).
- `node notes/_template/render.js <html이 있는 폴더>` 로 PDF와 페이지 스크린샷을 만들고,
  출력되는 페이지별 남은 여백(px)이 30 이상인지 확인한다(음수면 넘침).

## 파일명
- `YYMMDD_주제_정리노트.pdf` — 날짜가 맨 앞 (원본 스캔 파일명의 날짜 사용, 예: 261007).
- `notes/` 폴더에 저장하고 커밋·푸시한다.

## 제출물 표지 (notes/_cover/)
- `cover_designs.html` 한 페이지 = 표지 디자인 1종 (A4). 과목명·이름·학번·날짜 칸은 빈칸으로 둔다.
- 폰트 목록은 HTML 맨 위 주석 참고 (같은 폴더 `fonts/`, 커밋하지 않음).
- `node notes/_cover/render_cover.js notes/_cover` → `표지_디자인모음.pdf`, `표지_N_이름.pdf`, `표지_미리보기.png`.
