"""10 women's combos that pair with a brown leather strap (reuses ../c110/gen.py matching)."""
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
    ('FLUTE36', 'mop', None, dict(metal='rose', handMetal='rose', markMetal='rose', dialFinish='mop', marks=dict(style='roman'), date=False, chapterColor='#efe8df', hands=dict(secColor='#b9805f', edge='rgba(80,40,20,.45)'), **CHOC),
     '로즈골드 + 자개 + 초콜릿 브라운 — 가장 우아한 조합'),
    ('GOLD36', 'green', None, dict(**CHOC), '골드와 그린은 브라운 가죽과 클래식하게 어울려요'),
    ('GOLD36', 'champagne', None, dict(dialColor='#e3cf98', print='#3a2f14', **TAN), '샴페인 다이얼 + 탄 브라운 — 따뜻한 톤 통일'),
    ('EXP36', 'cream', None, dict(**TAN), '크림 다이얼은 브라운 가죽과 가장 무난한 짝'),
    ('EXP36', 'iceblue', None, dict(**CHOC), '아이스블루 + 진한 브라운 — 색 대비로 산뜻하게'),
    ('DRESS36', 'pink', None, dict(caseD=36, l2l=43, bezel=dict(outer=17.6, inner=16.2), **TAN), '파스텔 핑크 + 탄 가죽 — 부드러운 데일리 드레스'),
    ('COCKTAIL', 'iceblue', None, dict(caseD=38, l2l=45, dialFinish='cocktail', bezel=dict(outer=18.6, inner=17.0), dialColor='#86b3d6', print='#ffffff', **CHOC), '칵테일 무늬 다이얼 + 브라운 — 빛 받으면 반짝여요'),
    ('FIELD36', 'cream', None, dict(**TAN), '크림 필드워치 + 탄 가죽 — 빈티지 캐주얼'),
    ('MINI', 'white', 'brown', dict(**CHOC), '화이트 다이얼 + 브라운 베젤 + 가죽 — 스포티하지만 부드럽게'),
    ('BRONZE36', 'green', 'green', dict(caseD=36, l2l=43, bezel=dict(outer=17.0, inner=13.8), **TAN), '청동 케이스는 쓸수록 갈색빛이 돌아 가죽과 함께 멋스러워져요'),
]
out = []
for i, (style, col, bez, ov, why) in enumerate(LIST, 1):
    c = build(f'B{i:02d}', style, col, bez, 'brown', ov, women=True)
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
