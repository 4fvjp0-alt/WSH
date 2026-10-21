// 표지 디자인 렌더: node render_cover.js <cover_designs.html이 있는 폴더>
// → 표지_디자인모음.pdf (전체), 표지_N_이름.pdf (한 장씩), shot/cN.png, 표지_미리보기.png
//   <body data-set="클래식"> 이면 → 표지_클래식모음.pdf, 표지_클래식_N_이름.pdf, 표지_클래식_미리보기.png
// 빈칸 채우기: node render_cover.js <폴더> <data.json>  → window.COVER = data, 출력은 data.json 폴더에
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const S = path.resolve(process.argv[2] || __dirname);
  const data = process.argv[3] ? JSON.parse(fs.readFileSync(process.argv[3], 'utf8')) : null;
  const O = data ? path.dirname(path.resolve(process.argv[3])) : S;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 1.5 });
  if (data) await p.addInitScript(d => { window.COVER = d; }, data);
  await p.goto('file://' + S + '/cover_designs.html');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(500);
  const names = await p.$$eval('.page', ps => ps.map(e => e.dataset.name));
  const set = await p.$eval('body', e => e.dataset.set || '');
  const pre = set ? `표지_${set}_` : '표지_';
  fs.mkdirSync(O + '/shot', { recursive: true });
  const pages = await p.$$('.page');
  for (let i = 0; i < pages.length; i++) await pages[i].screenshot({ path: `${O}/shot/c${i + 1}.png` });
  const opt = { format: 'A4', printBackground: true, preferCSSPageSize: true };
  await p.pdf({ ...opt, path: `${O}/표지_${set || '디자인'}모음.pdf` });
  for (let i = 0; i < names.length; i++) await p.pdf({ ...opt, path: `${O}/${pre}${i + 1}_${names[i]}.pdf`, pageRanges: String(i + 1) });

  // 한눈에 비교용 미리보기 (4 x 2)
  const cells = names.map((n, i) => `<figure><img src="file://${O}/shot/c${i + 1}.png"><figcaption>${i + 1}. ${n}</figcaption></figure>`).join('');
  await p.setViewportSize({ width: 1640, height: 1200 });
  await p.setContent(`<style>body{margin:0;background:#e9e6df;font:600 22px "PlexKR",sans-serif}
    @font-face{font-family:"PlexKR";src:url("file://${S}/fonts/IBMPlexSansKR-Bold.ttf")}
    .g{display:grid;grid-template-columns:repeat(4,370px);gap:28px 30px;padding:30px}
    figure{margin:0}img{width:370px;display:block;box-shadow:0 2px 10px rgba(0,0,0,.18)}
    figcaption{margin-top:10px;text-align:center;color:#333}</style><div class="g">${cells}</div>`);
  await p.evaluate(() => Promise.all([...document.images].map(im => im.decode())).then(() => document.fonts.ready));
  await p.screenshot({ path: `${O}/${pre}미리보기.png`, fullPage: true });
  await b.close();
  console.log('pages:', names.map((n, i) => `${i + 1}.${n}`).join(' '));
})();
