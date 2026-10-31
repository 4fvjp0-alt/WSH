"""Catalog for the 2nd set of combos (men's divers M1-M3, women's F1-F3)."""
import json, html, os, sys

picks = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
HERE = os.path.dirname(os.path.abspath(OUT))

COMBOS = [
    ('m', 'M1', '터틀 스타일 쿠션 다이버', '44~45mm 쿠션 케이스 · 블랙/블루 다이얼 · 22mm 러버',
     '두툼한 쿠션 케이스라 손목 위 존재감이 커요. 손목 둘레 17cm 이상 추천.',
     ['터틀 케이스는 크라운 3.8시가 많아요 → 무브먼트도 3.8시 옵션', '러그 폭 22mm', 'SKX/터틀 겸용 다이얼(28.5mm)이 그대로 맞아요']),
    ('m', 'M2', 'BB58 스타일 빈티지 다이버', '39mm · 돔형 사파이어 · 골드 디테일 다이얼 · 스노우플레이크 핸즈',
     '39mm라 손목이 얇은 분도 편한 빈티지 다이버. 브레이슬릿·가죽·나토 모두 잘 어울려요.',
     ['일부 다이얼은 29mm → 케이스 다이얼 규격 확인', '러그 폭 20mm', '다이얼에 브랜드 로고 없는지 확인']),
    ('m', 'M3', '브론즈(청동) 다이버', '39~40mm CuSn8 브론즈 · 그린/브라운 다이얼 · 골드 핸즈',
     '쓸수록 색이 변하는(파티나) 청동 케이스. 세상에 하나뿐인 색으로 변해 가요.',
     ['파티나(녹색·갈색 변색)는 정상이에요. 원하면 광택제로 되돌릴 수 있어요', '케이스백이 스틸인지 확인 (피부 변색 방지)', '그린·브라운 다이얼과 골드 핸즈가 잘 어울려요']),
    ('f', 'F1', '칵테일 다이얼 드레스', '36~38mm 돔형 사파이어 · 텍스처 다이얼 · 도핀 핸즈 · 가죽',
     '빛에 따라 다이얼 무늬가 반짝이는 우아한 드레스 워치.',
     ['칵테일 다이얼 상품 수가 적어요 → 마음에 들면 빨리 구매', '로고 없는 옵션 확인', '얇은 가죽 스트랩(18~20mm)과 잘 어울려요']),
    ('f', 'F2', '일체형 브레이슬릿 스포츠', '37~41mm 팔각·일체형 브레이슬릿 · 블루/그레이 다이얼',
     '케이스와 브레이슬릿이 이어진 듯한 세련된 스포츠 워치.',
     ['대부분 40~41mm라 여성용엔 커요 → 37mm 옵션(⭐) 추천', '일체형이라 스트랩 교체가 어려워요', '다이얼 지름(28.5mm/31.8mm) 확인']),
    ('f', 'F3', '골드 PVD 그린 다이얼', '36mm 골드 PVD · 그린 선레이 다이얼 · 골드 핸즈 · 브레이슬릿',
     '골드와 그린의 클래식 조합. 포인트 주얼리처럼 차기 좋아요.',
     ['PVD 코팅은 긁히면 벗겨질 수 있어요', '36/39mm 겸용 상품 → 36mm 옵션 선택', '다이얼+핸즈 세트를 사면 색 맞추기 쉬워요']),
]
ROWS = [('case', '케이스'), ('dial', '다이얼'), ('hands', '핸즈')]


def card(it, star):
    imgf = os.path.join(HERE, 'img', f'{it["id"]}.jpg')
    pic = f'<img src="img/{it["id"]}.jpg">' if os.path.exists(imgf) else '<div class="noimg">사진 없음</div>'
    price = f'${it["price"]:.2f}' if it.get('price') is not None else '-'
    orig = f'<s>${it["orig"]:.2f}</s>' if it.get('orig') else ''
    bait = it.get('price') is not None and it['price'] <= 1.5 and it.get('orig')
    rating = f'★{it["rating"]:.1f}' if it.get('rating') else '평점 없음'
    sold = f'{it["sold_s"]} 판매' if it.get('sold_s') and it['sold_s'] != '0' else '판매 적음'
    return f'''<a class="card{' star' if star else ''}" href="https://www.aliexpress.us/item/{it["id"]}.html">
      <div class="pic">{pic}{'<span class="tag">⭐ 추천</span>' if star else ''}{'<span class="tag2">첫구매가</span>' if bait else ''}</div>
      <div class="pr"><b>{price}</b> {orig}</div><div class="meta">{rating} · {sold}</div>
      <div class="tt">{html.escape(it["title"])}</div><div class="id">#{it["id"]}</div></a>'''


def best(key):
    p = picks[key]['picks']
    return p[0] if p else None


def budget(code):
    s = sum((best(f'{code}_{r}') or {}).get('price') or 0 for r, _ in ROWS)
    return s


pages = []
# overview page
rows = ''
for theme, code, name, spec, desc, notes in COMBOS:
    b = budget(code)
    thumbs = ''.join(f'<img src="img/{best(code + "_" + r)["id"]}.jpg">' for r, _ in ROWS if best(code + '_' + r) and os.path.exists(os.path.join(HERE, 'img', best(code + '_' + r)['id'] + '.jpg')))
    rows += f'''<div class="ov {theme}"><div class="ovl"><div class="t"><span class="badge">{code}</span>{name}</div>
      <div class="s">{spec}</div><div class="d">{desc}</div></div><div class="th">{thumbs}</div>
      <div class="bud"><div class="k">⭐추천 부품 합계</div><div class="v">${b:.0f}</div><div class="k2">+ 무브먼트 $23~95</div></div></div>'''
pages.append(f'<div class="intro">남성 다이버 3종 · 여성용 3종 — 이전 조합과 겹치지 않는 새 스타일이에요. 각 조합은 다음 쪽에서 케이스·다이얼·핸즈 후보를 사진과 함께 보여 줘요.<br><b>합계는 ⭐추천 케이스+다이얼+핸즈 가격이에요.</b> 첫구매가($1~2)가 섞여 있어서 두 번째 주문부터는 더 비싸질 수 있어요. 무브먼트는 클론 $23~정품 $95.</div>{rows}')
for theme, code, name, spec, desc, notes in COMBOS:
    secs = ''
    for r, label in ROWS:
        items = picks[f'{code}_{r}']['picks']
        secs += f'<div class="sec"><div class="sh"><b>{label}</b><span>{len(items)}개 후보 · ⭐ = 판매량·평점 기준 1순위</span></div><div class="grid">{"".join(card(x, i == 0) for i, x in enumerate(items))}</div></div>'
    note = ''.join(f'<li>{n}</li>' for n in notes)
    pages.append(f'''<div class="combo {theme}"><div class="ch"><span class="badge">{code}</span>{name}<span class="bd">⭐추천 합계 약 ${budget(code):.0f} + 무브먼트</span></div>
      <div class="cs">{spec}</div><div class="cd">{desc}</div>{secs}<ul class="notes">{note}</ul></div>''')

total = len(pages)
doc = ''.join(f'''<section class="page"><header><div class="k">NH35 WATCH MOD · 새 조합 6종 (알리 실제 상품)</div>
  <div class="h">{'새 조합 한눈에 보기' if n == 0 else ('남성 다이버' if n <= 3 else '여성용')}</div></header>{p}
  <footer><span>2026-10-31 aliexpress.us 검색 기준(달러) · 한국 앱 가격·배송비와 다를 수 있어요 · 카드를 누르면 상품 페이지로 이동</span><span>{n + 1} / {total}</span></footer></section>'''
              for n, p in enumerate(pages))

CSS = '''
@font-face{font-family:K;src:url("../fonts/NotoSansKR.ttf");font-weight:100 900}
@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{font-family:K,sans-serif;color:#1f2937;background:#e5e7eb}
.page{width:210mm;height:297mm;padding:8mm 9mm 7mm;background:#fff;margin:0 auto;display:flex;flex-direction:column;gap:2.6mm;page-break-after:always;overflow:hidden}
.page:last-child{page-break-after:auto}
header .k{font-size:7pt;color:#6b7280}header .h{font-size:15pt;font-weight:800;color:#111827}
.m{--c:#0f4c5c;--bg:#f2f8f9;--line:#b6dbe2}.f{--c:#8a2b62;--bg:#fdf5fa;--line:#f2c6df}
.intro{font-size:9pt;color:#4b5563;background:#f9fafb;border-radius:2mm;padding:2.4mm 3mm}
.ov{display:flex;gap:3mm;align-items:center;border:1.2px solid var(--line);background:var(--bg);border-radius:3mm;padding:2.4mm 3mm}
.ovl{flex:1;min-width:0}.ov .t{font-size:11.5pt;font-weight:800;color:var(--c);display:flex;gap:2mm;align-items:center}
.ov .s{font-size:7.8pt;color:#374151;margin-top:.6mm}.ov .d{font-size:7.4pt;color:#6b7280;margin-top:.6mm}
.th{display:flex;gap:1.2mm}.th img{width:19mm;height:19mm;object-fit:cover;border-radius:1.6mm;border:1px solid #e5e7eb}
.bud{width:27mm;text-align:right}.bud .k{font-size:6.6pt;color:#6b7280}.bud .v{font-size:15pt;font-weight:800;color:var(--c)}.bud .k2{font-size:6.4pt;color:#9ca3af}
.badge{background:var(--c);color:#fff;border-radius:1.6mm;padding:.2mm 2mm;font-size:10pt}
.combo{border-radius:3mm;padding:3mm;border:1.2px solid var(--line);background:var(--bg);flex:1;display:flex;flex-direction:column}
.ch{font-size:14pt;font-weight:800;color:var(--c);display:flex;align-items:center;gap:2mm}
.bd{margin-left:auto;font-size:9pt;background:#fff;border:1px solid var(--line);border-radius:2mm;padding:.6mm 2.4mm}
.cs{font-size:9pt;color:#374151;margin-top:1mm}.cd{font-size:8pt;color:#6b7280;margin-top:.4mm}
.sec{margin-top:2.6mm}.sh{display:flex;gap:2mm;align-items:baseline;margin-bottom:1.2mm}.sh b{font-size:10.5pt;color:var(--c)}.sh span{font-size:7pt;color:#6b7280}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:1.8mm}
.card{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid #e5e7eb;border-radius:2mm;overflow:hidden}
.card.star{border:1.6px solid #f59e0b}
.pic{position:relative;aspect-ratio:1/1;background:#f3f4f6}.pic img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{display:flex;align-items:center;justify-content:center;height:100%;font-size:7pt;color:#9ca3af}
.tag{position:absolute;left:1mm;top:1mm;background:#f59e0b;color:#fff;font-size:6pt;font-weight:800;border-radius:1mm;padding:.2mm 1mm}
.tag2{position:absolute;right:1mm;bottom:1mm;background:#dc2626;color:#fff;font-size:5.6pt;font-weight:700;border-radius:1mm;padding:.2mm 1mm}
.pr{font-size:8.4pt;padding:.8mm 1.3mm 0}.pr b{color:#dc2626}.pr s{color:#9ca3af;font-size:6.6pt}
.meta{font-size:6.4pt;color:#6b7280;padding:0 1.3mm}
.tt{font-size:6pt;line-height:1.3;color:#374151;padding:.4mm 1.3mm 0;height:11.8mm;overflow:hidden;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical}
.id{font-size:5.4pt;color:#9ca3af;padding:.3mm 1.3mm .9mm}
.notes{margin-top:auto;padding:2mm 3mm 2mm 7mm;background:#fffbeb;border:1px dashed #fcd34d;border-radius:2mm;font-size:8.2pt;color:#92400e;line-height:1.6}
footer{margin-top:auto;font-size:6.4pt;color:#9ca3af;display:flex;justify-content:space-between;border-top:1px solid #e5e7eb;padding-top:1.4mm}
'''
open(OUT, 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>NH35 새 조합</title><style>{CSS}</style></head><body>{doc}</body></html>')
print('pages', total)
