"""10 women's DARK-dial combos on a brown leather strap (reuses ../c110/gen.py matching)."""
import sys, json, copy
sys.argv = ['gen.py', '/tmp/rs/_tmp_combos.json']
exec(open('../c110/gen.py').read())

STYLES['BRONZE36'] = copy.deepcopy(STYLES['BRONZE']); STYLES['BRONZE36']['kor'] = '브론즈 36mm'
PREF['BRONZE36'] = '3256808054148935'
STYLES['DRESS36'] = copy.deepcopy(STYLES['DRESS']); PREF_HANDS['DRESS36'] = PREF_HANDS['DRESS']; STYLES['DRESS36']['kor'] = '드레스 36mm'
PREF['DRESS36'] = '3256802494646018'
STYLES['COCKTAIL'] = copy.deepcopy(STYLES['DRESS']); PREF_HANDS['COCKTAIL'] = PREF_HANDS['DRESS']; STYLES['COCKTAIL']['kor'] = '칵테일 드레스 38mm'
PREF['COCKTAIL'] = '3256811532259524'
STYLES['FIELD36'] = copy.deepcopy(STYLES['FIELD']); STYLES['FIELD36']['kor'] = '필드워치 38mm'
PREF['FIELD36'] = '3256811690556918'

TAN, CHOC = dict(strapColor='#9a6a3f', stitch='#efe0c8'), dict(strapColor='#5a3720', stitch='#d9c3a0')
LIST = [
    ('FLUTE36', 'black', None, dict(metal='rose', handMetal='rose', markMetal='rose', markEdge='#e3b49a', print='#f3d9c9', chapterColor='#2a2224', hands=dict(secColor='#e3b49a', edge='rgba(80,40,20,.45)'), **CHOC),
     '로즈골드 + 블랙 다이얼 — 가장 고급스럽고 차분한 조합'),
    ('GOLD36', 'black', None, dict(chapterColor='#1c1c1c', **CHOC), '골드 + 블랙은 실패 없는 클래식, 진한 브라운과 무게감 통일'),
    ('GOLD36', 'burgundy', None, dict(chapterColor='#3a141a', **TAN), '버건디 + 골드 + 탄 가죽 — 와인빛 가을 무드'),
    ('GOLD36', 'blue', None, dict(chapterColor='#1a2a4f', **CHOC), '네이비 선레이 + 골드 — 빛에 따라 푸른빛이 살아나요'),
    ('EXP36', 'blue', None, dict(chapterColor='#c9ced3', **TAN), '네이비 + 스틸 + 탄 가죽 — 데일리로 가장 무난한 어두운 조합'),
    ('EXP36', 'green', None, dict(**TAN), '포레스트 그린 + 탄 가죽 — 자연스러운 어스톤'),
    ('DRESS36', 'burgundy', None, dict(caseD=36, l2l=43, bezel=dict(outer=17.6, inner=16.2), **CHOC), '버건디 선레이 + 도핀 핸즈 — 우아한 드레스 워치'),
    ('COCKTAIL', 'purple', None, dict(caseD=38, l2l=45, dialFinish='cocktail', bezel=dict(outer=18.6, inner=17.0), dialColor='#3e2a63', print='#ffffff', **CHOC), '딥 퍼플 칵테일 다이얼 — 빛 받으면 보랏빛 무늬가 반짝여요'),
    ('MINI', 'black', 'black', dict(chapterColor='#18191c', chapterTicks='#e6e6e6', markEdge='#c8ccd1', bezel=dict(ceramic=True), **TAN), '올블랙 미니 다이버 + 탄 가죽 — 시크하지만 가죽으로 부드럽게'),
    ('BRONZE36', 'brown', 'brown', dict(caseD=36, l2l=43, bezel=dict(outer=17.0, inner=13.8), **TAN), '초콜릿 다이얼 + 청동 + 탄 — 브라운 톤온톤'),
]
out = []
for i, (style, col, bez, ov, why) in enumerate(LIST, 1):
    c = build(f'K{i:02d}', style, col, bez, 'brown', ov, women=True)
    c['why'] = why
    # same well-rated genuine-leather strap for all (avoids the $1.09 first-order listing)
    sp = POOL['3256809850940819']
    c['parts'] = [p for p in c['parts'] if p['label'] != '스트랩'] + [part(sp, '스트랩', '브라운 계열 색상 선택 · 러그 폭(18/20mm) 확인')]
    t = sum(p['price'] for p in c['parts'])
    c.update(parts_total=round(t, 2), total_clone=round(t + MOVEMENT['clone']['price'], 2), total_genuine=round(t + MOVEMENT['genuine']['price'], 2), strap_included=False)
    out.append(c)
json.dump(dict(movement=MOVEMENT, usd_krw=USD_KRW, combos=out), open('combos.json', 'w'), ensure_ascii=False, indent=1)
for c in out:
    print(c['code'], c['style_kor'], c['spec'], c['parts_total'], [(p['label'], p['id'][-6:], p['price']) for p in c['parts']])
