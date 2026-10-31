"""Build the 110-combo PDF pages, contact sheets and budget CSV from combos.json."""
import json, html, csv, statistics, os

D = json.load(open('combos.json'))
C, MOV, FX = D['combos'], D['movement'], D['usd_krw']
men, women = [c for c in C if not c['women']], [c for c in C if c['women']]
STY_ORDER = []
for c in men:
    if c['style_kor'] not in STY_ORDER:
        STY_ORDER.append(c['style_kor'])


def won(usd):
    return f'{round(usd * FX, -3):,.0f}원'


def link(i):
    return f'https://www.aliexpress.us/item/{i}.html'


# ---------------------------------------------------------------- CSV
with open('budget.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(['코드', '구분', '스타일', '사양', '케이스', '케이스$', '다이얼', '다이얼$', '핸즈', '핸즈$', '스트랩', '스트랩$',
                '부품합계$', '총액(클론NH35)$', '총액(정품NH35)$', '총액(클론)원', '총액(정품)원', '첫구매가 포함'])
    for c in C:
        by = {p['label']: p for p in c['parts']}
        row = [c['code'], '여성' if c['women'] else '남성', c['style_kor'], c['spec']]
        for lab in ['케이스', '다이얼', '핸즈', '스트랩']:
            p = by.get(lab)
            row += [link(p['id']) if p else ('다이얼 세트 포함' if lab == '핸즈' else '케이스 포함/불필요'), p['price'] if p else 0]
        row += [c['parts_total'], c['total_clone'], c['total_genuine'], round(c['total_clone'] * FX, -3), round(c['total_genuine'] * FX, -3),
                'Y' if any(p['bait'] for p in c['parts']) else '']
        w.writerow(row)

# ---------------------------------------------------------------- HTML pages
def card(c):
    rows = ''.join(f'''<tr><td class="l">{p['label']}</td><td><img src="img/{p['id']}.jpg"></td><td><a href="{link(p['id'])}">#{p['id'][-8:]}</a>{'<span class="b">첫구매가</span>' if p['bait'] else ''}{f'<div class="nt">{p["note"]}</div>' if p['note'] else ''}</td><td class="p">${p['price']:.2f}</td></tr>''' for p in c['parts'])
    if c.get('strap_included'):
        rows += f'<tr><td class="l">스트랩</td><td></td><td><span class="nt" style="font-size:6pt;color:#4b5563">{c["strap_kor"].split("(")[0]} · 케이스 구성품</span></td><td class="p">$0</td></tr>'
    return f'''<div class="card {'w' if c['women'] else 'm'}"><img class="r" src="render/{c['code']}.jpg">
      <div class="hd"><span class="cd">{c['code']}</span><b>{html.escape(c['name'])}</b></div><div class="sp">{html.escape(c['spec'])}</div>
      <table>{rows}</table>
      <div class="tot"><span>부품 ${c['parts_total']:.0f}</span><b>총 ${c['total_clone']:.0f}~{c['total_genuine']:.0f}</b><em>{won(c['total_clone'])}~{won(c['total_genuine'])}</em></div></div>'''


def page(title, body, n, total):
    return f'''<section class="page"><header><div class="k">NH35 WATCH MOD · 예상 조합 {len(men)}+{len(women)}종</div><div class="h">{title}</div></header>{body}
      <footer><span>가격: 2026-10-31 aliexpress.us 검색 기준(달러, 1달러≈{FX:,}원) · 총액 = 부품 + 무브먼트(클론 ${MOV['clone']['price']:.0f} ~ 정품 ${MOV['genuine']['price']:.0f}) · 이미지는 사양 렌더링</span><span>{n} / {total}</span></footer></section>'''


pages = []
# summary page
srows = ''
for s in STY_ORDER:
    cs = [c for c in men if c['style_kor'] == s]
    t = [c['total_clone'] for c in cs]
    srows += f'<tr><td><b>{s}</b></td><td>{cs[0]["code"]}~{cs[-1]["code"]}</td><td>{cs[0]["cfg"]["caseD"]}mm</td><td>${min(t):.0f}</td><td>${statistics.mean(t):.0f}</td><td>${max(t):.0f}</td><td>{won(statistics.mean(t))}</td><td><img src="render/{cs[0]["code"]}.jpg"><img src="render/{cs[1]["code"]}.jpg"><img src="render/{cs[2]["code"]}.jpg"></td></tr>'
tw = [c['total_clone'] for c in women]
srows += f'<tr class="wr"><td><b>여성용 10종</b></td><td>F01~F10</td><td>36~38mm</td><td>${min(tw):.0f}</td><td>${statistics.mean(tw):.0f}</td><td>${max(tw):.0f}</td><td>{won(statistics.mean(tw))}</td><td><img src="render/F01.jpg"><img src="render/F04.jpg"><img src="render/F06.jpg"></td></tr>'
allc = [c['total_clone'] for c in C]
summary = f'''<div class="intro">남성 10개 스타일 × 10가지 변형 = <b>100종</b>, 여성 <b>10종</b>. 모든 조합에 알리 실제 상품(케이스·다이얼·핸즈·스트랩)을 자동 매칭하고 예산을 계산했어요.
  케이스는 스타일별로 직접 확인한 상품으로 고정했고, 다이얼은 색상·스타일 키워드로 판매량·평점이 가장 좋은 상품을 골랐어요.</div>
  <div class="kpis"><div><span>조합 수</span><b>{len(C)}종</b></div><div><span>평균 총액(클론)</span><b>${statistics.mean(allc):.0f}</b><em>{won(statistics.mean(allc))}</em></div>
  <div><span>최저 ~ 최고(클론)</span><b>${min(allc):.0f} ~ ${max(allc):.0f}</b></div><div><span>정품 NH35로 바꾸면</span><b>+${MOV['genuine']['price'] - MOV['clone']['price']:.0f}</b></div></div>
  <table class="sum"><thead><tr><th>스타일</th><th>코드</th><th>크기</th><th>최저</th><th>평균</th><th>최고</th><th>평균(원)</th><th>미리보기</th></tr></thead><tbody>{srows}</tbody></table>
  <div class="mv">무브먼트: 클론 <a href="{link(MOV['clone']['id'])}">#{MOV['clone']['id']}</a> ${MOV['clone']['price']:.2f} (★{MOV['clone']['rating']}, {MOV['clone']['sold_s']} 판매) ·
  정품 <a href="{link(MOV['genuine']['id'])}">#{MOV['genuine']['id']}</a> ${MOV['genuine']['price']:.2f} (★{MOV['genuine']['rating']}, {MOV['genuine']['sold_s']} 판매)</div>
  <ul class="notes"><li><b>첫구매가</b>($1~2) 표시 부품은 첫 주문에만 그 가격이에요. 두 번째부터는 더 나올 수 있어요.</li>
  <li>여러 색을 한 상품에서 파는 경우가 많아요 → 주문할 때 <b>옵션에서 색·베젤·크라운 위치(3시/3.8시)</b>를 고르세요.</li>
  <li>미국 스토어 가격이라 한국 앱 가격·배송비와 다를 수 있어요. 목록통관 면세 한도($150)를 넘지 않게 나눠 주문하세요.</li></ul>'''
pages.append(('한눈에 보기 · 스타일별 예산', summary))
# budget table pages
def tbl(cs):
    r = ''.join(f'<tr><td>{c["code"]}</td><td>{html.escape(c["style_kor"])}</td><td>{html.escape(c["spec"])}</td><td>${c["parts_total"]:.0f}</td><td><b>${c["total_clone"]:.0f}</b></td><td>${c["total_genuine"]:.0f}</td><td>{won(c["total_clone"])}</td></tr>' for c in cs)
    return f'<table class="bt"><thead><tr><th>코드</th><th>스타일</th><th>사양</th><th>부품</th><th>총(클론)</th><th>총(정품)</th><th>원화(클론)</th></tr></thead><tbody>{r}</tbody></table>'
pages.append(('예산표 ① 남성 M001~M040', tbl(men[:40])))
pages.append(('예산표 ② 남성 M041~M080', tbl(men[40:80])))
pages.append(('예산표 ③ 남성 M081~M100 · 여성 F01~F10', tbl(men[80:] + women)))
# detail pages (6 per page)
for i in range(0, len(C), 6):
    grp = C[i:i + 6]
    title = ('남성 ' if not grp[0]['women'] else '여성 ') + f'{grp[0]["code"]} ~ {grp[-1]["code"]} · {grp[0]["style_kor"]}' + ('' if grp[-1]['style_kor'] == grp[0]['style_kor'] else f' / {grp[-1]["style_kor"]}')
    pages.append((title, f'<div class="grid">{"".join(card(c) for c in grp)}</div>'))

CSS = '''
@font-face{font-family:K;src:url("../fonts/NotoSansKR.ttf");font-weight:100 900}
@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{font-family:K,sans-serif;color:#1f2937;background:#e5e7eb}
.page{width:210mm;height:297mm;padding:7mm 8mm 6mm;background:#fff;margin:0 auto;display:flex;flex-direction:column;gap:2.4mm;page-break-after:always;overflow:hidden}
.page:last-child{page-break-after:auto}
header .k{font-size:7pt;color:#6b7280}header .h{font-size:14pt;font-weight:800;color:#111827}
.intro{font-size:8.6pt;color:#374151;background:#f9fafb;border-radius:2mm;padding:2.4mm 3mm;line-height:1.55}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:2mm}.kpis div{background:#eff6ff;border:1px solid #bfdbfe;border-radius:2mm;padding:2mm 3mm}
.kpis span{display:block;font-size:7pt;color:#6b7280}.kpis b{font-size:14pt;color:#1e3a8a}.kpis em{display:block;font-style:normal;font-size:7pt;color:#4b5563}
table.sum{width:100%;border-collapse:collapse;font-size:8pt}.sum th{background:#1e3a8a;color:#fff;padding:1.4mm}.sum td{border-bottom:1px solid #e5e7eb;padding:1mm 1.4mm;text-align:center}
.sum td:first-child{text-align:left}.sum img{height:12.5mm;margin:0 .4mm;border-radius:1mm}.sum tr.wr td{background:#fdf2f8}
.mv{font-size:7.6pt;color:#374151}.mv a,.card a{color:#2563eb;text-decoration:none}
.notes{padding:2mm 3mm 2mm 7mm;background:#fffbeb;border:1px dashed #fcd34d;border-radius:2mm;font-size:7.8pt;color:#92400e;line-height:1.6}
table.bt{width:100%;border-collapse:collapse;font-size:6.9pt}.bt th{background:#111827;color:#fff;padding:1mm}.bt td{border-bottom:1px solid #eef0f3;padding:.62mm 1.2mm;text-align:right;white-space:nowrap}
.bt td:nth-child(2),.bt td:nth-child(3),.bt td:first-child{text-align:left}.bt td:nth-child(3){white-space:normal}
.grid{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:2.4mm;flex:1;min-height:0}
.card{border:1px solid var(--line);background:var(--bg);border-radius:2.4mm;padding:1.8mm;display:flex;flex-direction:column;overflow:hidden}
.m{--c:#1e3a8a;--bg:#f7f9ff;--line:#c7d7fe}.w{--c:#9d174d;--bg:#fff7fb;--line:#fbcfe8}
.card img.r{width:100%;height:76mm;object-fit:cover;object-position:center 40%;border-radius:1.6mm}
.hd{font-size:8.2pt;margin-top:1.2mm;display:flex;gap:1.2mm;align-items:center;color:#111}.cd{background:var(--c);color:#fff;border-radius:1mm;padding:0 1.2mm;font-size:7.4pt;font-weight:800}
.sp{font-size:6.4pt;color:#6b7280;margin:.4mm 0 .8mm;line-height:1.35}
.card table{width:100%;border-collapse:collapse;font-size:6.4pt;background:#fff;border-radius:1.2mm}
.card td{padding:.5mm .8mm;border-top:1px solid #f1f5f9;vertical-align:middle}.card td img{width:6.5mm;height:6.5mm;object-fit:cover;border-radius:.8mm;display:block}
.card td.l{color:var(--c);font-weight:700;white-space:nowrap}.card td.p{text-align:right;font-weight:700;color:#dc2626;white-space:nowrap}
.b{background:#dc2626;color:#fff;border-radius:.8mm;padding:0 .8mm;margin-left:.8mm;font-size:5.4pt}.nt{font-size:5.4pt;color:#9ca3af}
.tot{margin-top:auto;display:flex;align-items:baseline;gap:1.4mm;padding-top:1mm;flex-wrap:wrap}.tot span{font-size:6.6pt;color:#6b7280}.tot b{font-size:10pt;color:var(--c)}.tot em{font-style:normal;font-size:6.4pt;color:#4b5563}
footer{margin-top:auto;font-size:6.2pt;color:#9ca3af;display:flex;justify-content:space-between;border-top:1px solid #e5e7eb;padding-top:1.2mm;gap:3mm}
'''
total = len(pages)
doc = ''.join(page(t, b, n + 1, total) for n, (t, b) in enumerate(pages))
open('catalog.html', 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>NH35 110종</title><style>{CSS}</style></head><body>{doc}</body></html>')

# contact sheets
def sheet(cs, cols, title, fn):
    cells = ''.join(f'<div class="c"><img src="render/{c["code"]}.jpg"><div><b>{c["code"]}</b> {html.escape(c["style_kor"])}<br>{html.escape(c["spec"].split(" · ")[1])} · <b>${c["total_clone"]:.0f}~{c["total_genuine"]:.0f}</b></div></div>' for c in cs)
    open(fn, 'w').write(f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>@font-face{{font-family:K;src:url("../fonts/NotoSansKR.ttf")}}
    body{{margin:0;padding:24px;font-family:K,sans-serif;background:#fff;width:{cols * 190 + 48}px}}h1{{margin:0 0 4px;font-size:30px}}p{{margin:0 0 16px;color:#6b7280}}
    .g{{display:grid;grid-template-columns:repeat({cols},180px);gap:10px}}.c img{{width:180px;height:230px;object-fit:cover;object-position:center 42%;border-radius:8px;display:block}}
    .c div{{font-size:11px;line-height:1.35;color:#374151;margin-top:3px}}</style></head><body><h1>{title}</h1><p>가격 = 부품+무브먼트(클론~정품), 2026-10-31 aliexpress.us 기준 · 사양 렌더링</p><div class="g">{cells}</div></body></html>''')

sheet(men, 10, 'NH35 남성 예상 조합 100종', 'sheet_men.html')
sheet(women, 5, 'NH35 여성 예상 조합 10종', 'sheet_women.html')
print('pages', total)
