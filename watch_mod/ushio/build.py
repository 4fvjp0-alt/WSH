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
open('ushio.html', 'w').write(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{doc}</body></html>')
