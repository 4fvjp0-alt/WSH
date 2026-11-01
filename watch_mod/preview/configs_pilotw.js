const base = o => Object.assign({ lug: 18, metal: 'steel', crown: [3.0, 5.4],
  chapterW: 0.5, chapterColor: '#151618', dialColor: '#121316', dialFinish: 'matte', print: '#f2f2ee', minuteTrack: true,
  lume: '#eef1e4', markEdge: '#e9e9e9', vign: .25, marks: { style: 'arabic' }, date: false,
  hands: { hour: 'sword', hl: .56, hw: 2.2, minute: 'sword', ml: .93, mw: 1.7, sec: 'plain', secColor: '#e6e6e6', edge: 'rgba(0,0,0,.35)' },
  strap: 'leather', strapColor: '#9a6a3f', stitch: '#efe0c8', bg: ['#f7f4ef', '#ddd5ca'] }, o);
module.exports = [
  base({ id: 'pa', code: 'PW_A', caseD: 33, l2l: 40, bezel: { type: 'smooth', outer: 16.2, inner: 15.2 }, chapterW: 0.3 }),
  base({ id: 'pa2', code: 'PW_A_ROSE', caseD: 33, l2l: 40, metal: 'rose', bezel: { type: 'smooth', outer: 16.2, inner: 15.2 }, chapterW: 0.3, strapColor: '#5a3720', stitch: '#d9c3a0' }),
  base({ id: 'pb', code: 'PW_B', caseD: 36, l2l: 44, lug: 20, bezel: { type: 'smooth', outer: 17.6, inner: 16.2 }, chapterW: 0.5 }),
];
