"""Preview pages for the 2nd combo set (M1-M3, F1-F3) + Murph white-dial build."""
import json, sys
picks = json.load(open(sys.argv[1])); murph = json.load(open(sys.argv[2])); OUT = sys.argv[3]
P = {}
for v in picks.values():
    for it in v['picks']: P[it['id']] = it
for v in murph.values():
    for it in v: P[it['id']] = it
def top(k): return picks[k]['picks'][0]
def row(label, it, note=''):
    pr = f'${it["price"]:.2f}' if it.get('price') is not None else '-'
    o = f' <s>${it["orig"]:.2f}</s>' if it.get('orig') else ''
    t = it['title'][:70] + ('…' if len(it['title']) > 70 else '')
    return f'<tr><td class="k">{label}</td><td><a href="https://www.aliexpress.us/item/{it["id"]}.html">#{it["id"]}</a><div class="n">{note or t}</div></td><td class="p">{pr}{o}</td></tr>'
INFO = {
 'M1': ('m', '터틀 스타일 쿠션 다이버', '44mm 쿠션 케이스 · 블랙 베젤·다이얼 · 오렌지 초침 · 22mm 러버', '케이스 크라운이 3.8시면 무브먼트도 3.8시 옵션'),
 'M2': ('m', 'BB58 스타일 빈티지 다이버', '39mm · 돔형 사파이어 · 골드 프린트 블랙 다이얼 · 골드 스노우플레이크 핸즈', '⭐케이스는 브론즈 버전 — 스틸을 원하면 카탈로그 2~5순위'),
 'M3': ('m', '브론즈(청동) 다이버', '39mm CuSn8 · 그린 선레이 다이얼 · 골드 핸즈 · 브라운 가죽', '청동은 쓰면서 색이 변해요(파티나)'),
 'F1': ('f', '칵테일 다이얼 드레스', '38mm · 얇은 폴리시드 베젤 · 아이스블루 칵테일 다이얼 · 도핀 핸즈 · 브라운 가죽', '칵테일 다이얼은 상품 수가 적어요'),
 'F2': ('f', '일체형 브레이슬릿 스포츠', '37mm · 팔각 베젤 · 블루 태피스트리 다이얼 · 일체형 브레이슬릿', '여성용은 37mm 옵션 추천'),
 'F3': ('f', '골드 PVD 그린 다이얼', '36mm 골드 · 플루티드 베젤 · 그린 선레이 · 골드 브레이슬릿', 'PVD는 긁히면 벗겨질 수 있어요'),
}
def block(code):
    th, name, spec, tip = INFO[code]
    rows = row('케이스', top(code + '_case')) + row('다이얼', top(code + '_dial')) + row('핸즈', top(code + '_hands'))
    return f'<div class="row {th}"><img src="{code}.png"><div class="info"><div class="t"><span class="b">{code}</span>{name}</div><div class="s">{spec}</div><table>{rows}</table><div class="tip">💡 {tip}</div></div></div>'
def page(title, codes, n):
    return f'<section class="page"><header><div class="k">NH35 WATCH MOD · 새 조합 완성 예상 이미지</div><div class="h">{title}</div></header>{"".join(block(c) for c in codes)}<footer><span>⭐추천 부품 기준 사양 렌더링(실제 사진 아님) · 가격 2026-10-31 aliexpress.us 기준 · 상품 번호를 누르면 이동</span><span>{n}</span></footer></section>'
m = murph
mrows = (row('케이스 ⭐', m['case'][2], '38mm 빈티지 필드 케이스 · 사파이어 · 가죽 밴드 포함') + row('케이스 대안', m['case'][0], 'RICHUS 38mm · 브레이슬릿 포함 · 260개 판매')
 + row('다이얼 ⭐', m['dial'][0], 'RICHUS 흰 파일럿 다이얼 · 24H 아라비아 숫자 · 야광 · 로고 없음') + row('다이얼 대안', m['dial'][1], '크림 화이트 24H 아라비아 숫자 다이얼')
 + row('핸즈 ⭐', m['hands'][0], '블랙 3핸즈 · 그린 야광') + row('스트랩 ⭐', m['strap'][0], '빈티지 브라운 소가죽 20mm · 1,000+개 판매')
 + row('스트랩 대안', m['strap'][1], '퀵릴리즈 가죽 · 브라운 여러 톤'))
tot = sum(x['price'] for x in [m['case'][2], m['dial'][0], m['hands'][0], m['strap'][0]])
thumbs = ''.join(f'<img src="../murph/img/{x["id"]}.jpg">' for x in [m['case'][2], m['dial'][0], m['dial'][1], m['hands'][0], m['strap'][0]])
murph_page = f'''<section class="page"><header><div class="k">NH35 WATCH MOD · 특별 조합</div><div class="h">머프(Murph) 스타일 흰판 + 브라운 가죽</div></header>
<div class="mu"><img class="big" src="MURPH.png"><div class="info"><div class="t"><span class="b">MURPH</span>흰판 필드워치</div>
<div class="s">38mm 폴리시드 케이스 · 흰 다이얼(큰 아라비아 숫자 + 안쪽 24시간 눈금) · 블랙 야광 핸즈 · 브라운 가죽 20mm</div>
<div class="sum">⭐부품 합계 약 <b>${tot:.0f}</b> + 무브먼트(NH35 $23~95)</div><div class="thumbs">{thumbs}</div></div></div>
<table class="mt">{mrows}</table>
<ul class="notes"><li>영화 인터스텔라의 해밀턴 머프를 닮은 스타일이에요. <b>로고 없는 다이얼</b>만 골랐어요 (해밀턴 로고 다이얼은 위조품이라 제외).</li>
<li>다이얼에 날짜창이 없어요 → NH35를 쓰면 크라운 2단(날짜 조정 위치)이 헛돌아요. 신경 쓰이면 날짜 없는 NH38 무브먼트도 고려.</li>
<li>케이스 러그 폭을 확인하고(보통 20mm) 같은 폭 스트랩을 사세요. 다이얼은 RICHUS 제품이라 대안 케이스(RICHUS 38mm)와 맞추면 호환 걱정이 가장 적어요.</li></ul>
<footer><span>사양 렌더링(실제 사진 아님) · 가격 2026-10-31 aliexpress.us 기준</span><span>MURPH</span></footer></section>'''
CSS = open('/home/user/WSH/watch_mod/preview/pages.html').read().split('<style>')[1].split('</style>')[0]
CSS += '''.m{--c:#0f4c5c;--bg:#f2f8f9;--line:#b6dbe2}.f{--c:#8a2b62;--bg:#fdf5fa;--line:#f2c6df}
.tip{font-size:7.6pt;color:#92400e;margin-top:1.6mm}
.mu{display:flex;gap:6mm;align-items:center;--c:#5b3a1e;--bg:#faf6f0;--line:#e6d5bf;border:1.2px solid var(--line);background:var(--bg);border-radius:3.5mm;padding:3mm}
.mu .big{height:118mm;aspect-ratio:2/3;border-radius:3mm;box-shadow:0 1mm 3mm rgba(0,0,0,.15)}
.sum{font-size:10pt;margin:2mm 0;color:#374151}.sum b{color:#dc2626;font-size:14pt}
.thumbs{display:grid;grid-template-columns:repeat(3,1fr);gap:1.6mm;margin-top:2mm}.thumbs img{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:1.6mm;border:1px solid #e5e7eb}
.mt{--c:#5b3a1e}.notes{padding:2.4mm 3mm 2.4mm 7mm;background:#fffbeb;border:1px dashed #fcd34d;border-radius:2mm;font-size:8.2pt;color:#92400e;line-height:1.6}'''
html = page('🌊 남성 다이버 3종', ['M1', 'M2', 'M3'], 'A') + page('🌸 여성용 3종', ['F1', 'F2', 'F3'], 'B') + murph_page
open(OUT, 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{html}</body></html>')
