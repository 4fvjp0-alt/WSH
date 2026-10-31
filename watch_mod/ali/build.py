"""Build the AliExpress candidate catalog (HTML) from picks.json."""
import json, html, sys

picks = json.load(open(sys.argv[1]))
OUT = sys.argv[2]

SLOT = {
    'MOV': ('무브먼트 NH35', '정품·클론 모두 포함. 케이스 크라운 위치(3시/3.8시)에 맞는 옵션 선택'),
    'D1_case': ('케이스', 'SKX 스타일 41~42.5mm · 챕터링 · 사파이어 여부 옵션 확인'),
    'D1_dial': ('다이얼', '28.5mm 블랙 · C3 야광 · 3시 날짜창'),
    'D2_case': ('케이스', '40mm · 세라믹 베젤 · 브레이슬릿 포함 여부 확인'),
    'D2_dial': ('다이얼', '28.5mm 블랙 · 로고 없는 제품'),
    'D3_case': ('케이스', '62MAS 스타일 40mm · 돔형 사파이어'),
    'D3_dial': ('다이얼', '28.5mm · 62MAS/빈티지 스타일'),
    'W1_case': ('케이스', '36mm 플루티드 · 주빌리 · 36mm 옵션 선택'),
    'W1_dial': ('다이얼', '자개(MOP) · 로마숫자'),
    'W2_case': ('케이스', '36mm 스무스 베젤 · 브레이슬릿'),
    'W2_dial': ('다이얼', '티파니 블루·핑크 등 파스텔 · 날짜창 없는 옵션 가능'),
    'W3_case': ('케이스', '36~38mm 다이버 · 크라운 3.8시 케이스 주의'),
    'W3_dial': ('다이얼', '28.5mm 화이트'),
    'hands_diver': ('핸즈 — 다이버용', 'C3/BGW9 야광 · 서브·SKX 스타일'),
    'hands_dress': ('핸즈 — 드레스용', '로즈골드·실버 · 바톤/도핀'),
    'straps': ('스트랩', '20mm 러버(FKM)·트로픽·가죽 · 러그 폭 확인'),
}
COMBOS = [
    ('d', 'D1', 'SKX 스타일 가성비 다이버', ['D1_case', 'D1_dial'], '핸즈는 공통 쪽의 다이버용 핸즈에서 고르세요. 러버 스트랩은 케이스에 포함된 상품이 많아요.'),
    ('d', 'D2', '서브 스타일 정석 다이버', ['D2_case', 'D2_dial'], '케이스에 오이스터/주빌리 브레이슬릿이 포함된 상품을 고르면 스트랩이 따로 필요 없어요.'),
    ('d', 'D3', '빈티지 62MAS 스타일', ['D3_case', 'D3_dial'], '다이얼과 핸즈의 야광 색을 맞추세요. 일부 다이얼은 29mm라 케이스 다이얼 규격 확인 필요.'),
    ('w', 'W1', '플루티드 베젤 드레스', ['W1_case', 'W1_dial'], '36/39mm, 36/40mm를 같이 파는 케이스가 많아요 → 36mm 옵션 선택.'),
    ('w', 'W2', '파스텔 다이얼 데일리', ['W2_case', 'W2_dial'], '다이얼+핸즈 세트 상품이 많아요. 세트를 사면 핸즈를 따로 살 필요가 없어요.'),
    ('w', 'W3', '미니 다이버', ['W3_case', 'W3_dial'], '크라운 3.8시 케이스는 무브먼트도 3.8시 옵션으로 사야 해요.'),
]


LOGOCHK = {'3256810335640394', '3256811563984647', '3256812704905559'}


def card(it, star):
    if it is None:
        return ''
    img = f'img/{it["id"]}.jpg'
    has_img = bool(it.get('img'))
    price = f'${it["price"]:.2f}' if it.get('price') is not None else '-'
    orig = f'<s>${it["orig"]:.2f}</s>' if it.get('orig') else ''
    bait = it.get('price') is not None and it['price'] <= 1.5 and it.get('orig')
    rating = f'★{it["rating"]:.1f}' if it.get('rating') else '평점 없음'
    sold = f'{it["sold_s"]} 판매' if it.get('sold_s') and it['sold_s'] != '0' else '판매 적음'
    url = f'https://www.aliexpress.us/item/{it["id"]}.html'
    title = html.escape(it['title'])
    pic = f'<img src="{img}">' if has_img else '<div class="noimg">사진 없음</div>'
    return f'''<a class="card{' star' if star else ''}" href="{url}">
      <div class="pic">{pic}{'<span class="tag">⭐ 1차 추천</span>' if star else ''}{'<span class="tag2">첫구매가</span>' if bait else ''}{'<span class="tag3">⚠ 사진에 로고 보임</span>' if it['id'] in LOGOCHK else ''}</div>
      <div class="pr"><b>{price}</b> {orig}</div>
      <div class="meta">{rating} · {sold}</div>
      <div class="tt">{title}</div>
      <div class="id">#{it["id"]}</div></a>'''


def section(key):
    name, note = SLOT[key]
    v = picks[key]
    cards = card(v['prev'], True) + ''.join(card(x, False) for x in v['picks'])
    return f'<div class="sec"><div class="sh"><b>{name}</b><span>{note}</span></div><div class="grid">{cards}</div></div>'


pages = []
for i in range(0, 6, 2):
    body = ''
    for theme, code, name, keys, tip in COMBOS[i:i + 2]:
        body += f'''<div class="combo {theme}"><div class="ch"><span class="badge">{code}</span>{name}</div>
        {''.join(section(k) for k in keys)}<div class="tip">💡 {tip}</div></div>'''
    pages.append(body)
common = f'''<div class="combo c"><div class="ch"><span class="badge">공통</span>모든 조합에 쓰는 부품</div>
  {section('MOV')}{section('hands_diver')}{section('hands_dress')}{section('straps')}</div>'''
pages.append(common)

total = len(pages)
doc = ''.join(f'''<section class="page"><header><div class="k">NH35 WATCH MOD · ALIEXPRESS 상품 후보 카탈로그</div>
  <div class="h">조합별 실제 상품 (⭐1차 추천 + 추가 후보 5개)</div></header>{p}
  <footer><span>2026-10-31 aliexpress.us 검색 결과 기준(달러) · 한국 앱 가격·배송비와 다를 수 있어요 · 카드를 누르면 상품 페이지로 이동 · 로고 있는 다이얼은 No-logo 옵션 선택</span><span>{n + 1} / {total}</span></footer></section>'''
              for n, p in enumerate(pages))

CSS = '''
@font-face{font-family:K;src:url("../fonts/NotoSansKR.ttf");font-weight:100 900}
@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{font-family:K,sans-serif;color:#1f2937;background:#e5e7eb}
.page{width:210mm;height:297mm;padding:7.5mm 9mm 6.5mm;background:#fff;margin:0 auto;display:flex;flex-direction:column;gap:2mm;page-break-after:always;overflow:hidden}
.page:last-child{page-break-after:auto}
header .k{font-size:7pt;color:#6b7280;letter-spacing:.4px}header .h{font-size:13pt;font-weight:800;color:#111827}
.combo{border-radius:3mm;padding:2.4mm 2.6mm;border:1.2px solid var(--line);background:var(--bg)}
.d{--c:#1e3a8a;--bg:#f5f8ff;--line:#bfdbfe}.w{--c:#9d174d;--bg:#fff6fa;--line:#fbcfe8}.c{--c:#065f46;--bg:#f3fcf8;--line:#a7f3d0}
.ch{font-size:11pt;font-weight:800;color:var(--c);display:flex;align-items:center;gap:2mm;margin-bottom:1.4mm}
.badge{background:var(--c);color:#fff;border-radius:1.6mm;padding:.3mm 2mm;font-size:9.5pt}
.sec{margin-top:1.2mm}.sh{display:flex;gap:2mm;align-items:baseline;margin-bottom:1mm}
.sh b{font-size:9pt;color:var(--c)}.sh span{font-size:7pt;color:#6b7280}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:1.6mm}
.card{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid #e5e7eb;border-radius:2mm;overflow:hidden}
.card.star{border:1.6px solid #f59e0b}
.pic{position:relative;aspect-ratio:1/1;background:#f3f4f6}.pic img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{display:flex;align-items:center;justify-content:center;height:100%;font-size:7pt;color:#9ca3af}
.tag{position:absolute;left:1mm;top:1mm;background:#f59e0b;color:#fff;font-size:5.8pt;font-weight:800;border-radius:1mm;padding:.2mm 1mm}
.tag2{position:absolute;right:1mm;bottom:1mm;background:#dc2626;color:#fff;font-size:5.4pt;font-weight:700;border-radius:1mm;padding:.2mm 1mm}
.tag3{position:absolute;left:1mm;bottom:1mm;background:#7c2d12;color:#fff;font-size:5.2pt;font-weight:700;border-radius:1mm;padding:.2mm 1mm}
.pr{font-size:8pt;padding:.8mm 1.2mm 0;color:#111}.pr b{color:#dc2626}.pr s{color:#9ca3af;font-size:6.4pt}
.meta{font-size:6.2pt;color:#6b7280;padding:0 1.2mm}
.tt{font-size:5.8pt;line-height:1.3;color:#374151;padding:.4mm 1.2mm 0;height:7.6mm;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.id{font-size:5.2pt;color:#9ca3af;padding:.2mm 1.2mm .8mm}
.tip{font-size:7.4pt;color:#92400e;background:#fffbeb;border:1px dashed #fcd34d;border-radius:1.6mm;padding:1mm 2mm;margin-top:1.6mm}
footer{margin-top:auto;font-size:6.4pt;color:#9ca3af;display:flex;justify-content:space-between;border-top:1px solid #e5e7eb;padding-top:1.4mm}
'''
open(OUT, 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>NH35 알리 상품 후보</title><style>{CSS}</style></head><body>{doc}</body></html>')
print('pages', total)
