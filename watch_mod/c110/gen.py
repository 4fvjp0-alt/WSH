"""Generate 100 men's + 10 women's NH35 mod combos, each matched to real AliExpress parts.

Inputs : scraped search results (/tmp/rs/ali_full*.json) -> pool of listings
Output : combos.json (renderer config + matched parts + budget per combo)
"""
import json, re, glob, copy, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'combos.json'
USD_KRW = 1400

# ------------------------------------------------------------------ listing pool
def parse(t):
    t2 = re.sub(r'\d+\s*×\s*\$[\d,.]+', '', t)
    t2 = re.sub(r'save \$[\d,.]+', '', t2)
    t2 = re.sub(r'- \$[\d,.]+', '', t2)
    am = [float(x.replace(',', '')) for x in re.findall(r'\$([\d,]+\.?\d*)', t2)]
    price = am[0] if am else None
    orig = next((a for a in am[1:4] if price and a > price * 1.05), None)
    ms = re.search(r'([\d,.]+K?\+?)\s+sold', t2)
    s = ms.group(1) if ms else '0'
    n = s.replace(',', '').replace('+', '')
    sold = int(float(n[:-1]) * 1000) if n.endswith('K') else int(float(n or 0))
    mr = re.search(r'sold\s+(\d\.\d|\d)\s+\$', t2) or re.search(r'-\d+%\s+(\d\.\d|\d)\s+[\d,.]+K?\+?\s+sold', t2)
    rating = float(mr.group(1)) if mr else None
    title = re.split(r'\s\$|\s[\d,.]+K?\+?\s+sold', t)[0]
    return dict(price=price, orig=orig, rating=rating, sold=sold, sold_s=s, title=re.sub(r'\s*·\s*', ' ', title))

POOL, BYQ = {}, {}
for fn in sorted(glob.glob('/tmp/rs/ali_full*.json')):
    for q, items in json.load(open(fn)).items():
        BYQ.setdefault(q, [])
        for it in items:
            if not it.get('img') or '/kf/' not in it['img']:
                continue
            p = parse(it['t'])
            if p['price'] is None:
                continue
            p.update(id=it['id'], img=it['img'])
            POOL.setdefault(it['id'], p)
            if it['id'] not in [x['id'] for x in BYQ[q]]:
                BYQ[q].append(POOL[it['id']])

LOGO = re.compile(r'S[ -]?logo|S dial|PADI|Rolex|Omega|Tudor|Sea[- ]?Dweller|Grenade|\bGS\b|Grand Seiko|Hamilton|Longines|Cartier|Patek|Audemars|Panerai|IWC|Breitling', re.I)
WEAK = re.compile(r'Prospex|Presage|Seiko logo|Custom Logo|Khaki', re.I)
NOLOGO = re.compile(r'no[ -]?logo|sterile', re.I)


def score(p):
    s = p['sold'] * (p['rating'] or 4.5)
    if p['rating'] is not None and p['rating'] < 4.3:
        s *= 0.2
    if p['price'] <= 1.2 and p.get('orig'):      # first-shopper bait price
        s *= 0.35
    return s + 1


def candidates(queries, inc=None, exc=None, logo=False, kind=None):
    seen, out = set(), []
    qs = queries if isinstance(queries, list) else [queries]
    for q in qs:
        for p in BYQ.get(q, []):
            if p['id'] in seen:
                continue
            t = p['title']
            if inc and not re.search(inc, t, re.I):
                continue
            if exc and re.search(exc, t, re.I):
                continue
            if logo and (LOGO.search(t) or (WEAK.search(t) and not NOLOGO.search(t))):
                continue
            if kind == 'dial' and re.search(r'\bcase\b', t, re.I) and not re.search(r'dial', t.split('case')[0], re.I):
                continue
            seen.add(p['id'])
            out.append(p)
    return sorted(out, key=score, reverse=True)


ALLDIAL_Q = [q for q in BYQ if re.search(r'dial', q, re.I)]
COLOR_RE = {
    'black': r'black', 'blue': r'(?<!ice )(?<!sky )(?<!light )blue|navy', 'green': r'green|olive', 'white': r'white',
    'grey': r'gr[ae]y|slate', 'orange': r'orange', 'red': r'\bred\b', 'yellow': r'yellow', 'brown': r'brown|chocolate|coffee',
    'cream': r'cream|beige|ivory|vintage', 'silver': r'silver', 'salmon': r'salmon|copper', 'purple': r'purple|lavender|violet',
    'pink': r'pink|sakura', 'iceblue': r'ice blue|sky blue|light blue|tiffany|mint|turquoise', 'champagne': r'champagne|gold',
    'burgundy': r'burgundy|wine|bordeaux|red', 'mop': r'MOP|pearl|shell',
}
STYLE_DIAL = {
    'diver': r'lum|lume|C3|BGW9|div|sub|skx|turtle',
    'field': r'arabic|pilot|field|military|numeral|24h',
    'dress': r'sunburst|sunray|dress|no lum|texture|stripe|baton|roman',
    'explorer': r'explorer|369|3\s?6\s?9|arabic',
    'any': None,
}


def pick_dial(color, style):
    pools = [
        candidates(ALLDIAL_Q, inc=COLOR_RE[color], logo=True, kind='dial'),
    ]
    sty = STYLE_DIAL[style]
    both = [p for p in pools[0] if not sty or re.search(sty, p['title'], re.I)]
    if both:
        return both[0], True
    if pools[0]:
        return pools[0][0], False
    any_ = candidates(ALLDIAL_Q, inc=sty, logo=True, kind='dial')
    return (any_[0] if any_ else None), False


# --------------------------------------------------------------- styles (men)
E = 'rgba(0,0,0,.35)'
STYLES = {
    'SKX': dict(kor='SKX 스타일 다이버', case=(['SKX007 case sapphire NH35', 'SKX case 42mm chapter ring NH35', '42mm diver case NH35 ceramic bezel'], r'SKX|42', r'44mm|45mm|square|octag|assembled'),
                hands=(['skx hands NH35', 'NH35 hands C3 luminous'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='diver',
                cfg=dict(caseD=42, lug=22, l2l=46.5, metal='steel', crown=[3.2, 6.2], crownGuard=True,
                         bezel=dict(type='diver', outer=20.0, inner=15.4, color='#151619', ink='#f2f2f2'), chapterW=1.6, chapterColor='#1a1b1e', chapterTicks='#e8e8e8',
                         dialFinish='sunburst', lume='#eef3dc', markEdge='#c8ccd1', marks=dict(twelve='tri', quarter='bar', other='dot'), markSize=1.3, markInset=2.7, date=True,
                         hands=dict(hour='sword', hl=.60, hw=2.5, minute='sword', ml=.92, mw=1.9, sec='lolli', secColor='#d8dce0', edge=E), text='AUTOMATIC', text2='200m')),
    'SUB': dict(kor='서브 스타일 다이버', case=(['40mm ceramic bezel sapphire case NH35 bracelet', 'sub case 40mm NH35 oyster bracelet', '41mm sub case NH35 sapphire'], r'40|41', r'GMT|rose|gold|insert(?!.*case)'),
                hands=(['mercedes hands NH35', 'NH35 sub hands'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='diver',
                cfg=dict(caseD=40, lug=20, l2l=47.5, metal='steel', crown=[3.4, 6.4], crownGuard=True,
                         bezel=dict(type='diver', outer=19.0, inner=15.3, color='#0c0d0f', ink='#e8e8e8', ceramic=True), chapterW=0.9, chapterColor='#1b1c1f',
                         dialFinish='gloss', minuteTrack=True, lume='#f0f4e4', markEdge='#e9ecef', marks=dict(twelve='tri', quarter='bar', other='dot'), markSize=1.25, markInset=3.1, date=True,
                         hands=dict(hour='merc', hl=.56, hw=2.3, minute='pencil', ml=.93, mw=1.7, sec='lolli', secColor='#e3e6e9', edge=E), text='AUTOMATIC', text2='300m')),
    'MAS': dict(kor='62MAS 빈티지 다이버', case=(['62MAS case NH35 sapphire'], r'62\s?MAS|domed', r'insert|dial'),
                hands=(['NH35 hands silver baton', 'NH35 hands gold vintage lume', 'baton hands NH35'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='diver',
                cfg=dict(caseD=40, lug=20, l2l=47, metal='steel', crown=[3.6, 6.8], domed=True,
                         bezel=dict(type='diver', outer=19.1, inner=15.5, color='#1b1c1e', ink='#e9dcc0', allMinutes=True, numSize=2.5), chapterW=1.2, chapterColor='#2a2b2d', chapterTicks='#e2d3b2',
                         dialFinish='matte', lume='#e6cb93', markEdge='#c9cdd2', vign=.35, marks=dict(twelve='rect2', quarter='rect', other='rect'), markSize=1.1, markInset=3.0, date=True, dateBg='#efe5cc',
                         hands=dict(hour='arrow', hl=.60, hw=2.7, minute='lumebaton', ml=.92, mw=1.6, sec='plain', secColor='#d0d4d8', edge=E), text='AUTOMATIC', text2='DIVER 150m')),
    'BB': dict(kor='BB58 스타일 다이버', case=(['BB58 case NH35 39mm', '39mm diver case NH35 gilt bezel'], r'39|BB58|58', r'insert only|Upgraded|San Martin'),
               hands=(['snowflake hands NH35'], r'hand|pointer|needle', r'dial'), dialstyle='diver',
               cfg=dict(caseD=39, lug=20, l2l=47.5, metal='steel', crown=[3.6, 7.0], domed=True,
                        bezel=dict(type='diver', outer=18.6, inner=15.0, color='#121316', ink='#d9b46a', numSize=2.5), chapterW=0.9, chapterColor='#17181b',
                        dialFinish='gloss', minuteTrack=True, lume='#efe3c4', markEdge='#d4af63', markMetal='gold', marks=dict(twelve='tri', quarter='bar', other='dot'), markSize=1.2, markInset=3.0, date=False,
                        handMetal='gold', hands=dict(hour='snowflake', hl=.58, hw=2.6, minute='pencil', ml=.93, mw=1.6, sec='lolli', secColor='#d4af63', edge='rgba(90,60,10,.6)'), text='AUTOMATIC', text2='200m')),
    'TURTLE': dict(kor='터틀 쿠션 다이버', case=(['turtle case NH35 sapphire', 'SRP777 turtle watch case NH35'], r'turtle|SRP|cushion|44|45', r'insert only|dial'),
                   hands=(['turtle hands NH35', 'skx hands NH35'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='diver',
                   cfg=dict(caseD=44, shape='cushion', lug=22, l2l=47, metal='steel', crown=[3.4, 6.6],
                            bezel=dict(type='diver', outer=19.6, inner=15.2, color='#141518', ink='#f0f0f0'), chapterW=1.5, chapterColor='#18191c', chapterTicks='#e6e6e6',
                            dialFinish='sunburst', lume='#eef3dc', markEdge='#c8ccd1', marks=dict(twelve='tri', quarter='bar', other='dot'), markSize=1.3, markInset=2.8, date=True,
                            hands=dict(hour='arrow', hl=.60, hw=2.8, minute='sword', ml=.92, mw=1.9, sec='lolli', secColor='#e8742c', edge=E), text='AUTOMATIC', text2="DIVER'S 200m")),
    'BRONZE': dict(kor='브론즈 다이버', case=(['bronze watch case NH35', 'CuSn8 bronze case NH35 diver'], r'bronze|CuSn', r'insert only|dial|pilot'),
                   hands=(['NH35 hands gold vintage lume', 'gold hands NH35'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='diver',
                   cfg=dict(caseD=39, lug=20, l2l=47, metal='bronze', crown=[3.6, 6.8], domed=True,
                            bezel=dict(type='diver', outer=18.6, inner=15.0, color='#2a3324', ink='#d9b07a', numSize=2.5), chapterW=1.0, chapterColor='#28301f',
                            dialFinish='sunburst', minuteTrack=True, lume='#e6cb93', markEdge='#c99a5e', markMetal='gold', vign=.4, marks=dict(twelve='rect2', quarter='rect', other='rect'), markSize=1.1, markInset=3.0, date=True, dateBg='#efe5cc',
                            handMetal='gold', hands=dict(hour='lumebaton', hl=.58, hw=1.9, minute='lumebaton', ml=.92, mw=1.5, sec='plain', secColor='#c99a5e', edge='rgba(90,60,10,.6)'), text='AUTOMATIC', text2='BRONZE 200m')),
    'FIELD': dict(kor='필드워치', case=(['field watch case 38mm NH35 sapphire', 'Murph case NH35 38mm', 'field watch case 40mm NH35'], r'38|40|field|vintage', r'diver|diving|200M|santos|square|bronze|ceramic|insert|PVD'),
                  hands=(['NH35 hands field watch black', 'sword hands NH35'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='field',
                  cfg=dict(caseD=38, lug=20, l2l=46, metal='steel', crown=[3.4, 6.2],
                           bezel=dict(type='smooth', outer=18.6, inner=16.6), chapterW=0.6, chapterColor='#e2e2de',
                           dialFinish='matte', minuteTrack=True, inner24=True, lume='#e7ecd8', markEdge='#1c1c1e', vign=.12, marks=dict(style='arabic'), date=False,
                           handMetal='black', hands=dict(hour='sword', hl=.58, hw=2.4, minute='sword', ml=.93, mw=1.8, sec='plain', secColor='#1c1c1e', edge='rgba(0,0,0,.6)'))),
    'PILOT': dict(kor='파일럿 워치', case=(['pilot watch case NH35 40mm sapphire', 'pilot case 42mm NH35'], r'pilot|40|42|43', r'GMT|bronze|PVD Gold'),
                  hands=(['pilot hands NH35', 'sword hands NH35'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='field',
                  cfg=dict(caseD=42, lug=22, l2l=50, metal='steel', crown=[4.6, 7.6],
                           bezel=dict(type='smooth', outer=20.5, inner=19.0), chapterW=0.6, chapterColor='#1c1d20',
                           dialFinish='matte', minuteTrack=True, lume='#f0f2e6', markEdge='#e8e8e8', vign=.25, marks=dict(style='arabic'), date=False,
                           hands=dict(hour='sword', hl=.58, hw=2.6, minute='sword', ml=.94, mw=2.0, sec='plain', secColor='#eceff1', edge=E))),
    'DRESS': dict(kor='드레스 워치', case=(['dress watch case 40mm NH35 sapphire', '38mm dress watch case NH35 sapphire'], r'38|39|40|dress', r'diver|diving|200M|GMT|santos|square|ceramic|insert|chapter'),
                  hands=(['NH35 dauphine hands', 'baton hands NH35'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='dress',
                  cfg=dict(caseD=40, lug=20, l2l=47, metal='steel', crown=[3.0, 5.6], domed=True,
                           bezel=dict(type='smooth', outer=19.6, inner=18.0), chapterW=0.8, chapterColor='#d8dde2',
                           dialFinish='sunburst', minuteTrack=True, lume='#fff', markEdge='#fff', vign=.2, marks=dict(twelve='baton2', quarter='baton', other='baton'), markSize=1.2, markInset=2.8, date=False,
                           hands=dict(hour='dauphine', hl=.58, hw=1.9, minute='dauphine', ml=.92, mw=1.5, lume=False, sec='plain', secColor='#eef1f3', edge=E), text='AUTOMATIC')),
    'OCTA': dict(kor='팔각 일체형 스포츠', case=(['integrated bracelet case NH35', 'octagon case NH35 bracelet sapphire'], r'integrat|octag|geometric|PRX', r'Seamaster|mesh|Presidential'),
                 hands=(['baton hands NH35', 'NH35 baton hands luminous'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='dress',
                 cfg=dict(caseD=40, lug=27, l2l=42, noLugs=True, metal='steel', crown=[3.2, 5.6],
                          bezel=dict(type='octagon', outer=20.0, inner=16.0), chapterW=0.7, chapterColor='#c9ced3',
                          dialFinish='tapisserie', lume='#f1f6e6', markEdge='#e3e7eb', vign=.25, marks=dict(twelve='rect2', quarter='rect', other='rect'), markSize=1.05, markInset=2.5, date=True,
                          hands=dict(hour='lumebaton', hl=.58, hw=1.7, minute='lumebaton', ml=.92, mw=1.35, sec='plain', secColor='#e3e6e9', edge=E), text='AUTOMATIC')),
    'EXPLORER': dict(kor='익스플로러 스타일', case=(['explorer case 39mm NH35', '36mm explorer case NH35'], r'39|40|explorer|oyster', r'flut|GMT|diver|ceramic'),
                     hands=(['mercedes hands NH35', 'NH35 sub hands'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='explorer',
                     cfg=dict(caseD=39, lug=20, l2l=47, metal='steel', crown=[3.4, 6.2],
                              bezel=dict(type='smooth', outer=19.0, inner=16.4), chapterW=0.8, chapterColor='#c9ced3',
                              dialFinish='gloss', minuteTrack=True, lume='#f0f4e4', markEdge='#e9ecef', marks=dict(style='explorer', twelve='tri', quarter='rect', other='rect'), markSize=1.15, markInset=2.9, date=False,
                              hands=dict(hour='merc', hl=.56, hw=2.2, minute='pencil', ml=.93, mw=1.6, sec='lolli', secColor='#e3e6e9', edge=E), text='AUTOMATIC')),
}

STRAPS = {
    'rubber22': (['22mm rubber watch strap'], r'rubber|FKM|silicone', r'smart|apple|samsung|galaxy|Tudor|Omega|Rolex|Blancpain|IWC|huawei|garmin'),
    'rubber20': (['20mm FKM rubber strap', '20mm rubber strap navy'], r'rubber|FKM', r'smart|apple|samsung|galaxy|Tudor|Omega|Rolex|Blancpain|IWC'),
    'tropic': (['20mm tropic rubber strap'], r'trop', r'smart|apple|samsung|Tudor|Omega|Rolex|Blancpain|IWC'),
    'nato': (['20mm nato strap'], r'nato|nylon', r'smart|apple|samsung|galaxy'),
    'brown': (['20mm brown leather watch strap', '20mm leather watch strap'], r'leather', r'smart|apple|samsung|galaxy|alligator'),
    'black': (['20mm black leather watch strap'], r'leather', r'smart|apple|samsung|galaxy'),
    'oyster': (['20mm oyster bracelet'], r'oyster|bracelet|steel', r'smart|apple|samsung|galaxy|mesh'),
    'jubilee': (['22mm jubilee bracelet'], r'jubilee', r'smart|apple|samsung|galaxy'),
}
STRAP_KOR = dict(rubber22='러버 22mm', rubber20='러버 20mm', tropic='트로픽 러버', nato='나토', brown='브라운 가죽', black='블랙 가죽', oyster='오이스터 브레이슬릿', jubilee='주빌리 브레이슬릿', integrated='일체형 브레이슬릿(케이스 포함)')
STRAP_RENDER = {
    'rubber22': dict(strap='rubber'), 'rubber20': dict(strap='rubber'), 'tropic': dict(strap='tropic', strapColor='#151515'),
    'nato': dict(strap='leather', stitch='rgba(255,255,255,0)'), 'brown': dict(strap='leather', strapColor='#6b4226', stitch='#d9c3a0'),
    'black': dict(strap='leather', strapColor='#1c1c1e', stitch='#8a8a8a'), 'oyster': dict(strap='oyster'), 'jubilee': dict(strap='jubilee'),
    'integrated': dict(strap='integrated'),
}

COLORS = {  # key: (kor, dial hex, print)
    'black': ('블랙', '#141518', '#e9e9e9'), 'blue': ('블루', '#1f3d7a', '#eef2f8'), 'green': ('그린', '#1f5a3c', '#eef3ee'),
    'white': ('화이트', '#f3f3f1', '#26282c'), 'grey': ('그레이', '#5a5f66', '#f0f0f0'), 'orange': ('오렌지', '#e0661f', '#fff4ea'),
    'red': ('레드', '#9c1f24', '#fbecec'), 'yellow': ('옐로', '#e2b21c', '#2a2410'), 'brown': ('브라운', '#5b3a24', '#f1e3cf'),
    'cream': ('크림', '#efe6cf', '#2b2620'), 'silver': ('실버', '#c9cdd2', '#26282c'), 'salmon': ('살몬', '#e3a27e', '#3a2418'),
    'purple': ('퍼플', '#5a3d86', '#f1ecf8'), 'pink': ('핑크', '#e9b3c4', '#4a2532'), 'iceblue': ('아이스블루', '#a7d3e6', '#203440'),
    'champagne': ('샴페인', '#d9c08a', '#3a2f14'), 'burgundy': ('버건디', '#5e1a24', '#f6e6e8'), 'mop': ('자개', '#f3efe9', '#2a2224'),
}
BEZEL = {  # diver insert colours
    'black': ('#151619', None, '#f2f2f2'), 'blue': ('#1f3f8f', None, '#f4f4f4'), 'pepsi': ('#a3202a', '#1f3f8f', '#f4f4f4'),
    'batman': ('#1f3f8f', '#151619', '#f4f4f4'), 'coke': ('#a3202a', '#151619', '#f4f4f4'), 'green': ('#1d5a3c', None, '#ecefea'),
    'orange': ('#d9621d', None, '#151515'), 'grey': ('#5b6067', None, '#f2f2f2'), 'burgundy': ('#6a1c26', None, '#e9d2a0'),
    'brown': ('#4a3020', None, '#e5c99a'), 'white': ('#eceeee', None, '#1e1f22'),
}
BEZEL_KOR = dict(black='블랙', blue='블루', pepsi='펩시(레드·블루)', batman='배트맨(블루·블랙)', coke='코크(레드·블랙)', green='그린', orange='오렌지', grey='그레이', burgundy='버건디', brown='브라운', white='화이트')

# 10 variants per style: (dial colour, bezel, strap, extra)
V = {
    'SKX': [('black', 'black', 'rubber22'), ('blue', 'pepsi', 'jubilee'), ('orange', 'black', 'rubber22'), ('black', 'pepsi', 'jubilee'), ('green', 'green', 'nato'),
            ('white', 'blue', 'rubber22'), ('grey', 'grey', 'jubilee'), ('yellow', 'black', 'rubber22'), ('blue', 'blue', 'rubber22'), ('black', 'coke', 'jubilee')],
    'SUB': [('black', 'black', 'oyster'), ('blue', 'blue', 'oyster'), ('green', 'green', 'oyster'), ('black', 'green', 'oyster'), ('blue', 'batman', 'jubilee'),
            ('grey', 'black', 'oyster'), ('white', 'black', 'oyster'), ('black', 'pepsi', 'jubilee'), ('burgundy', 'burgundy', 'oyster'), ('iceblue', 'brown', 'oyster')],
    'MAS': [('black', 'black', 'tropic'), ('grey', 'black', 'oyster'), ('blue', 'blue', 'tropic'), ('green', 'black', 'brown'), ('brown', 'brown', 'brown'),
            ('cream', 'black', 'tropic'), ('black', 'burgundy', 'oyster'), ('blue', 'black', 'nato'), ('grey', 'grey', 'tropic'), ('green', 'green', 'oyster')],
    'BB': [('black', 'black', 'oyster'), ('black', 'burgundy', 'oyster'), ('blue', 'blue', 'oyster'), ('brown', 'brown', 'brown'), ('green', 'green', 'nato'),
           ('black', 'burgundy', 'brown'), ('blue', 'blue', 'nato'), ('grey', 'black', 'black'), ('black', 'black', 'tropic'), ('burgundy', 'burgundy', 'brown')],
    'TURTLE': [('black', 'black', 'rubber22'), ('blue', 'pepsi', 'rubber22'), ('blue', 'blue', 'rubber22'), ('orange', 'black', 'rubber22'), ('green', 'black', 'nato'),
               ('white', 'black', 'rubber22'), ('grey', 'grey', 'jubilee'), ('black', 'coke', 'rubber22'), ('yellow', 'black', 'rubber22'), ('brown', 'brown', 'brown')],
    'BRONZE': [('green', 'green', 'brown'), ('brown', 'brown', 'brown'), ('black', 'black', 'brown'), ('blue', 'blue', 'brown'), ('green', 'black', 'nato'),
               ('cream', 'brown', 'brown'), ('grey', 'black', 'black'), ('blue', 'black', 'nato'), ('black', 'brown', 'tropic'), ('champagne', 'brown', 'brown')],
    'FIELD': [('white', None, 'brown'), ('black', None, 'brown'), ('green', None, 'nato'), ('cream', None, 'brown'), ('blue', None, 'black'),
              ('black', None, 'nato'), ('white', None, 'black'), ('grey', None, 'nato'), ('brown', None, 'brown'), ('cream', None, 'nato')],
    'PILOT': [('black', None, 'brown'), ('blue', None, 'brown'), ('green', None, 'brown'), ('cream', None, 'black'), ('grey', None, 'black'),
              ('black', None, 'black'), ('blue', None, 'nato'), ('brown', None, 'brown'), ('white', None, 'brown'), ('black', None, 'nato')],
    'DRESS': [('white', None, 'black'), ('blue', None, 'brown'), ('green', None, 'brown'), ('salmon', None, 'brown'), ('silver', None, 'black'),
              ('black', None, 'black'), ('champagne', None, 'brown'), ('grey', None, 'black'), ('burgundy', None, 'brown'), ('cream', None, 'brown')],
    'OCTA': [('blue', None, 'integrated'), ('green', None, 'integrated'), ('grey', None, 'integrated'), ('black', None, 'integrated'), ('iceblue', None, 'integrated'),
             ('white', None, 'integrated'), ('salmon', None, 'integrated'), ('purple', None, 'integrated'), ('brown', None, 'integrated'), ('silver', None, 'integrated')],
}
# 10th style: EXPLORER replaces nothing — 11 styles x ~9 would exceed; keep 10 styles x 10 = 100
ORDER = ['SKX', 'SUB', 'MAS', 'BB', 'TURTLE', 'BRONZE', 'FIELD', 'PILOT', 'DRESS', 'OCTA']

# curated case per style (checked by hand: right size/style, 28.5mm dial, good sales)
PREF = {'SUB': '3256806812392828', 'BB': '3256812254952485', 'BRONZE': '3256806944949739', 'FIELD': '3256811690556918',
        'PILOT': '3256812410081441', 'DRESS': '3256810323017539', 'OCTA': '3256812525167334',
        'FLUTE36': '3256808915969609', 'EXP36': '3256807066497943', 'MINI': '3256809249370712'}

MOVEMENT = {'clone': POOL.get('3256811827697822'), 'genuine': POOL.get('3256805411410101')}


def part(p, label, note=''):
    if not p:
        return None
    return dict(label=label, id=p['id'], title=p['title'], price=p['price'], orig=p.get('orig'), rating=p['rating'],
                sold_s=p['sold_s'], img=p['img'], bait=bool(p['price'] <= 1.2 and p.get('orig')), note=note)


def build(code, style, dial_color, bezel, strap, overrides=None, women=False):
    st = STYLES[style]
    pref = (overrides or {}).pop('_case', None) or PREF.get(style)
    if pref and pref in POOL:
        case = POOL[pref]
    else:
        cases = candidates(*st['case'][:1], inc=st['case'][1], exc=st['case'][2])
        case = cases[0] if cases else None
    dial, exact = pick_dial(dial_color, st['dialstyle'])
    hands_c = candidates(st['hands'][0], inc=st['hands'][1], exc=st['hands'][2], logo=True)
    hands = hands_c[0] if hands_c else None
    dial_has_hands = bool(dial and re.search(r'hands|pointer|needle', dial['title'], re.I))
    parts = [part(case, '케이스', '옵션에서 베젤/색상 선택' if bezel else ''), part(dial, '다이얼', '' if exact else '색상 옵션 확인')]
    if not dial_has_hands:
        parts.append(part(hands, '핸즈'))
    ct = case['title'] if case else ''
    included = (strap == 'oyster' and re.search(r'oyster|bracelet', ct, re.I)) or \
               (strap == 'jubilee' and re.search(r'jubilee|presidential', ct, re.I)) or \
               (strap in ('rubber22', 'rubber20') and re.search(r'rubber|silicone', ct, re.I))
    if strap != 'integrated' and not included:
        sq = STRAPS[strap]
        sc = candidates(sq[0], inc=sq[1], exc=sq[2])
        parts.append(part(sc[0] if sc else None, '스트랩'))
    parts = [p for p in parts if p]
    cfg = copy.deepcopy(st['cfg'])
    kor, hexc, prt = COLORS[dial_color]
    cfg.update(dialColor=hexc, print=prt, id=code.lower(), code=code)
    if dial_color in ('white', 'cream', 'silver', 'iceblue', 'pink', 'salmon', 'champagne', 'yellow', 'mop'):
        cfg['vign'] = .12
        if style in ('SKX', 'SUB', 'TURTLE', 'EXPLORER'):
            cfg['markEdge'] = '#2a2e35'
        if style in ('FIELD',):
            pass
    if style == 'PILOT' and dial_color in ('cream', 'white'):
        cfg.update(lume='#2a2620', markEdge='#2a2620')
    if style == 'FIELD' and dial_color not in ('white', 'cream'):
        cfg.update(handMetal='steel', markEdge='#e9e9e9', hands={**cfg['hands'], 'secColor': '#e9e9e9', 'edge': E})
    if bezel and cfg['bezel']['type'] == 'diver':
        c1, c2, ink = BEZEL[bezel]
        cfg['bezel'].update(color=c1, ink=ink)
        if c2:
            cfg['bezel']['color2'] = c2
        else:
            cfg['bezel'].pop('color2', None)
        if style == 'BB' and bezel in ('black', 'burgundy', 'blue', 'brown', 'green'):
            cfg['bezel']['ink'] = '#d9b46a'
    sr = STRAP_RENDER[strap]
    cfg.update(sr)
    if strap in ('rubber22', 'rubber20'):
        cfg['strapColor'] = {'blue': '#1f3f8f', 'orange': '#d9621d', 'green': '#24412f', 'yellow': '#d9a81c', 'white': '#e9ebee'}.get(dial_color, '#1b1c1f')
    if strap == 'nato':
        cfg['strapColor'] = {'green': '#4a5a32', 'black': '#202124', 'grey': '#5a5f66', 'cream': '#b8a77f', 'blue': '#24365c'}.get(dial_color, '#4a5a32')
    cfg['bg'] = ['#f6f6f4', '#d7d8da']
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    name = f"{st['kor']} · {kor}{' 다이얼' if not women else ''}"
    spec = f"{cfg['caseD']}mm · {kor} 다이얼" + (f" · {BEZEL_KOR[bezel]} 베젤" if bezel else '') + f" · {STRAP_KOR[strap]}"
    total = sum(p['price'] for p in parts)
    return dict(code=code, style=style, style_kor=st['kor'], name=name, spec=spec, women=women, cfg=cfg, parts=parts, strap_included=bool(included) or strap == 'integrated', strap_kor=STRAP_KOR[strap],
                parts_total=round(total, 2), total_clone=round(total + MOVEMENT['clone']['price'], 2),
                total_genuine=round(total + MOVEMENT['genuine']['price'], 2))


combos = []
n = 0
for style in ORDER:
    for dial_color, bezel, strap in V[style]:
        n += 1
        combos.append(build(f'M{n:03d}', style, dial_color, bezel, strap))

# ---------------------------------------------------------------- women (10)
STYLES['FLUTE36'] = dict(kor='플루티드 36mm', case=(['36mm fluted bezel case NH35 jubilee', '36mm fluted case rose gold NH35'], r'flut', r'dial'),
                         hands=(['NH35 hands rose gold', 'NH35 hands silver baton'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='dress',
                         cfg=dict(caseD=36, lug=20, l2l=44, metal='steel', crown=[3.0, 5.2], bezel=dict(type='fluted', outer=17.6, inner=15.2), chapterW=0.8, chapterColor='#efe8df',
                                  dialFinish='sunburst', minuteTrack=True, lume='#fff', markEdge='#c9cdd2', vign=.12, marks=dict(twelve='baton2', quarter='baton', other='baton'), markSize=1.15, markInset=2.9, date=True,
                                  hands=dict(hour='baton', hl=.55, hw=1.3, minute='baton', ml=.90, mw=1.0, lume=False, sec='plain', secColor='#d0d4d8', edge=E)))
STYLES['EXP36'] = dict(kor='스무스 36mm', case=(['36mm case sapphire NH35 bracelet', '36mm explorer case NH35'], r'36', r'flut|dial'),
                       hands=(['NH35 hands silver baton', 'baton hands NH35'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='dress',
                       cfg=dict(caseD=36, lug=20, l2l=43.5, metal='steel', crown=[3.0, 5.2], bezel=dict(type='smooth', outer=17.6, inner=15.6), chapterW=0.9, chapterColor='#dfe3e6',
                                dialFinish='sunburst', minuteTrack=True, lume='#f2f7ea', markEdge='#d9dde1', vign=.16, marks=dict(twelve='rect2', quarter='rect', other='rect'), markSize=1.0, markInset=2.6, date=False,
                                hands=dict(hour='lumebaton', hl=.56, hw=1.6, minute='lumebaton', ml=.90, mw=1.3, sec='plain', secColor='#eef1f3', edge=E)))
STYLES['MINI'] = dict(kor='미니 다이버 38mm', case=(['SKX013 case sapphire NH35', '36mm diver case NH35', '38mm diver case NH35'], r'SKX013|3[678]\s?mm', r'44mm|45mm|insert only|acrylic'),
                      hands=(['NH35 hands C3 luminous', 'skx hands NH35'], r'hand|pointer|needle', r'dial|GMT|4\s?pins'), dialstyle='diver',
                      cfg=dict(caseD=38, lug=20, l2l=44, metal='steel', crown=[3.0, 5.6], crownGuard=True, bezel=dict(type='diver', outer=17.3, inner=14.3, color='#1d5a3c', ink='#e9ece8', numSize=2.3, ceramic=True),
                               chapterW=1.0, chapterColor='#eceff2', chapterTicks='#30343a', dialFinish='matte', lume='#f1f6e6', markEdge='#2a2e35', markEdgeW=2.4, vign=.10,
                               marks=dict(twelve='tri', quarter='bar', other='dot'), markSize=1.05, markInset=2.4, date=True,
                               hands=dict(hour='sword', hl=.58, hw=2.2, minute='sword', ml=.92, mw=1.7, sec='lolli', secColor='#c8402e', edge='rgba(20,24,30,.8)'), text='AUTOMATIC'))
STYLES['GOLD36'] = dict(kor='골드 PVD 36mm', case=(['gold PVD case 36mm NH35 sapphire', 'gold watch case 36mm NH35 bracelet'], r'gold', r'dial'),
                        hands=(['gold hands NH35', 'NH35 hands rose gold'], r'hand|pointer|needle', r'dial|GMT'), dialstyle='dress',
                        cfg=dict(caseD=36, lug=20, l2l=44, metal='gold', crown=[3.0, 5.2], bezel=dict(type='fluted', outer=17.6, inner=15.2), chapterW=0.8, chapterColor='#e9dcae',
                                 dialFinish='sunburst', minuteTrack=True, lume='#fff', markEdge='#e0bf62', markMetal='gold', vign=.3, marks=dict(twelve='baton2', quarter='baton', other='baton'), markSize=1.15, markInset=2.9, date=True, dateBg='#fffdf5',
                                 handMetal='gold', hands=dict(hour='baton', hl=.55, hw=1.3, minute='baton', ml=.90, mw=1.0, lume=False, sec='plain', secColor='#e0bf62', edge='rgba(90,60,10,.55)')))
WOMEN = [
    ('FLUTE36', 'mop', None, 'jubilee', dict(metal='rose', handMetal='rose', markMetal='rose', dialFinish='mop', marks=dict(style='roman'), date=False, chapterColor='#efe8df', bg=['#fbf6f3', '#e7d9d2'], hands=dict(secColor='#b9805f', edge='rgba(80,40,20,.45)'))),
    ('FLUTE36', 'pink', None, 'jubilee', dict(bg=['#fbf6f7', '#e8dadd'])),
    ('FLUTE36', 'silver', None, 'jubilee', dict()),
    ('EXP36', 'iceblue', None, 'oyster', dict()),
    ('EXP36', 'purple', None, 'oyster', dict(dialColor='#9b86c9')),
    ('GOLD36', 'green', None, 'oyster', dict()),
    ('GOLD36', 'champagne', None, 'oyster', dict(dialColor='#e3cf98', print='#3a2f14')),
    ('MINI', 'white', 'green', 'rubber20', dict()),
    ('MINI', 'pink', 'white', 'rubber20', dict(strapColor='#e9b3c4')),
    ('DRESS', 'salmon', None, 'brown', dict(_case='3256802494646018', caseD=36, l2l=43, bezel=dict(outer=17.6, inner=16.2))),
]
for i, (style, col, bez, strap, ov) in enumerate(WOMEN, 1):
    c = build(f'F{i:02d}', style, col, bez, strap, ov, women=True)
    combos.append(c)

json.dump(dict(movement=MOVEMENT, usd_krw=USD_KRW, combos=combos), open(OUT, 'w'), ensure_ascii=False, indent=1)
print('combos', len(combos))
from collections import Counter
print('unique parts', len({p['id'] for c in combos for p in c['parts']}))
for c in combos[:3] + combos[-2:]:
    print(c['code'], c['name'], c['parts_total'], [(p['label'], p['id'][-6:], p['price']) for p in c['parts']])
