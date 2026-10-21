// 표지 디자인 렌더: node render_cover.js <cover_designs.html이 있는 폴더>
// → 표지_디자인모음.pdf (전체), 표지_N_이름.pdf (한 장씩), shot/cN.png, 표지_미리보기.png
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const S = path.resolve(process.argv[2] || __dirname);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + S + '/cover_designs.html');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(500);
  const names = await p.$$eval('.page', ps => ps.map(e => e.dataset.name));
  fs.mkdirSync(S + '/shot', { recursive: true });
  const pages = await p.$$('.page');
  for (let i = 0; i < pages.length; i++) await pages[i].screenshot({ path: `${S}/shot/c${i + 1}.png` });
  const opt = { format: 'A4', printBackground: true, preferCSSPageSize: true };
  await p.pdf({ ...opt, path: `${S}/표지_디자인모음.pdf` });
  for (let i = 0; i < names.length; i++) await p.pdf({ ...opt, path: `${S}/표지_${i + 1}_${names[i]}.pdf`, pageRanges: String(i + 1) });

  // 한눈에 비교용 미리보기 (4 x 2)
  const cells = names.map((n, i) => `<figure><img src="file://${S}/shot/c${i + 1}.png"><figcaption>${i + 1}. ${n}</figcaption></figure>`).join('');
  await p.setViewportSize({ width: 1640, height: 1200 });
  await p.setContent(`<style>body{margin:0;background:#e9e6df;font:600 22px "PlexKR",sans-serif}
    @font-face{font-family:"PlexKR";src:url("file://${S}/fonts/IBMPlexSansKR-Bold.ttf")}
    .g{display:grid;grid-template-columns:repeat(4,370px);gap:28px 30px;padding:30px}
    figure{margin:0}img{width:370px;display:block;box-shadow:0 2px 10px rgba(0,0,0,.18)}
    figcaption{margin-top:10px;text-align:center;color:#333}</style><div class="g">${cells}</div>`);
  await p.evaluate(() => Promise.all([...document.images].map(im => im.decode())).then(() => document.fonts.ready));
  await p.screenshot({ path: `${S}/표지_미리보기.png`, fullPage: true });
  await b.close();
  console.log('pages:', names.map((n, i) => `${i + 1}.${n}`).join(' '));
})();
