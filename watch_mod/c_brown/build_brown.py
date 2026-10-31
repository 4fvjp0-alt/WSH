"""3-page PDF for the 10 women's brown-leather combos (card layout shared with ../c110/build.py)."""
import json, html, re

src = open('../c110/build.py').read()
CSS = re.search(r"CSS = '''(.*?)'''", src, re.S).group(1)
D = json.load(open('combos.json'))
C, MOV, FX = D['combos'], D['movement'], D['usd_krw']


def won(usd):
    return f'{round(usd * FX, -3):,.0f}원'


def link(i):
    return f'https://www.aliexpress.us/item/{i}.html'


exec(src[src.index('def card(c):'):src.index('def page(')])  # defines card()


def page(title, body, n, total):
    return f'''<section class="page"><header><div class="k">NH35 WATCH MOD · 여성용 브라운 가죽 스트랩 추천 10종</div><div class="h">{title}</div></header>{body}
      <footer><span>가격: 2026-10-31 aliexpress.us 기준(1달러≈{FX:,}원) · 총액 = 부품 + 무브먼트(클론 ${MOV['clone']['price']:.0f} ~ 정품 ${MOV['genuine']['price']:.0f}) · 이미지는 사양 렌더링</span><span>{n} / {total}</span></footer></section>'''


cells = ''.join(f'''<div class="ov"><img src="render/{c['code']}.jpg"><div><b>{c['code']}</b> {html.escape(c['style_kor'])}<div class="sp2">{html.escape(c['spec'])}</div>
  <div class="why">💡 {html.escape(c['why'])}</div><div class="pr2">${c['total_clone']:.0f}~{c['total_genuine']:.0f} · {won(c['total_clone'])}~</div></div></div>''' for c in C)
strap = next(p for p in C[0]['parts'] if p['label'] == '스트랩')
intro = f'''<div class="intro">브라운 가죽은 <b>크림·샴페인·골드·자개·그린·아이스블루·파스텔</b> 다이얼과 특히 잘 어울려요. 케이스는 36~38mm로 골랐고, 스트랩은 모두
  평점 ★{strap['rating']} · {strap['sold_s']} 판매된 <a href="{link(strap['id'])}">빈티지 소가죽 스트랩 #{strap['id']}</a> (${strap['price']:.2f}, 18~22mm·여러 브라운 톤)으로 통일했어요.
  <b>탄(밝은 갈색)</b>은 밝은 다이얼, <b>초콜릿(진한 갈색)</b>은 금속·진한 다이얼과 매치했어요.</div><div class="ovg">{cells}</div>'''
pages = [('브라운 가죽에 어울리는 10가지 조합', intro), ('상세 ① B01~B06', f'<div class="grid">{"".join(card(c) for c in C[:6])}</div>'),
         ('상세 ② B07~B10', f'<div class="grid">{"".join(card(c) for c in C[6:])}</div>')]
CSS += '''.ovg{display:grid;grid-template-columns:repeat(2,1fr);gap:2.2mm;flex:1}
.ov{display:flex;gap:2.4mm;border:1px solid #f2d3c0;background:#fdf8f4;border-radius:2.4mm;padding:1.6mm;align-items:center}
.ov img{height:41mm;aspect-ratio:2/3;object-fit:cover;border-radius:1.6mm}.ov b{color:#7c3f1d}.ov{font-size:8.6pt}
.sp2{font-size:6.8pt;color:#6b7280;margin:.6mm 0}.why{font-size:7.2pt;color:#92400e;line-height:1.4}.pr2{font-size:9pt;font-weight:800;color:#7c3f1d;margin-top:1mm}
.intro a{color:#2563eb;text-decoration:none}.w{--c:#7c3f1d;--bg:#fdf8f4;--line:#f2d3c0}'''
doc = ''.join(page(t, b, n + 1, len(pages)) for n, (t, b) in enumerate(pages))
open('catalog.html', 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{doc}</body></html>')
