// NH35A / NH38A (Japan genuine) price tracker for AliExpress Korea (KRW).
// Usage: node track.js            -> search, append history.json, write chart.png + latest.md
//        node track.js --chart    -> only rebuild chart/report from history.json
// Needs: playwright (preinstalled in the cloud container) and network access to *.aliexpress.com, *.alicdn.com.
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const DIR = __dirname, HIST = path.join(DIR, 'history.json');

const GROUPS = {
  NH38A: { queries: ['NH38A movement japan genuine', 'NH38 movement', '일본 정품 NH38A 무브먼트'], model: /NH38/i,
           watch: { '1005010806500239': '정품 NH38A ★4.9 1K+', '1005008240895208': '정품 NH38A ★4.9 2K+' } },
  NH35A: { queries: ['NH35A movement japan genuine', 'TMI NH35 movement', '일본 정품 NH35A 무브먼트'], model: /NH35/i,
           watch: { '1005006845396357': '정품 NH35A ★4.8 687', '1005001430226835': '정품 NH35A(옵션) ★4.8 618', '1005012515033825': '정품 NH35/38 ★5.0 253' } },
};
const GENUINE = /정품|genuine|original|오리지널|TMI|일본|japan/i;
const CLONE = /중국|china|차이나|클론|복제|copy|대체할/i;
const PARTS = /스템|stem|로터|rotor|해머|핸즈|바늘|hands|다이얼|dial|케이스|case|휠|wheel|밸런스|balance|도구|tool|홀더|holder/i;

function parse(t) {
  const pr = [...t.matchAll(/₩([\d,]+)/g)].map(m => +m[1].replace(/,/g, ''));
  const ms = t.match(/(?:(\d\.\d|\d)\s+)?([\d,.]+K?\+?)\s*판매/);
  let rating = ms && ms[1] ? +ms[1] : null;
  if (rating == null) { const mr = t.match(/판매\s+(\d\.\d)\s/); rating = mr ? +mr[1] : null; }
  let s = ms ? ms[2] : '0', n = s.replace(/[,+]/g, '');
  const sold = n.endsWith('K') ? Math.round(parseFloat(n) * 1000) : parseInt(n || '0', 10) || 0;
  const title = t.split(/\s-?\d+%\s|\s₩/)[0];
  return { price: pr[0] || null, rating, sold, sold_s: s, title };
}

async function search() {
  const b = await chromium.launch();
  const ctx = await b.newContext({ locale: 'ko-KR', viewport: { width: 1400, height: 1000 } });
  await ctx.addCookies([{ name: 'aep_usuc_f', value: 'site=kor&c_tp=KRW&region=KR&b_locale=ko_KR', domain: '.aliexpress.com', path: '/' }]);
  const p = await ctx.newPage(); const out = {};
  for (const [g, cfg] of Object.entries(GROUPS)) {
    out[g] = {};
    for (const q of cfg.queries) {
      try {
        await p.goto('https://www.aliexpress.com/w/wholesale-' + q.replace(/\s+/g, '-') + '.html', { timeout: 45000, waitUntil: 'domcontentloaded' });
        await p.waitForTimeout(4000);
        for (let k = 0; k < 5; k++) { await p.mouse.wheel(0, 1400); await p.waitForTimeout(600); }
        const items = await p.$$eval('a[href*="/item/"]', as => { const s = new Set(), r = []; for (const a of as) { const m = a.href.match(/item\/(\d+)/); if (!m || s.has(m[1])) continue; const t = a.innerText.replace(/\s+/g, ' ').trim(); if (t.length < 20) continue; s.add(m[1]); r.push({ id: m[1], t: t.slice(0, 320) }); } return r; });
        for (const it of items) if (!out[g][it.id]) out[g][it.id] = { id: it.id, ...parse(it.t) };
      } catch (e) { console.error('search failed', q, e.message.split('\n')[0]); }
      await p.waitForTimeout(1200);
    }
  }
  await b.close(); return out;
}

function summarize(found) {
  const snap = { ts: new Date().toISOString(), groups: {} };
  for (const [g, cfg] of Object.entries(GROUPS)) {
    const all = Object.values(found[g] || {});
    const genuine = all.filter(x => x.price && x.price >= 60000 && x.price <= 250000 && cfg.model.test(x.title) && GENUINE.test(x.title) && !CLONE.test(x.title) && !PARTS.test(x.title));
    const qualified = genuine.filter(x => (x.rating || 0) >= 4.7 && x.sold >= 100);
    const minOf = a => a.length ? a.reduce((m, x) => x.price < m.price ? x : m) : null;
    const watch = {}; for (const id of Object.keys(cfg.watch)) { const x = all.find(y => y.id === id); if (x && x.price) watch[id] = x.price; }
    const pick = x => x && { id: x.id, price: x.price, rating: x.rating, sold_s: x.sold_s, title: x.title.slice(0, 80) };
    snap.groups[g] = { min_qualified: pick(minOf(qualified)), min_genuine: pick(minOf(genuine)), watch, n_genuine: genuine.length };
  }
  return snap;
}

const won = n => n == null ? '-' : '₩' + n.toLocaleString('ko-KR');
const link = id => `https://www.aliexpress.com/item/${id}.html`;

function series(H, g) {
  const S = { '검증된 정품 최저가 (★4.7+·100개+)': H.map(h => [h.ts, h.groups[g]?.min_qualified?.price ?? null]) };
  for (const [id, name] of Object.entries(GROUPS[g].watch)) S[name] = H.map(h => [h.ts, h.groups[g]?.watch?.[id] ?? null]);
  return S;
}

function report(H) {
  const last = H[H.length - 1], prev = H[H.length - 2];
  let md = `# NH35A / NH38A 일본 정품 가격 추적\n\n마지막 확인: ${new Date(last.ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} (기록 ${H.length}회)\n\n`;
  const alerts = [];
  for (const g of Object.keys(GROUPS)) {
    const cur = last.groups[g]?.min_qualified, before = prev?.groups[g]?.min_qualified;
    const hist = H.map(h => h.groups[g]?.min_qualified?.price).filter(Boolean);
    const low = hist.length ? Math.min(...hist) : null;
    md += `## ${g}\n- 검증된 정품 최저가: **${won(cur?.price)}** ${cur ? `[#${cur.id}](${link(cur.id)}) ★${cur.rating} · ${cur.sold_s}판매` : '(오늘 검색에서 못 찾음)'}\n`;
    if (before && cur) md += `- 직전 대비: ${cur.price - before.price >= 0 ? '+' : ''}${won(cur.price - before.price).replace('₩-', '-₩')}\n`;
    md += `- 기록상 최저: ${won(low)}\n`;
    for (const [id, name] of Object.entries(GROUPS[g].watch)) md += `- ${name}: ${won(last.groups[g]?.watch?.[id])} ([링크](${link(id)}))\n`;
    if (cur && low && cur.price <= low && hist.length > 1) alerts.push(`${g} 지금이 기록상 최저가 ${won(cur.price)}`);
    md += '\n';
  }
  md = (alerts.length ? `> 🔔 **${alerts.join(' / ')}**\n\n` : '') + md + '![chart](chart.png)\n';
  fs.writeFileSync(path.join(DIR, 'latest.md'), md);
  return { md, alerts };
}

async function chart(H) {
  const colors = ['#dc2626', '#2563eb', '#16a34a', '#9333ea', '#ea580c'];
  const panel = g => {
    const S = series(H, g), W = 760, Ht = 300, L = 70, R = 20, T = 20, B = 50;
    const pts = Object.values(S).flat().filter(p => p[1] != null); if (!pts.length) return `<h2>${g}</h2><p>데이터 없음</p>`;
    const t0 = +new Date(H[0].ts), t1 = Math.max(+new Date(H[H.length - 1].ts), t0 + 3600e3);
    let lo = Math.min(...pts.map(p => p[1])), hi = Math.max(...pts.map(p => p[1])); const pad = Math.max((hi - lo) * 0.15, 3000); lo -= pad; hi += pad;
    const X = t => L + (W - L - R) * (+new Date(t) - t0) / (t1 - t0), Y = v => T + (Ht - T - B) * (1 - (v - lo) / (hi - lo));
    let svg = `<svg width="${W}" height="${Ht}" xmlns="http://www.w3.org/2000/svg" font-family="sans-serif" font-size="11">`;
    for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; svg += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e5e7eb"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" fill="#6b7280">${Math.round(v / 1000)}k</text>`; }
    const days = new Set(H.map(h => new Date(h.ts).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric' })));
    [...days].forEach(d => { const h = H.find(x => new Date(x.ts).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric' }) === d); svg += `<text x="${X(h.ts)}" y="${Ht - B + 18}" text-anchor="middle" fill="#6b7280">${d}</text>`; });
    let legend = ''; let i = 0;
    for (const [name, s] of Object.entries(S)) {
      const c = colors[i++ % colors.length], q = s.filter(p => p[1] != null);
      if (q.length) { svg += `<polyline fill="none" stroke="${c}" stroke-width="${i === 1 ? 3 : 1.8}" points="${q.map(p => X(p[0]) + ',' + Y(p[1])).join(' ')}"/>` + q.map(p => `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="${i === 1 ? 3.5 : 2.5}" fill="${c}"/>`).join(''); }
      legend += `<span style="color:${c}">● ${name} ${q.length ? '₩' + q[q.length - 1][1].toLocaleString() : '-'}</span>`;
    }
    const m = S[Object.keys(S)[0]].filter(p => p[1] != null);
    if (m.length) { const low = m.reduce((a, b) => b[1] < a[1] ? b : a); svg += `<text x="${X(low[0])}" y="${Y(low[1]) + 18}" text-anchor="middle" fill="#dc2626" font-weight="bold">최저 ₩${low[1].toLocaleString()}</text>`; }
    return `<h2>${g}</h2>${svg}</svg><div class="lg">${legend}</div>`;
  };
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:sans-serif;margin:16px;width:800px}h1{font-size:20px;margin:0 0 4px}p{color:#6b7280;margin:0 0 8px;font-size:12px}h2{font-size:16px;margin:12px 0 4px}.lg{font-size:12px;display:flex;flex-wrap:wrap;gap:4px 14px}</style></head><body>
  <h1>NH35A / NH38A 일본 정품 가격 추이 (원화)</h1><p>AliExpress 한국 검색 결과 · 굵은 빨간 선 = 평점 4.7 이상·판매 100개 이상 정품 중 최저가 · 마지막 ${new Date(H[H.length - 1].ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}</p>${panel('NH38A')}${panel('NH35A')}</body></html>`;
  fs.writeFileSync(path.join(DIR, 'chart.html'), html);
  const b = await chromium.launch(); const p = await b.newPage({ deviceScaleFactor: 2, viewport: { width: 832, height: 800 } });
  await p.goto('file://' + path.join(DIR, 'chart.html')); await p.screenshot({ path: path.join(DIR, 'chart.png'), fullPage: true }); await b.close();
}

(async () => {
  const H = fs.existsSync(HIST) ? JSON.parse(fs.readFileSync(HIST, 'utf8')) : [];
  if (!process.argv.includes('--chart')) { const snap = summarize(await search()); H.push(snap); fs.writeFileSync(HIST, JSON.stringify(H, null, 1)); }
  await chart(H); const { md, alerts } = report(H);
  console.log(md); if (alerts.length) console.log('ALERT:', alerts.join(' / '));
  await telegram(H, alerts);
})();

// Telegram: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (cloud environment variables). Needs api.telegram.org allowed.
async function telegram(H, alerts) {
  const tok = process.env.TELEGRAM_BOT_TOKEN, chat = process.env.TELEGRAM_CHAT_ID;
  if (!tok || !chat) { console.log('telegram: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipped'); return; }
  const last = H[H.length - 1], prev = H[H.length - 2];
  let text = (alerts.length ? '🔔 최저가! ' + alerts.join(' / ') + '\n\n' : '') + '⌚ NH35A/NH38A 정품 가격 (' + new Date(last.ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) + ')\n';
  for (const g of Object.keys(GROUPS)) {
    const c = last.groups[g]?.min_qualified, b = prev?.groups[g]?.min_qualified;
    const lows = H.map(h => h.groups[g]?.min_qualified?.price).filter(Boolean);
    const d = c && b ? c.price - b.price : null;
    text += `\n${g}: ${won(c?.price)}${d == null ? '' : d === 0 ? ' (변동 없음)' : d < 0 ? ` (▼${won(-d)})` : ` (▲${won(d)})`} · 기록 최저 ${won(Math.min(...lows))}` + (c ? `\n${link(c.id)}` : '');
  }
  try {
    const r = await fetch(`https://api.telegram.org/bot${tok}/sendPhoto`, { method: 'POST', body: (() => { const f = new FormData(); f.append('chat_id', chat); f.append('caption', text.slice(0, 1000)); f.append('photo', new Blob([fs.readFileSync(path.join(DIR, 'chart.png'))]), 'chart.png'); return f; })() });
    console.log('telegram:', r.status);
  } catch (e) { console.log('telegram failed:', e.message); }
}
