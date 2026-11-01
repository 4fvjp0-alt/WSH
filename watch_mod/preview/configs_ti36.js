const base = o => Object.assign({ caseD: 36, l2l: 44.6, lug: 18, metal: 'titanium', crown: [3.4, 6.0],
  bezel: { type: 'smooth', outer: 17.6, inner: 16.2 }, chapterW: 0.5, chapterColor: '#151618', dialColor: '#121316', dialFinish: 'matte',
  print: '#f2f2ee', minuteTrack: true, lume: '#eef1e4', markEdge: '#e9e9e9', vign: .25, marks: { style: 'arabic' }, date: false,
  hands: { hour: 'sword', hl: .56, hw: 2.2, minute: 'sword', ml: .93, mw: 1.7, sec: 'plain', secColor: '#e6e6e6', edge: 'rgba(0,0,0,.35)' },
  strap: 'leather', bg: ['#f7f4ef', '#ddd5ca'] }, o);
module.exports = [
  base({ id: 't1', code: 'TI36_TAN', strapColor: '#9a6a3f', stitch: '#efe0c8' }),
  base({ id: 't2', code: 'TI36_CHOCO', strapColor: '#4e2f1c', stitch: '#d9c3a0' }),
  base({ id: 't3', code: 'TI36_SUEDE', strapColor: '#b58a5c', stitch: 'rgba(255,255,255,0)' }),
];
