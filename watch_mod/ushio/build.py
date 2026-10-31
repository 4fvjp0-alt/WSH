"""One-page PDF: Grand Seiko Ushio 300-style NH35 builds (sterile)."""
import json, html
C = json.load(open('combos.json'))
def link(i): return f'https://www.aliexpress.us/item/{i}.html'
def card(c):
    rows = ''.join(f'''<tr><td class="l">{p['label']}</td><td><img src="img/{p['id']}.jpg"></td><td><a href="{link(p['id'])}">#{p['id']}</a><div class="nt">{html.escape(p['note'])}</div></td>
      <td class="p">${p['price']:.2f}<div class="nt">{('★'+str(p['rating'])) if p['rating'] else ''} {p['sold_s']}판매</div></td></tr>''' for p in c['parts'])
    return f'''<div class="card"><img class="r" src="{c['code']}.png"><div class="info"><div class="hd"><span class="cd">{c['code']}</span>{c['name']}</div>
      <div class="why">{c['why']}</div><table>{rows}</table>
      <div class="tot">부품 ${c['parts_total']:.0f} · <b>총 ${c['total_clone']:.0f}~{c['total_genuine']:.0f}</b> <em>{round(c['total_clone']*1400,-3):,.0f}~{round(c['total_genuine']*1400,-3):,.0f}원</em></div></div></div>'''
CSS = '''@font-face{font-family:K;src:url("../fonts/NotoSansKR.ttf");font-weight:100 900}@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{font-family:K,sans-serif;color:#1f2937}.page{width:210mm;height:297mm;padding:8mm 9mm 6mm;display:flex;flex-direction:column;gap:2.4mm}
.k{font-size:7pt;color:#6b7280}.h{font-size:15pt;font-weight:800;color:#0f2a5c}
.intro{font-size:7.8pt;color:#374151;background:#f1f5fb;border-radius:2mm;padding:2.2mm 3mm;line-height:1.55}
.card{display:flex;gap:3mm;border:1px solid #c7d7fe;background:#f7f9ff;border-radius:2.4mm;padding:1.8mm;flex:1;min-height:0;overflow:hidden}
.card img.r{height:100%;aspect-ratio:2/3;object-fit:cover;border-radius:1.6mm}.info{flex:1;display:flex;flex-direction:column;min-width:0}
.hd{font-size:11pt;font-weight:800;color:#0f2a5c;display:flex;gap:1.6mm;align-items:center}.cd{background:#0f2a5c;color:#fff;border-radius:1mm;padding:0 1.6mm;font-size:9pt}
.why{font-size:7.4pt;color:#92400e;margin:.4mm 0 .8mm}table{width:100%;border-collapse:collapse;font-size:7.2pt;background:#fff;border-radius:1.4mm}
td{padding:.45mm 1mm;border-top:1px solid #eef1f5;vertical-align:middle}td img{width:7.2mm;height:7.2mm;object-fit:cover;border-radius:1mm;display:block}
td.l{font-weight:700;color:#0f2a5c;white-space:nowrap}td a{color:#2563eb;text-decoration:none;font-size:6.6pt}.nt{font-size:6.2pt;color:#6b7280}
td.p{text-align:right;font-weight:700;color:#dc2626;white-space:nowrap}.tot{margin-top:auto;font-size:8pt;color:#374151}.tot b{font-size:11pt;color:#0f2a5c}.tot em{font-style:normal;font-size:7pt;color:#6b7280}
.notes{font-size:7.2pt;color:#92400e;background:#fffbeb;border:1px dashed #fcd34d;border-radius:2mm;padding:1.6mm 3mm 1.6mm 6mm;line-height:1.5}
footer{font-size:6.2pt;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:1mm}'''
body = ''.join(card(c) for c in C)
doc = f'''<section class="page"><div class="k">NH35 WATCH MOD · 레퍼런스: 그랜드세이코 Spring Drive U.F.A. 우시오 300 다이버 (SLGB023 블루 / SLGB025 그린, 2026)</div>
<div class="h">우시오 다이버 스타일 NH35 조합 4종 (로고 없음)</div>
<div class="intro">원본 특징: 40.8mm 티타늄 · 다이얼과 같은 색 세라믹 베젤 · <b>수면 같은 물결(우시오) 그라데이션 다이얼</b> · 다면 커팅 사각 인덱스(12시 2줄) · 화살 시침+칼 분침 · 4시 크라운 · 3열 티타늄 브레이슬릿.
알리 부품으로 <b>모양과 색감</b>을 최대한 맞췄어요. 원본의 스프링드라이브 무브먼트·파워리저브 표시(7시)는 NH35로 재현할 수 없어요.</div>
{body}
<ul class="notes"><li>로고 없는 부품만 골랐어요. 그랜드세이코 로고가 인쇄된 다이얼은 위조품이라 제외 — 원하면 <b>본인 이니셜 커스텀 로고</b> 다이얼로 대체 가능.</li>
<li>4시 크라운 느낌을 원하면 크라운 3.8시 티타늄 케이스(#3256807365144809, $35.70)+ NH35 <b>3.8시 무브먼트</b> 조합도 가능해요(브레이슬릿 별도).</li>
<li>티타늄 케이스 옵션에 블루 베젤이 있으면 U1은 인서트 추가 구매가 필요 없어요. 다이얼 색은 옵션 사진으로 진하기를 확인하세요.</li></ul>
<footer>가격: 2026-10-31 aliexpress.us 기준(1달러≈1,400원) · 총액 = 부품 + 무브먼트(클론 $27 ~ 정품 $89) · 이미지는 사양 렌더링(실제 사진 아님)</footer></section>'''
M = json.load(open('movements.json'))
u3 = next(c for c in C if c['code'] == 'U3')
def prow(p, label=None):
    return f'''<tr><td class="l">{label or p['label']}</td><td><img src="img/{p['id']}.jpg"></td><td><a href="{link(p['id'])}">{link(p['id'])}</a><div class="nt">{html.escape(p['note'])}</div></td>
      <td class="p">${p['price']:.2f}<div class="nt">{('★'+str(p['rating'])) if p['rating'] else '평점 없음'} · {p['sold_s']}판매</div></td></tr>'''
parts_rows = ''.join(prow(p) for p in u3['parts']) + ''.join(prow(p, f'무브먼트 {i+1}') for i, p in enumerate(M['yn55']))
pt = u3['parts_total']
mrow = lambda name, price, total, pro, con, cls='': f'<tr class="{cls}"><td><b>{name}</b></td><td>{price}</td><td><b>{total}</b></td><td>{pro}</td><td>{con}</td></tr>'
mt = (mrow('YN55 (Epson)', '영상 $26 / 미국스토어 $43~76', f'${pt+26.29:.0f} ~ ${pt+76.49:.0f}', 'NH35 케이스·다이얼(무날짜)·핸즈 호환 확인 · 정품급 품질', '크라운 날짜단계 헛돎 · 초침 호환 100% 아님', 'hl')
      + mrow('NH38 정품', f'${M["nh38"]["price"]:.0f}', f'${pt+M["nh38"]["price"]:.0f}', '날짜 없음 → 크라운 깔끔', '비쌈')
      + mrow('NH35 정품', '$89', f'${pt+89.38:.0f}', '표준', '날짜단계 헛돎 · 비쌈')
      + mrow('NH35 클론', '$27', f'${pt+26.84:.0f}', '최저가', '품질 복불복 (영상에서도 고장으로 실패)'))
page2 = f'''<section class="page"><div class="k">NH35 WATCH MOD · 우시오 스타일 추가 조합</div>
<div class="h">U3 + YN55 — 블루 · 스틸 가성비, Epson YN55 무브먼트</div>
<div class="p2"><img class="big" src="U3.png"><div class="i2">
<div class="intro"><b>왜 U3에 YN55?</b> U3 다이얼(RICHUS 3D 물결)은 <b>날짜창이 없어서</b> YN55의 유일한 큰 문제(NH35 날짜창 다이얼과 날짜 위치 어긋남)가 생기지 않아요.
YN55는 세이코 그룹(Epson) 정품 무브먼트로 NH35 케이스·다이얼·핸즈와 호환되는 것이 확인됐어요.</div>
<div class="sum2">부품 합계 <b>${pt:.0f}</b> + YN55 → <b>총 약 ${pt+26.29:.0f}~{pt+76.49:.0f}</b><br><span>영상 구매가($26) 기준 약 {round((pt+26.29)*1400,-3):,.0f}원 · 한국 앱 가격 확인 필수</span></div>
<table class="cmp"><tr><th>YN55 vs NH35 (영상 실측)</th><th>결과</th></tr>
<tr><td>NH35 케이스</td><td>✅ 깊이·스템 높이 딱 맞음</td></tr><tr><td>NH35 다이얼 (날짜 없음)</td><td>✅ 다이얼 발 구멍 여러 개라 그대로 장착</td></tr>
<tr><td>NH35 다이얼 (날짜 있음)</td><td>⚠️ 날짜가 왼쪽으로 어긋남 → Miyota 8215 다이얼 필요</td></tr><tr><td>NH35 핸즈</td><td>✅ 2세트 모두 장착, 몇 주 착용 문제없음 (보장은 아님)</td></tr>
<tr><td>스템 분리</td><td>스템 옆 작은 구멍 속 버튼 (NH35는 레버)</td></tr><tr><td>소음</td><td>로터 소리가 NH35보다 약간 큼</td></tr></table>
</div></div>
<div class="st">부품 링크 (U3 + YN55)</div><table class="pl">{parts_rows}</table>
<div class="st">U3 무브먼트별 총액 비교</div>
<table class="mt"><tr><th>무브먼트</th><th>가격</th><th>U3 총액</th><th>장점</th><th>단점</th></tr>{mt}</table>
<ul class="notes"><li>RICHUS 다이얼은 NH35·Miyota 겸용 → <b>NH35 옵션</b> 선택 (YN55는 둘 다 장착 가능). 판매자에게 <b>날짜창 없음</b> 재확인.</li>
<li><b>초침 여분</b>을 하나 같이 사 두세요 · 스템은 동봉된 여분으로 조금씩 잘라 맞추기(영상은 약 5.1mm).</li>
<li>케이스의 '블루' 옵션은 GMT(24시간) 베젤이라 <b>블루 다이버 인서트(Miuksi)로 교체</b>해야 우시오 느낌이 나요.</li>
<li>참고 영상: AJMWatches 「Build your own YN55 Custom Watch | The Best Budget NH35 Alternative?」(2026-09)</li></ul>
<footer>가격: 2026-10-31 aliexpress.us 기준(1달러≈1,400원) · YN55 미국 스토어 가격은 부풀려져 있어 한국 앱에서 재확인 · 이미지는 사양 렌더링</footer></section>'''
CSS2 = '''.page{page-break-after:always}.page:last-child{page-break-after:auto}
.p2{display:flex;gap:4mm;align-items:stretch}.p2 .big{width:58mm;aspect-ratio:2/3;object-fit:cover;border-radius:2mm}.i2{flex:1;display:flex;flex-direction:column;gap:2mm}
.sum2{font-size:9pt;color:#374151;background:#eef6ff;border-radius:2mm;padding:2mm 3mm}.sum2 b{color:#0f2a5c;font-size:12pt}.sum2 span{font-size:7pt;color:#6b7280}
table.cmp th,table.mt th{background:#0f2a5c;color:#fff;font-size:7.4pt;padding:1mm;text-align:left}table.cmp td{font-size:7.2pt}
.st{font-size:10pt;font-weight:800;color:#0f2a5c;margin-top:1mm}table.pl td a{font-size:6.2pt;word-break:break-all}
table.mt td{font-size:7.2pt}table.mt tr.hl td{background:#fff7d6}'''
open('ushio.html', 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}{CSS2}</style></head><body>{doc}{page2}</body></html>')
