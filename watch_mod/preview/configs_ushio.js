const base = (o) => Object.assign({ caseD: 40, lug: 20, l2l: 47, metal: 'titanium', crown: [3.4, 6.6], crownGuard: true,
  bezel: { type: 'diver', outer: 19.0, inner: 15.3, color: '#1c2f63', ink: '#eef1f6', ceramic: true }, chapterW: 0.9, chapterColor: '#1a2547', chapterTicks: '#e9edf3',
  dialColor: '#1f3e7a', dialFinish: 'wave', print: '#eef2f8', minuteTrack: false, lume: '#eef3e6', markEdge: '#e3e7eb', vign: .55,
  marks: { twelve: 'rect2', quarter: 'rect', other: 'rect' }, markSize: 1.15, markInset: 2.7, date: true,
  hands: { hour: 'arrow', hl: .60, hw: 2.9, minute: 'sword', ml: .93, mw: 1.9, sec: 'plain', secColor: '#e3e6e9', edge: 'rgba(0,0,0,.35)' },
  strap: 'oyster', text: 'AUTOMATIC', text2: 'DIVER 300m', bg: ['#f3f4f6', '#d2d6db'] }, o);
module.exports = [
  base({ id: 'u1', code: 'U1' }),
  base({ id: 'u2', code: 'U2', bezel: { type: 'diver', outer: 19.0, inner: 15.3, color: '#1e4a3b', ink: '#eef3ef', ceramic: true }, chapterColor: '#173a2f', dialColor: '#24604c' }),
  base({ id: 'u3', code: 'U3', metal: 'steel', bezel: { type: 'diver', outer: 19.0, inner: 15.3, color: '#1c2f63', ink: '#eef1f6', ceramic: true }, dialColor: '#223f86' }),
  base({ id: 'u4', code: 'U4', metal: 'steel', bezel: { type: 'diver', outer: 19.0, inner: 15.3, color: '#1e4a3b', ink: '#eef3ef', ceramic: true }, chapterColor: '#173a2f', dialColor: '#2d7a63' }),
];
