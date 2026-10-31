"""Build the 'expected finished watch' pages (HTML) for the guide PDF."""
import json, re, sys

picks = json.load(open(sys.argv[1]))
OUT = sys.argv[2]

# id -> (price, orig) from catalog data
P = {}
for v in picks.values():
    for it in ([v['prev']] if v['prev'] else []) + v['picks']:
        P[it['id']] = (it.get('price'), it.get('orig'))
P.setdefault('3256807258106958', (1.09, 12.01))
P.setdefault('3256802603676272', (5.80, 17.74))

MOV = ('무브먼트', '3256807809241435', 'NH35 정품 · 크라운 위치를 케이스에 맞춰 옵션 선택')
COMBOS = [
    ('d', 'D1', 'SKX 스타일 가성비 다이버', '42.5mm · 펩시 베젤 · 블랙 선레이 · 블루 러버', [
        ('케이스', '3256811669139812', '42.5mm 실버 SKX · 챕터링 · 러버 밴드 포함 (펩시 옵션)'),
        ('다이얼', '3256810471915379', '28.5mm 로고 없는 선레이 · C3 (블랙 옵션)'),
        ('핸즈', '3256811819451028', 'SKX 스타일 C3 핸즈'), MOV]),
    ('d', 'D2', '서브 스타일 정석 다이버', '40mm · 블랙 세라믹 베젤 · 유광 블랙 · 오이스터', [
        ('케이스', '3256806812392828', '40mm 904L · 세라믹 베젤 · 오이스터 브레이슬릿 옵션'),
        ('다이얼', '3256808193361956', '28.5mm 서브 에나멜 블랙 · BGW9'),
        ('핸즈', '3256808930278423', '서브 핸즈 · BGW9/C3 · 실버'), MOV]),
    ('d', 'D3', '빈티지 62MAS 스타일', '40mm · 돔형 사파이어 · 빈티지 야광 · 트로픽', [
        ('케이스', '3256807653520012', '62MAS 모드 · 아치형 사파이어 · 30BAR'),
        ('다이얼', '3256812494032196', '28.5mm 선레이 · 로고 없음 (빈티지 야광은 카탈로그 후보 참고)'),
        ('핸즈', '3256807258106958', '62MAS 바톤 스타일 · C3'),
        ('스트랩', '3256809573948916', 'FKM 트로픽 러버 20mm'), MOV]),
    ('w', 'W1', '플루티드 베젤 드레스', '36mm 로즈골드 · 자개 다이얼 · 로마숫자 · 주빌리', [
        ('케이스', '3256808915969609', '36/39mm 플루티드 · 주빌리 · 로즈골드 · 36mm 옵션'),
        ('다이얼', '3256809172126598', '자개(MOP) · 로고 없음 — 로마숫자는 #3256806557587601'),
        ('핸즈', '3256812914536821', '로즈골드 핸즈'), MOV]),
    ('w', 'W2', '파스텔 다이얼 데일리', '36mm · 스무스 베젤 · 민트 블루 · 오이스터', [
        ('케이스', '3256807066497943', '36/40mm · 오이스터 브레이슬릿 · 36mm 옵션'),
        ('다이얼+핸즈', '3256812055028462', '티파니 블루 다이얼+핸즈 세트 · 날짜창 없는 옵션 가능'), MOV]),
    ('w', 'W3', '미니 다이버', '38mm · 그린 세라믹 베젤 · 화이트 다이얼 · 그린 러버', [
        ('케이스', '3256809249370712', 'SKX013 38mm · 세라믹 베젤 · 크라운 3.8시'),
        ('다이얼', '3256806044780595', '28.5mm 심플 화이트 (1차 추천은 사진에 로고가 보여 교체)'),
        ('핸즈', '3256807169125651', 'C3/BGW9 폴리시드 핸즈'),
        ('스트랩', '3256809573948916', 'FKM 러버 20mm · 그린 색상 선택'),
        ('무브먼트', '3256807809066984', 'NH35 정품 · 크라운 3.8시 (케이스와 맞춤)')]),
]


def price(i):
    p, o = P.get(i, (None, None))
    if p is None:
        return '-'
    return f'${p:.2f}' + (f' <s>${o:.2f}</s>' if o else '')


def block(theme, code, name, spec, parts):
    rows = ''.join(f'''<tr><td class="k">{k}</td><td><a href="https://www.aliexpress.us/item/{i}.html">#{i}</a><div class="n">{n}</div></td><td class="p">{price(i)}</td></tr>'''
                   for k, i, n in parts)
    return f'''<div class="row {theme}"><img src="{code}.png"><div class="info">
      <div class="t"><span class="b">{code}</span>{name}</div><div class="s">{spec}</div>
      <table>{rows}</table></div></div>'''


def page(title, items, n):
    return f'''<section class="page"><header><div class="k">NH35 WATCH MOD · 완성 예상 이미지</div><div class="h">{title}</div></header>
    {''.join(block(*c) for c in items)}
    <footer><span>1차 추천 부품 기준 사양 렌더링(실제 사진 아님) · 가격은 2026-10-31 aliexpress.us 기준 · 상품 번호를 누르면 상품 페이지로 이동</span><span>{n}</span></footer></section>'''


CSS = '''
@font-face{font-family:K;src:url("../fonts/NotoSansKR.ttf");font-weight:100 900}
@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{font-family:K,sans-serif;color:#1f2937;background:#e5e7eb}
.page{width:210mm;height:297mm;padding:8mm 10mm 7mm;background:#fff;margin:0 auto;display:flex;flex-direction:column;gap:3mm;page-break-after:always;overflow:hidden}
.page:last-child{page-break-after:auto}
header .k{font-size:7.5pt;color:#6b7280}header .h{font-size:15pt;font-weight:800;color:#111827}
.row{display:flex;gap:5mm;align-items:center;border:1.2px solid var(--line);border-radius:3.5mm;background:var(--bg);padding:2.5mm;height:82mm}
.d{--c:#1e3a8a;--bg:#f5f8ff;--line:#bfdbfe}.w{--c:#9d174d;--bg:#fff6fa;--line:#fbcfe8}
.row img{height:100%;aspect-ratio:2/3;border-radius:2.5mm;box-shadow:0 1mm 3mm rgba(0,0,0,.12)}
.info{flex:1;min-width:0}
.t{font-size:13pt;font-weight:800;color:var(--c);display:flex;align-items:center;gap:2mm}
.b{background:var(--c);color:#fff;border-radius:1.6mm;padding:.2mm 2mm;font-size:10.5pt}
.s{font-size:8.6pt;color:#4b5563;margin:1mm 0 2.4mm}
table{width:100%;border-collapse:collapse;font-size:7.8pt;background:#fff;border-radius:2mm;overflow:hidden}
td{padding:1.4mm 2mm;border-top:1px solid #f1f5f9;vertical-align:top}
td.k{font-weight:700;color:var(--c);width:18%;white-space:nowrap}
td a{color:#2563eb;text-decoration:none;font-size:7.2pt}.n{color:#374151;margin-top:.3mm}
td.p{text-align:right;white-space:nowrap;font-weight:700;color:#dc2626;width:22%}td.p s{color:#9ca3af;font-weight:400;font-size:6.6pt}
footer{margin-top:auto;font-size:6.6pt;color:#9ca3af;display:flex;justify-content:space-between;border-top:1px solid #e5e7eb;padding-top:1.4mm}
'''
html = page('🌊 다이버 3종', COMBOS[:3], 'A') + page('🌸 여성용 3종', COMBOS[3:], 'B')
open(OUT, 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>완성 예상</title><style>{CSS}</style></head><body>{html}</body></html>')
