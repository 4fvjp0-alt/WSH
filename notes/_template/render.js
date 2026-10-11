const { chromium } = require('playwright');
(async () => {
  const S = process.argv[2];
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 1.5 });
  await p.goto('file://' + S + '/notes.html');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(500);
  const of = await p.evaluate(() => [...document.querySelectorAll('.page')].map((pg, i) => {
    const r = pg.getBoundingClientRect(); let max = 0;
    pg.querySelectorAll('*').forEach(e => { if (e.closest('.ft')||e.closest('.hd')) return; const b = e.getBoundingClientRect(); if (b.bottom > max) max = b.bottom; });
    return (i+1) + ':' + Math.round(r.bottom - max);
  }));
  console.log('space left (px):', of.join(' '));
  const pages = await p.$$('.page');
  for (let i = 0; i < pages.length; i++) await pages[i].screenshot({ path: `${S}/shot/s${i+1}.png` });
  await p.pdf({ path: `${S}/out.pdf`, format: 'A4', printBackground: true, preferCSSPageSize: true });
  await b.close();
})();
