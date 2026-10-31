// Procedural top-down watch renderer (SVG). 1mm = MM px.
const MM = 11, W = 600, H = 900, CX = 300, CY = 430;
const rad = d => d * Math.PI / 180;
const P = (r, a, cx = CX, cy = CY) => [cx + r * Math.sin(rad(a)), cy - r * Math.cos(rad(a))];
const f = n => n.toFixed(2);
let RNG = 1;
const rnd = () => (RNG = (RNG * 16807) % 2147483647) / 2147483647;

const METAL = {
  steel: ['#fbfcfd', '#d5d9de', '#9aa1a9', '#6b727a'],
  rose:  ['#fff1e8', '#efc3ab', '#c98d71', '#8e5a45'],
  bronze:['#f6dcb2', '#c99a5e', '#94653a', '#57391f'],
  gold:  ['#fff6d6', '#f0cf73', '#c79a34', '#7d5a14'],
  black: ['#5a5e64', '#2a2c30', '#16171a', '#050506'],
  titanium: ['#eef0f1', '#c3c7cb', '#959ba1', '#62686e'],
};

function metalDefs(id, m) {
  const [a, b, c, d] = METAL[m];
  return `
  <linearGradient id="${id}-lin" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="${a}"/><stop offset=".35" stop-color="${b}"/>
    <stop offset=".7" stop-color="${c}"/><stop offset="1" stop-color="${d}"/></linearGradient>
  <linearGradient id="${id}-h" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="${c}"/><stop offset=".25" stop-color="${a}"/>
    <stop offset=".55" stop-color="${b}"/><stop offset="1" stop-color="${d}"/></linearGradient>
  <linearGradient id="${id}-brush" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="${c}"/><stop offset=".5" stop-color="${b}"/><stop offset="1" stop-color="${c}"/></linearGradient>
  <linearGradient id="${id}-pol" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="${d}"/><stop offset=".35" stop-color="${a}"/><stop offset=".6" stop-color="${b}"/><stop offset="1" stop-color="${d}"/></linearGradient>
  <radialGradient id="${id}-ring" cx=".5" cy=".5" r=".5">
    <stop offset=".80" stop-color="${d}"/><stop offset=".86" stop-color="${a}"/>
    <stop offset=".93" stop-color="${b}"/><stop offset="1" stop-color="${d}"/></radialGradient>`;
}

function ring(r1, r2, attrs) { // annulus r1 outer, r2 inner
  return `<path fill-rule="evenodd" ${attrs} d="M${CX - r1},${CY} a${r1},${r1} 0 1,0 ${2 * r1},0 a${r1},${r1} 0 1,0 ${-2 * r1},0 Z
    M${CX - r2},${CY} a${r2},${r2} 0 1,0 ${2 * r2},0 a${r2},${r2} 0 1,0 ${-2 * r2},0 Z"/>`;
}
function wedge(r1, r2, a1, a2) {
  const [x1, y1] = P(r1, a1), [x2, y2] = P(r1, a2), [x3, y3] = P(r2, a2), [x4, y4] = P(r2, a1);
  return `M${f(x1)},${f(y1)} A${r1},${r1} 0 0,1 ${f(x2)},${f(y2)} L${f(x3)},${f(y3)} A${r2},${r2} 0 0,0 ${f(x4)},${f(y4)}Z`;
}

function cushionPath(R, n) {
  let d = '';
  for (let t = 0; t <= 360; t += 2) {
    const c = Math.cos(rad(t)), sn = Math.sin(rad(t));
    const x = CX + R * Math.sign(c) * Math.pow(Math.abs(c), 2 / n), y = CY + R * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / n);
    d += (t ? 'L' : 'M') + f(x) + ',' + f(y);
  }
  return d + 'Z';
}
function polyPath(R, N, rot) {
  let d = '';
  for (let k = 0; k < N; k++) { const [x, y] = P(R, rot + k * 360 / N); d += (k ? 'L' : 'M') + f(x) + ',' + f(y); }
  return d + 'Z';
}

/* ---------------- strap / bracelet ---------------- */
function strap(c, id, top) {
  const w0 = c.lug * MM, y0 = top ? 0 : CY, y1 = top ? CY : H;
  const len = Math.abs(y1 - y0);
  let s = '';
  const taperAt = y => { // width at y (narrower far from case)
    const t = Math.abs(y - CY) / (H / 2);
    return w0 * (1 - 0.13 * Math.min(1, t));
  };
  const outline = () => {
    const pts = [];
    for (let i = 0; i <= 20; i++) { const y = y0 + len * i / 20; pts.push([CX - taperAt(y) / 2, y]); }
    for (let i = 20; i >= 0; i--) { const y = y0 + len * i / 20; pts.push([CX + taperAt(y) / 2, y]); }
    return 'M' + pts.map(p => p.map(f).join(',')).join('L') + 'Z';
  };
  if (['rubber', 'tropic', 'leather'].includes(c.strap)) {
    const col = c.strapColor;
    s += `<path d="${outline()}" fill="${col}"/>`;
    s += `<path d="${outline()}" fill="url(#${id}-strapshade)"/>`;
    if (c.strap === 'tropic') s += `<path d="${outline()}" fill="url(#${id}-weave)"/>`;
    if (c.strap === 'rubber') {
      // center ridge + holes
      for (let y = y0; y < y1; y += 2) { /* nothing: smooth */ }
      if (!top) for (let k = 0; k < 4; k++) {
        const y = CY + 20 * MM + k * 4.6 * MM;
        s += `<ellipse cx="${CX}" cy="${y}" rx="${1.1 * MM}" ry="${0.75 * MM}" fill="#0b0b0c" stroke="rgba(255,255,255,.12)" stroke-width="1"/>`;
      }
      s += `<path d="${outline()}" fill="none" stroke="rgba(255,255,255,.10)" stroke-width="2"/>`;
    }
    if (c.strap === 'leather') {
      // stitching
      const pts = side => { const a = []; for (let i = 0; i <= 20; i++) { const y = y0 + len * i / 20; a.push([CX + side * (taperAt(y) / 2 - 0.9 * MM), y]); } return a; };
      for (const sd of [-1, 1]) s += `<polyline points="${pts(sd).map(p => p.map(f).join(',')).join(' ')}" fill="none" stroke="${c.stitch}" stroke-width="1.6" stroke-dasharray="5 4" opacity=".9"/>`;
      if (!top) for (let k = 0; k < 4; k++) {
        const y = CY + 21 * MM + k * 4.4 * MM;
        s += `<circle cx="${CX}" cy="${y}" r="${0.75 * MM}" fill="rgba(0,0,0,.35)"/>`;
      }
      // keeper
      const ky = top ? 0.18 * H : H - 0.12 * H;
      s += `<rect x="${CX - taperAt(ky) / 2 - 3}" y="${ky}" width="${taperAt(ky) + 6}" height="${3.2 * MM}" rx="6" fill="${c.strapColor}" stroke="rgba(0,0,0,.18)" stroke-width="2"/>`;
    }
    return s;
  }
  // metal bracelets
  const rowH = (c.strap === 'oyster' ? 7.2 : c.strap === 'integrated' ? 5.2 : 3.8) * MM;
  let y = top ? CY : CY, i = 0;
  const rows = [];
  if (top) { for (let yy = CY; yy > -rowH; yy -= rowH) rows.push(yy - rowH); }
  else { for (let yy = CY; yy < H + rowH; yy += rowH) rows.push(yy); }
  for (const ry of rows) {
    const w = taperAt(ry + rowH / 2), L = CX - w / 2, gap = 2.2;
    if (c.strap === 'oyster' || c.strap === 'integrated') {
      const cw = w * (c.strap === 'integrated' ? 0.52 : 0.34);
      s += `<rect x="${L}" y="${ry}" width="${(w - cw) / 2 - gap}" height="${rowH - gap}" rx="3" fill="url(#${id}-brush)"/>`;
      s += `<rect x="${CX + cw / 2 + gap}" y="${ry}" width="${(w - cw) / 2 - gap}" height="${rowH - gap}" rx="3" fill="url(#${id}-brush)"/>`;
      s += `<rect x="${CX - cw / 2}" y="${ry + rowH * 0.1}" width="${cw}" height="${rowH * 0.8 - gap}" rx="4" fill="url(#${id}-pol)"/>`;
      s += `<rect x="${CX - cw / 2}" y="${ry + rowH * 0.1}" width="${cw}" height="${rowH * 0.8 - gap}" rx="4" fill="url(#${id}-gloss)" opacity=".7"/>`;
    } else { // jubilee
      const ow = w * 0.27, cw = (w - 2 * ow - 4 * gap) / 3;
      s += `<rect x="${L}" y="${ry}" width="${ow}" height="${rowH - gap}" rx="3" fill="url(#${id}-brush)"/>`;
      s += `<rect x="${CX + w / 2 - ow}" y="${ry}" width="${ow}" height="${rowH - gap}" rx="3" fill="url(#${id}-brush)"/>`;
      const off = (i % 2) * rowH * 0.5;
      for (let k = 0; k < 3; k++) {
        const x = L + ow + gap + k * (cw + gap);
        const yy = ry + (k === 1 ? off : (rowH * 0.5 - off)) - rowH * 0.25;
        s += `<rect x="${x}" y="${yy}" width="${cw}" height="${rowH * 0.9}" rx="${cw / 2.2}" fill="url(#${id}-pol)"/>`;
      }
    }
    i++;
  }
  return `<g clip-path="url(#${id}-${top ? 'topclip' : 'botclip'})">${s}</g>`;
}

/* ---------------- dial ---------------- */
function dialTexture(c, id, r) {
  let s = `<circle cx="${CX}" cy="${CY}" r="${r}" fill="${c.dialColor}"/>`;
  if (c.dialFinish === 'sunburst') {
    RNG = 7;
    let w = '';
    for (let a = 0; a < 360; a += 0.75) {
      const b = Math.cos(rad(2 * (a - 315)));
      const k = 0.65 + 0.35 * rnd();
      if (b > 0) w += `<path d="M${CX},${CY}L${P(r, a).map(f)}L${P(r, a + 0.75).map(f)}Z" fill="#fff" opacity="${f(b * b * 0.30 * k)}"/>`;
      else w += `<path d="M${CX},${CY}L${P(r, a).map(f)}L${P(r, a + 0.75).map(f)}Z" fill="#000" opacity="${f(b * b * 0.22 * k)}"/>`;
    }
    s += w;
  }
  if (c.dialFinish === 'wave') {
    RNG = 11;
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" fill="url(#${id}-dialgloss)"/>`;
    for (let y = -r; y < r; y += 0.75 * MM) {
      const A = (0.25 + 0.55 * rnd()) * MM, k = (0.9 + 0.8 * rnd()) / MM, ph = rnd() * 6.28;
      let d = '';
      for (let x = -r; x <= r; x += 4) d += (x === -r ? 'M' : 'L') + f(CX + x) + ',' + f(CY + y + A * Math.sin(k * x + ph) + 0.4 * A * Math.sin(2.3 * k * x + ph * 1.7));
      s += `<path d="${d}" fill="none" stroke="#fff" stroke-opacity="${f(0.05 + 0.10 * rnd())}" stroke-width="${f(1.4 + 2.2 * rnd())}"/>`;
      s += `<path d="${d}" transform="translate(0,3)" fill="none" stroke="#000" stroke-opacity="${f(0.08 + 0.12 * rnd())}" stroke-width="${f(1.2 + 1.6 * rnd())}"/>`;
    }
  }
  if (c.dialFinish === 'cocktail') {
    for (let k = 0; k < 36; k++) {
      const a1 = k * 10, lit = 0.5 + 0.5 * Math.cos(rad(2 * (a1 + 5 - 315)));
      s += `<path d="M${CX},${CY}L${P(r, a1).map(f)}L${P(r, a1 + 5).map(f)}Z" fill="#fff" opacity="${f(0.05 + 0.28 * lit)}"/>`;
      s += `<path d="M${CX},${CY}L${P(r, a1 + 5).map(f)}L${P(r, a1 + 10).map(f)}Z" fill="#000" opacity="${f(0.04 + 0.16 * (1 - lit))}"/>`;
    }
    for (let rr = r * 0.12; rr < r; rr += 0.55 * MM) s += `<circle cx="${CX}" cy="${CY}" r="${f(rr)}" fill="none" stroke="#fff" stroke-opacity=".06" stroke-width="1"/>`;
  }
  if (c.dialFinish === 'tapisserie') {
    s += `<rect x="${CX - r}" y="${CY - r}" width="${2 * r}" height="${2 * r}" fill="url(#${id}-tap)"/>`;
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" fill="url(#${id}-dialgloss)"/>`;
  }
  if (c.dialFinish === 'gloss') {
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" fill="url(#${id}-dialgloss)"/>`;
  }
  if (c.dialFinish === 'mop') {
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" filter="url(#${id}-mop)" opacity=".55"/>`;
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" fill="url(#${id}-dialgloss)" opacity=".6"/>`;
  }
  if (c.dialFinish === 'matte') {
    s += `<circle cx="${CX}" cy="${CY}" r="${r}" filter="url(#${id}-grain)" opacity=".12"/>`;
  }
  s += `<circle cx="${CX}" cy="${CY}" r="${r}" fill="url(#${id}-vign)"/>`;
  return s;
}

function lumeMark(shape, x, y, a, sz, c, id) {
  const st = c.markEdge, lw = c.markEdgeW || 2;
  const lum = c.lume;
  const tr = `transform="translate(${f(x)},${f(y)}) rotate(${a})"`;
  if (shape === 'dot') return `<g ${tr}><circle r="${sz}" fill="${lum}" stroke="${st}" stroke-width="${lw}"/><circle r="${sz}" fill="url(#${id}-markshine)"/></g>`;
  if (shape === 'bar') return `<g ${tr}><rect x="${-sz * 0.55}" y="${-sz * 1.6}" width="${sz * 1.1}" height="${sz * 3.2}" rx="2" fill="${lum}" stroke="${st}" stroke-width="${lw}"/><rect x="${-sz * 0.55}" y="${-sz * 1.6}" width="${sz * 1.1}" height="${sz * 3.2}" rx="2" fill="url(#${id}-markshine)"/></g>`;
  if (shape === 'tri') return `<g ${tr}><path d="M${-sz * 1.25},${-sz * 1.2} L${sz * 1.25},${-sz * 1.2} L0,${sz * 1.3}Z" fill="${lum}" stroke="${st}" stroke-width="${lw}" stroke-linejoin="round"/></g>`;
  if (shape === 'rect') return `<g ${tr}><rect x="${-sz * 0.6}" y="${-sz * 1.9}" width="${sz * 1.2}" height="${sz * 3.8}" rx="1.5" fill="${lum}" stroke="${st}" stroke-width="${lw}"/></g>`;
  if (shape === 'rect2') return `<g ${tr}><rect x="${-sz * 1.55}" y="${-sz * 1.9}" width="${sz * 1.1}" height="${sz * 3.8}" rx="1.5" fill="${lum}" stroke="${st}" stroke-width="${lw}"/><rect x="${sz * 0.45}" y="${-sz * 1.9}" width="${sz * 1.1}" height="${sz * 3.8}" rx="1.5" fill="${lum}" stroke="${st}" stroke-width="${lw}"/></g>`;
  if (shape === 'baton') return `<g ${tr}><rect x="${-sz * 0.42}" y="${-sz * 2.1}" width="${sz * 0.84}" height="${sz * 4.2}" rx="1.2" fill="url(#${id}-mpol)" stroke="rgba(0,0,0,.25)" stroke-width="0.8"/></g>`;
  if (shape === 'baton2') return `<g ${tr}><rect x="${-sz * 1.05}" y="${-sz * 2.1}" width="${sz * 0.8}" height="${sz * 4.2}" rx="1.2" fill="url(#${id}-mpol)" stroke="rgba(0,0,0,.25)" stroke-width="0.8"/><rect x="${sz * 0.25}" y="${-sz * 2.1}" width="${sz * 0.8}" height="${sz * 4.2}" rx="1.2" fill="url(#${id}-mpol)" stroke="rgba(0,0,0,.25)" stroke-width="0.8"/></g>`;
  return '';
}

function indices(c, id, r) {
  let s = '';
  // minute track
  if (c.minuteTrack) {
    for (let m = 0; m < 60; m++) {
      const a = m * 6, five = m % 5 === 0;
      const [x1, y1] = P(r - 0.35 * MM, a), [x2, y2] = P(r - (five ? 1.25 : 0.95) * MM, a);
      s += `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="${c.print}" stroke-width="${five ? 1.6 : 1}" opacity=".9"/>`;
    }
  }
  const rr = r - (c.markInset || 2.9) * MM, sz = (c.markSize || 1.25) * MM;
  for (let h = 0; h < 12; h++) {
    const a = h * 30;
    if (h === 3 && c.date) continue;
    const [x, y] = P(rr, a);
    let shape = c.marks.other;
    if (h === 0) shape = c.marks.twelve;
    else if (h === 6 || h === 9 || h === 3) shape = c.marks.quarter || shape;
    if (c.marks.style === 'explorer' && (h === 3 || h === 6 || h === 9)) {
      const [tx, ty] = P(r - 3.1 * MM, a);
      s += `<text x="${f(tx)}" y="${f(ty)}" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="800" font-size="${3.3 * MM}" fill="${c.lume}" stroke="${c.markEdge}" stroke-width="1.6" paint-order="stroke">${h}</text>`;
      continue;
    }
    if (c.marks.style === 'arabic') {
      const [tx, ty] = P(r - 3.2 * MM, a);
      s += `<text x="${f(tx)}" y="${f(ty)}" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="700" font-size="${2.8 * MM}" fill="${c.print}">${h === 0 ? 12 : h}</text>`;
      if (c.inner24) { const [ux, uy] = P(r - 6.9 * MM, a); s += `<text x="${f(ux)}" y="${f(uy)}" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="500" font-size="${1.2 * MM}" fill="${c.print}" opacity=".85">${h === 0 ? 24 : h + 12}</text>`; }
      continue;
    }
    if (c.marks.style === 'roman') {
      const R = ['XII', 'I', 'II', 'III', 'IIII', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI'][h];
      const [tx, ty] = P(r - 3.0 * MM, a);
      const rot = (h > 3 && h < 9) ? a + 180 : a;
      s += `<text x="${f(tx)}" y="${f(ty)}" transform="rotate(${rot} ${f(tx)} ${f(ty)})" text-anchor="middle" dominant-baseline="central" font-family="DejaVu Serif, serif" font-size="${2.4 * MM}" fill="${c.print}" letter-spacing="-1">${R}</text>`;
      continue;
    }
    s += lumeMark(shape, x, y, a, sz, c, id);
  }
  // date window
  if (c.date) {
    const [dx, dy] = P(r - 3.2 * MM, 90);
    const w = 3.3 * MM, h = 2.7 * MM;
    s += `<rect x="${dx - w / 2}" y="${dy - h / 2}" width="${w}" height="${h}" rx="2" fill="${c.dateBg || '#fff'}" stroke="${c.markEdge}" stroke-width="2.2"/>`;
    s += `<rect x="${dx - w / 2}" y="${dy - h / 2}" width="${w}" height="${h * 0.35}" rx="2" fill="rgba(0,0,0,.10)"/>`;
    s += `<text x="${dx}" y="${dy + 0.75}" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="600" font-size="${2.0 * MM}" fill="${c.dateFg || '#111'}">31</text>`;
    if (c.cyclops) {
      const cw = w * 1.75, ch = h * 1.75;
      s += `<rect x="${dx - cw / 2}" y="${dy - ch / 2}" width="${cw}" height="${ch}" rx="${0.9 * MM}" fill="#fff" stroke="rgba(160,190,220,.9)" stroke-width="2.4"/>`;
      s += `<text x="${dx}" y="${dy + 1}" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="700" font-size="${3.4 * MM}" fill="#111">31</text>`;
      s += `<rect x="${dx - cw / 2 + 2}" y="${dy - ch / 2 + 2}" width="${cw - 4}" height="${ch * 0.42}" rx="${0.7 * MM}" fill="#fff" opacity=".35"/>`;
    }
  }
  return s;
}

/* ---------------- hands ---------------- */
function handPath(type, L, w) {
  // returns [outline, lumeInner] in local coords (pointing up)
  switch (type) {
    case 'sword': return [
      `M${-w / 2},${2.2 * MM} L${-w / 2},${-L * 0.72} L0,${-L} L${w / 2},${-L * 0.72} L${w / 2},${2.2 * MM} Z`,
      `M${-w / 2 + 2.6},${-L * 0.2} L${-w / 2 + 2.6},${-L * 0.70} L0,${-L + 6} L${w / 2 - 2.6},${-L * 0.70} L${w / 2 - 2.6},${-L * 0.2} Z`];
    case 'pencil': return [
      `M${-w / 2},${2.2 * MM} L${-w / 2},${-L * 0.88} L0,${-L} L${w / 2},${-L * 0.88} L${w / 2},${2.2 * MM} Z`,
      `M${-w / 2 + 2.4},${-L * 0.22} L${-w / 2 + 2.4},${-L * 0.86} L0,${-L + 5} L${w / 2 - 2.4},${-L * 0.86} L${w / 2 - 2.4},${-L * 0.22} Z`];
    case 'baton': return [
      `M${-w / 2},${1.8 * MM} L${-w / 2},${-L + w / 2} L0,${-L} L${w / 2},${-L + w / 2} L${w / 2},${1.8 * MM} Z`, null];
    case 'lumebaton': return [
      `M${-w / 2},${2 * MM} L${-w / 2},${-L} L${w / 2},${-L} L${w / 2},${2 * MM} Z`,
      `M${-w / 2 + 2.3},${-L * 0.25} L${-w / 2 + 2.3},${-L + 2.3} L${w / 2 - 2.3},${-L + 2.3} L${w / 2 - 2.3},${-L * 0.25} Z`];
    case 'arrow': return [
      `M${-w * 0.28},${2 * MM} L${-w * 0.28},${-L * 0.62} L${-w * 0.62},${-L * 0.62} L0,${-L} L${w * 0.62},${-L * 0.62} L${w * 0.28},${-L * 0.62} L${w * 0.28},${2 * MM} Z`,
      `M${-w * 0.62 + 4},${-L * 0.65} L0,${-L + 5} L${w * 0.62 - 4},${-L * 0.65} Z`];
    case 'dauphine': return [
      `M0,${1.6 * MM} L${-w / 2},${-L * 0.28} L0,${-L} L${w / 2},${-L * 0.28} Z`, null];
    case 'snowflake': {
      const cy = -L * 0.64, q = w * 0.62, sw = w * 0.2;
      return [
        `M${-sw},${2 * MM} L${-sw},${cy + q} L${-q},${cy} L0,${cy - q} L${q},${cy} L${sw},${cy + q} L${sw},${2 * MM} Z M${-sw * 1.4},${cy - q + 2} L0,${-L} L${sw * 1.4},${cy - q + 2} Z`,
        `M${-q + 3},${cy} L0,${cy - q + 3} L${q - 3},${cy} L0,${cy + q - 3} Z`];
    }
    case 'merc': {
      const cy = -L * 0.70, cr = 1.55 * MM, sw = w * 0.42;
      return [
        `M${-sw},${2 * MM} L${-sw},${cy + cr - 1} A${cr},${cr} 0 1,1 ${sw},${cy + cr - 1} L${sw},${2 * MM} Z M0,${cy - cr + 1} L${-w * 0.42},${cy - cr + 2} L0,${-L} L${w * 0.42},${cy - cr + 2} Z`,
        `M${f(-cr + 2.6)},${cy} a${cr - 2.6},${cr - 2.6} 0 1,0 ${f(2 * (cr - 2.6))},0 a${cr - 2.6},${cr - 2.6} 0 1,0 ${f(-2 * (cr - 2.6))},0`];
    }
  }
}

function hands(c, id, r) {
  const t = { h: (10 + 9 / 60) * 30, m: 9 * 6 + 3.6, s: 36 * 6 };
  const hs = c.hands;
  const one = (type, L, w, ang, isH) => {
    const [o, l] = handPath(type, L, w);
    const fill = `url(#${id}-handmetal)`;
    let g = `<path d="${o}" fill="${fill}" stroke="${hs.edge}" stroke-width="0.9"/>`;
    if (type === 'dauphine') g += `<path d="M0,${1.6 * MM} L0,${-L} L${w / 2},${-L * 0.28} Z" fill="#000" opacity=".22"/>`;
    else if (type === 'baton' || !l) g += `<path d="M0,${1.8 * MM} L0,${-L}" stroke="rgba(255,255,255,.55)" stroke-width="${w * 0.35}"/><path d="${o}" fill="url(#${id}-facet)" />`;
    if (l && hs.lume !== false) g += `<path d="${l}" fill="${c.lume}"/>`;
    if (type === 'merc' && hs.lume !== false) g += `<path d="M0,${-L * 0.70} L0,${-L * 0.70 - 1.55 * MM + 2.6} M0,${-L * 0.70} L${f(-1.2 * MM)},${f(-L * 0.70 + 0.8 * MM)} M0,${-L * 0.70} L${f(1.2 * MM)},${f(-L * 0.70 + 0.8 * MM)}" stroke="${hs.edge === 'none' ? '#c9cdd2' : '#d8dce0'}" stroke-width="2.6"/>`;
    return `<g transform="translate(${CX + 2.4},${CY + 3.4}) rotate(${ang})" filter="url(#${id}-hshadow)" opacity=".45"><path d="${o}" fill="#000"/></g>
            <g transform="translate(${CX},${CY}) rotate(${ang})">${g}</g>`;
  };
  let s = '';
  s += one(hs.hour, r * hs.hl, hs.hw * MM, t.h, true);
  s += one(hs.minute, r * hs.ml, hs.mw * MM, t.m, false);
  // seconds
  const sL = r * 0.95, tail = 3 * MM;
  let sec = `<path d="M0,${tail} L0,${-sL}" stroke="${hs.secColor}" stroke-width="${0.32 * MM}" stroke-linecap="round"/>`;
  if (hs.sec === 'lolli') sec += `<circle cx="0" cy="${-sL * 0.74}" r="${0.95 * MM}" fill="${c.lume}" stroke="${hs.secColor}" stroke-width="2.4"/>`;
  if (hs.sec === 'tip') sec += `<path d="M0,${-sL * 0.70} L0,${-sL}" stroke="${hs.secTip}" stroke-width="${0.32 * MM}"/>`;
  sec += `<rect x="${-0.55 * MM}" y="0" width="${1.1 * MM}" height="${tail}" rx="3" fill="${hs.secColor}"/>`;
  s += `<g transform="translate(${CX + 2.6},${CY + 3.8}) rotate(${t.s})" filter="url(#${id}-hshadow)" opacity=".35"><path d="M0,${tail} L0,${-sL}" stroke="#000" stroke-width="${0.32 * MM}"/></g>`;
  s += `<g transform="translate(${CX},${CY}) rotate(${t.s})">${sec}</g>`;
  s += `<circle cx="${CX}" cy="${CY}" r="${1.05 * MM}" fill="url(#${id}-handmetal)" stroke="${hs.edge}" stroke-width="0.8"/>`;
  s += `<circle cx="${CX}" cy="${CY}" r="${0.45 * MM}" fill="${hs.secColor}"/>`;
  return s;
}

/* ---------------- bezel ---------------- */
function bezel(c, id, Rc) {
  const b = c.bezel, ro = b.outer * MM, ri = b.inner * MM;
  let s = '';
  if (b.type === 'diver') {
    // coin edge
    s += ring(Rc - 0.15 * MM, ro, `fill="url(#${id}-ring)"`);
    RNG = 3;
    for (let k = 0; k < 120; k++) {
      const a = k * 3;
      const [x1, y1] = P(Rc - 0.2 * MM, a), [x2, y2] = P(ro + 0.25 * MM, a);
      s += `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="rgba(0,0,0,.28)" stroke-width="1.4"/>`;
    }
    if (b.color2) {
      for (const [a1, a2, col] of [[-90, 0, b.color], [0, 90, b.color], [90, 180, b.color2], [180, 270, b.color2]]) s += `<path d="${wedge(ro, ri, a1, a2)}" fill="${col}"/>`;
    } else s += ring(ro, ri, `fill="${b.color}"`);
    if (b.ceramic) s += ring(ro, ri, `fill="url(#${id}-ceramic)"`);
    s += ring(ro, ri, `fill="url(#${id}-insertshade)"`);
    const mid = (ro + ri) / 2, ink = b.ink;
    for (let m = 0; m < 60; m++) {
      const a = m * 6;
      if (m === 0) continue;
      if (m % 10 === 0) {
        const [tx, ty] = P(mid, a);
        s += `<text x="${f(tx)}" y="${f(ty)}" transform="rotate(${a} ${f(tx)} ${f(ty)})" text-anchor="middle" dominant-baseline="central" font-family="Inter, sans-serif" font-weight="600" font-size="${(b.numSize || 2.7) * MM}" fill="${ink}">${m}</text>`;
      } else if (m % 5 === 0) {
        const [x1, y1] = P(mid + 0.9 * MM, a), [x2, y2] = P(mid - 0.9 * MM, a);
        s += `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="${ink}" stroke-width="${0.9 * MM}"/>`;
      } else if (m < 15 || b.allMinutes) {
        const [x1, y1] = P(mid + 0.55 * MM, a), [x2, y2] = P(mid - 0.55 * MM, a);
        s += `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="${ink}" stroke-width="1.6"/>`;
      }
    }
    // 12 o'clock triangle + pip
    const [px, py] = P(mid, 0);
    s += `<path d="M${px - 1.5 * MM},${py - 1.15 * MM} L${px + 1.5 * MM},${py - 1.15 * MM} L${px},${py + 1.25 * MM}Z" fill="${ink}"/>`;
    s += `<circle cx="${px}" cy="${py - 0.2 * MM}" r="${0.62 * MM}" fill="${c.lume}" stroke="#bfc4c9" stroke-width="1.5"/>`;
  } else if (b.type === 'octagon') {
    s += `<path fill-rule="evenodd" d="${polyPath(ro, 8, 22.5)} M${CX - ri},${CY} a${ri},${ri} 0 1,0 ${2 * ri},0 a${ri},${ri} 0 1,0 ${-2 * ri},0Z" fill="url(#${id}-lin)" stroke="rgba(0,0,0,.3)" stroke-width="1.2"/>`;
    s += `<path fill-rule="evenodd" d="${polyPath(ro - 0.6 * MM, 8, 22.5)} M${CX - ri - 0.6 * MM},${CY} a${ri + 0.6 * MM},${ri + 0.6 * MM} 0 1,0 ${2 * (ri + 0.6 * MM)},0 a${ri + 0.6 * MM},${ri + 0.6 * MM} 0 1,0 ${-2 * (ri + 0.6 * MM)},0Z" fill="url(#${id}-brush)" opacity=".55"/>`;
    for (let k = 0; k < 8; k++) { const [x, y] = P((ro + ri) / 2 + 0.3 * MM, 22.5 + k * 45); s += `<circle cx="${f(x)}" cy="${f(y)}" r="${0.75 * MM}" fill="url(#${id}-lin)" stroke="rgba(0,0,0,.4)" stroke-width="1"/><path d="${polyPath(0.42 * MM, 6, 10 + k * 7).replace(/([ML])([\d.]+),([\d.]+)/g, (m0, c0, xx, yy) => c0 + f(+xx - CX + x) + ',' + f(+yy - CY + y))}" fill="#6b7178" opacity=".8"/>`; }
  } else if (b.type === 'fluted') {
    const N = 64;
    for (let k = 0; k < N; k++) {
      const a1 = k * 360 / N, am = a1 + 180 / N, a2 = a1 + 360 / N;
      const lit = 0.5 + 0.5 * Math.cos(rad(am - 315));
      s += `<path d="${wedge(ro, ri, a1, am)}" fill="url(#${id}-lin)"/>`;
      s += `<path d="${wedge(ro, ri, a1, am)}" fill="#fff" opacity="${f(0.15 + 0.5 * lit)}"/>`;
      s += `<path d="${wedge(ro, ri, am, a2)}" fill="url(#${id}-lin)"/>`;
      s += `<path d="${wedge(ro, ri, am, a2)}" fill="#000" opacity="${f(0.10 + 0.32 * (1 - lit))}"/>`;
    }
    s += ring(Rc, ro, `fill="url(#${id}-ring)"`);
  } else { // smooth polished
    s += ring(Rc, ri, `fill="url(#${id}-ring)"`);
  }
  return s;
}

/* ---------------- full watch ---------------- */
function watchSVG(c) {
  const id = c.id;
  const Rc = c.caseD / 2 * MM;
  const lugW = c.lug * MM, l2l = c.l2l * MM;
  const crystalR = c.bezel.inner * MM;
  const dialR = Math.min(14.25 * MM, crystalR - (c.chapterW || 0.7) * MM);
  const dialPrint = c.print;

  const defs = `
  ${metalDefs(id, c.metal)}
  ${metalDefs(id + 'm', c.markMetal || c.metal).replace(new RegExp(`${id}m-pol`, 'g'), `${id}-mpol`)}
  <linearGradient id="${id}-handmetal" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="${METAL[c.handMetal || c.metal][3]}"/><stop offset=".5" stop-color="${METAL[c.handMetal || c.metal][0]}"/><stop offset=".5" stop-color="${METAL[c.handMetal || c.metal][2]}"/><stop offset="1" stop-color="${METAL[c.handMetal || c.metal][1]}"/></linearGradient>
  <linearGradient id="${id}-facet" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".0"/><stop offset=".5" stop-color="#fff" stop-opacity=".25"/><stop offset=".5" stop-color="#000" stop-opacity=".12"/><stop offset="1" stop-color="#000" stop-opacity=".0"/></linearGradient>
  <linearGradient id="${id}-gloss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <radialGradient id="${id}-vign" cx=".5" cy=".5" r=".5"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="${c.vign ?? .28}"/></radialGradient>
  <radialGradient id="${id}-dialgloss" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".6" stop-color="#fff" stop-opacity="0"/></radialGradient>
  <radialGradient id="${id}-markshine" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".6" stop-color="#fff" stop-opacity="0"/></radialGradient>
  <radialGradient id="${id}-insertshade" cx=".5" cy=".5" r=".5"><stop offset="${f(crystalR / (c.bezel.outer * MM))}" stop-color="#000" stop-opacity=".35"/><stop offset="${f((crystalR / (c.bezel.outer * MM) + 1) / 2)}" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".25"/></radialGradient>
  <linearGradient id="${id}-ceramic" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".28"/><stop offset=".3" stop-color="#fff" stop-opacity="0"/><stop offset=".75" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".12"/></linearGradient>
  <linearGradient id="${id}-strapshade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset=".12" stop-color="#fff" stop-opacity=".10"/><stop offset=".5" stop-color="#fff" stop-opacity=".04"/><stop offset=".88" stop-color="#000" stop-opacity=".05"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></linearGradient>
  <pattern id="${id}-weave" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="none"/><path d="M0,7 L7,0 L14,7 L7,14Z" fill="rgba(255,255,255,.07)"/><circle cx="7" cy="7" r="2.2" fill="rgba(0,0,0,.55)"/></pattern>
  <filter id="${id}-mop" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.012 0.02" numOctaves="3" seed="${c.seed || 4}"/><feColorMatrix type="matrix" values="1.4 0 0 0 0.05  0 1.2 0.3 0 0.05  0.2 0 1.5 0 0.1  0 0 0 0 1"/></filter>
  <filter id="${id}-brushV" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.85 0.006" numOctaves="2" seed="3"/><feColorMatrix type="saturate" values="0"/></filter>
  <filter id="${id}-brushH" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.85" numOctaves="2" seed="5"/><feColorMatrix type="saturate" values="0"/></filter>
  <radialGradient id="${id}-ar" cx=".72" cy=".78" r=".6"><stop offset="0" stop-color="#7aa7ff" stop-opacity=".10"/><stop offset="1" stop-color="#7aa7ff" stop-opacity="0"/></radialGradient>
  <radialGradient id="${id}-ground" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#000" stop-opacity=".22"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
  <pattern id="${id}-tap" width="${0.95 * MM}" height="${0.95 * MM}" patternUnits="userSpaceOnUse"><rect width="${0.95 * MM}" height="${0.95 * MM}" fill="#000" opacity=".28"/><rect x="1.4" y="1.4" width="${0.95 * MM - 2.8}" height="${0.95 * MM - 2.8}" rx="1" fill="#fff" opacity=".10"/><rect x="1.4" y="1.4" width="${0.95 * MM - 2.8}" height="2" fill="#fff" opacity=".18"/></pattern>
  <filter id="${id}-grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2"/><feColorMatrix type="saturate" values="0"/></filter>
  <filter id="${id}-hshadow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>
  <filter id="${id}-drop" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="6" dy="12" stdDeviation="14" flood-color="#000" flood-opacity=".35"/></filter>
  <filter id="${id}-soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="18"/></filter>
  <radialGradient id="${id}-bg" cx=".5" cy=".45" r=".75"><stop offset="0" stop-color="${c.bg[0]}"/><stop offset="1" stop-color="${c.bg[1]}"/></radialGradient>
  <linearGradient id="${id}-crys" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="${c.domed ? .38 : .26}"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="${id}-fadeT" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.bg[1]}" stop-opacity="1"/><stop offset="1" stop-color="${c.bg[1]}" stop-opacity="0"/></linearGradient>
  <linearGradient id="${id}-fadeB" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${c.bg[1]}" stop-opacity="1"/><stop offset="1" stop-color="${c.bg[1]}" stop-opacity="0"/></linearGradient>
  <clipPath id="${id}-dialclip"><circle cx="${CX}" cy="${CY}" r="${dialR}"/></clipPath>
  <clipPath id="${id}-crysclip"><circle cx="${CX}" cy="${CY}" r="${crystalR}"/></clipPath>
  <clipPath id="${id}-topclip"><rect x="0" y="0" width="${W}" height="${CY}"/></clipPath>
  <clipPath id="${id}-botclip"><rect x="0" y="${CY}" width="${W}" height="${H - CY}"/></clipPath>`;

  // lugs
  let lugs = '', lugD = '';
  if (!c.noLugs) for (const sy of [-1, 1]) for (const sx of [-1, 1]) {
    const xi = CX + sx * lugW / 2, xt = CX + sx * (lugW / 2 + 2.5 * MM);
    const yTip = CY + sy * l2l / 2, yBase = CY + sy * Rc * 0.45;
    const xb = CX + sx * Rc * 0.89;
    const ym = CY + sy * (Rc * 0.45 + (l2l / 2 - Rc * 0.45) * 0.55);
    const xm = CX + sx * (lugW / 2 + 2.5 * MM + (Rc * 0.89 - lugW / 2 - 2.5 * MM) * 0.25);
    const ld = `M${f(xi)},${f(yBase)} L${f(xi)},${f(yTip - sy * 0.6 * MM)} Q${f(xi)},${f(yTip)} ${f(xi + sx * 0.8 * MM)},${f(yTip)} L${f(xt - sx * 0.6 * MM)},${f(yTip)} Q${f(xt)},${f(yTip)} ${f(xt)},${f(yTip - sy * 0.8 * MM)} Q${f(xm)},${f(ym)} ${f(xb)},${f(yBase)} Z`;
    lugD += `<path d="${ld}"/>`;
    lugs += `<path d="M${f(xi)},${f(yBase)} L${f(xi)},${f(yTip - sy * 0.6 * MM)} Q${f(xi)},${f(yTip)} ${f(xi + sx * 0.8 * MM)},${f(yTip)} L${f(xt - sx * 0.6 * MM)},${f(yTip)} Q${f(xt)},${f(yTip)} ${f(xt)},${f(yTip - sy * 0.8 * MM)} Q${f(xm)},${f(ym)} ${f(xb)},${f(yBase)} Z" fill="url(#${id}-h)" stroke="rgba(0,0,0,.28)" stroke-width="1"/>`;
    lugs += `<path d="M${f(xt - sx * 0.35 * MM)},${f(yTip - sy * 0.9 * MM)} Q${f(xm - sx * 0.4 * MM)},${f(ym)} ${f(xb - sx * 0.5 * MM)},${f(yBase)}" fill="none" stroke="rgba(255,255,255,.8)" stroke-width="2.2"/>`;
  }
  // crown
  const crW = c.crown[0] * MM, crH = c.crown[1] * MM, crX = CX + Rc - 1.2 * MM;
  let crown = `<rect x="${crX}" y="${CY - crH / 2}" width="${crW + 1.2 * MM}" height="${crH}" rx="${0.8 * MM}" fill="url(#${id}-lin)" stroke="rgba(0,0,0,.35)" stroke-width="1"/>`;
  for (let k = 1; k < 12; k++) crown += `<line x1="${crX + 1.6 * MM + k * (crW - 0.6 * MM) / 12}" y1="${CY - crH / 2 + 1.5}" x2="${crX + 1.6 * MM + k * (crW - 0.6 * MM) / 12}" y2="${CY + crH / 2 - 1.5}" stroke="rgba(0,0,0,.25)" stroke-width="1.2"/>`;
  if (c.crownGuard) {
    crown = `<path d="M${CX + Rc * 0.86},${CY - crH / 2 - 2.6 * MM} Q${CX + Rc + 1.6 * MM},${CY - crH / 2 - 0.8 * MM} ${CX + Rc + 1.5 * MM},${CY - crH / 2 + 1}
      L${CX + Rc + 1.5 * MM},${CY + crH / 2 - 1} Q${CX + Rc + 1.6 * MM},${CY + crH / 2 + 0.8 * MM} ${CX + Rc * 0.86},${CY + crH / 2 + 2.6 * MM}Z" fill="url(#${id}-lin)" stroke="rgba(0,0,0,.25)"/>` + crown;
  }

  // chapter ring / rehaut
  let chapter = ring(crystalR, dialR - 1, `fill="${c.chapterColor}"`);
  if (c.chapterTicks) for (let m = 0; m < 60; m++) {
    const a = m * 6, five = m % 5 === 0;
    const [x1, y1] = P(crystalR - 0.15 * MM, a), [x2, y2] = P(crystalR - (five ? 1.0 : 0.6) * MM, a);
    s_ = `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" stroke="${c.chapterTicks}" stroke-width="${five ? 2.2 : 1.2}"/>`;
    chapter += s_;
  }
  chapter += ring(crystalR, dialR - 1, `fill="url(#${id}-insertshade)" opacity=".7"`);

  const body = `
  <rect width="${W}" height="${H}" fill="url(#${id}-bg)"/>
  <g>${strap(c, id, true)}${strap(c, id, false)}</g>
  <rect x="0" y="0" width="${W}" height="70" fill="url(#${id}-fadeT)"/>
  <rect x="0" y="${H - 70}" width="${W}" height="70" fill="url(#${id}-fadeB)"/>
  <ellipse cx="${CX + 10}" cy="${CY + 22}" rx="${Rc * 1.25}" ry="${l2l * 0.62}" fill="url(#${id}-ground)"/>
  <g filter="url(#${id}-drop)">
    ${lugs}
    ${crown}
    ${c.shape === 'cushion' ? `<path d="${cushionPath(Rc, 3.2)}" fill="url(#${id}-lin)" stroke="rgba(0,0,0,.25)" stroke-width="1"/><path d="${cushionPath(Rc - 1.2 * MM, 3.2)}" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="2"/>` : `<circle cx="${CX}" cy="${CY}" r="${Rc}" fill="url(#${id}-lin)"/>`}
  </g>
  <clipPath id="${id}-caseclip">${lugD}${c.shape === 'cushion' ? `<path d="${cushionPath(Rc, 3.2)}"/>` : `<circle cx="${CX}" cy="${CY}" r="${Rc}"/>`}</clipPath>
  <g clip-path="url(#${id}-caseclip)" style="mix-blend-mode:multiply" opacity=".22"><rect width="${W}" height="${H}" filter="url(#${id}-brushV)"/></g>
  ${c.shape === 'cushion' ? '' : ring(Rc, Rc - 0.6 * MM, `fill="url(#${id}-ring)"`)}
  ${bezel(c, id, c.shape === 'cushion' ? c.bezel.outer * MM + 0.9 * MM : Rc)}
  ${ring(crystalR + 1.5, crystalR - 0.5, 'fill="rgba(0,0,0,.45)"')}
  <g>${chapter}</g>
  <g clip-path="url(#${id}-dialclip)">${dialTexture(c, id, dialR)}</g>
  ${indices(c, id, dialR)}
  ${c.logo ? `<text x="${CX}" y="${CY - dialR * 0.40}" text-anchor="middle" font-family="DejaVu Serif, serif" font-weight="700" font-size="${(c.logoSize || 2.6) * MM}" fill="${dialPrint}" letter-spacing="1">${c.logo}</text>` : ''}
  ${c.logo2 ? `<text x="${CX}" y="${CY - dialR * 0.40 + 2.2 * MM}" text-anchor="middle" font-family="DejaVu Serif, serif" font-style="italic" font-size="${1.35 * MM}" fill="${dialPrint}" opacity=".9">${c.logo2}</text>` : ''}
  ${c.text ? `<text x="${CX}" y="${CY + dialR * 0.42}" text-anchor="middle" font-family="Inter, sans-serif" font-size="${1.45 * MM}" letter-spacing="1.5" fill="${dialPrint}" opacity=".85">${c.text}</text>` : ''}
  ${c.text2 ? `<text x="${CX}" y="${CY + dialR * 0.42 + 1.9 * MM}" text-anchor="middle" font-family="Inter, sans-serif" font-size="${1.15 * MM}" letter-spacing="1.2" fill="${c.text2Color || dialPrint}" opacity=".85">${c.text2}</text>` : ''}
  ${hands(c, id, dialR)}
  <g clip-path="url(#${id}-crysclip)">
    <path d="M${CX - crystalR},${CY - crystalR * 0.15} Q${CX - crystalR * 0.2},${CY - crystalR * 0.55} ${CX + crystalR * 0.35},${CY - crystalR} L${CX - crystalR},${CY - crystalR}Z" fill="url(#${id}-crys)"/>
    <circle cx="${CX}" cy="${CY}" r="${crystalR}" fill="url(#${id}-ar)"/>
    <path d="M${f(P(crystalR - 2, 290)[0])},${f(P(crystalR - 2, 290)[1])} A${crystalR - 2},${crystalR - 2} 0 0,1 ${f(P(crystalR - 2, 345)[0])},${f(P(crystalR - 2, 345)[1])}" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="2.4" stroke-linecap="round"/>
    ${c.domed ? `<ellipse cx="${CX + crystalR * 0.45}" cy="${CY + crystalR * 0.55}" rx="${crystalR * 0.35}" ry="${crystalR * 0.08}" transform="rotate(-40 ${CX + crystalR * 0.45} ${CY + crystalR * 0.55})" fill="#fff" opacity=".12"/>` : ''}
  </g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>${defs}</defs>${body}</svg>`;
}
let s_;
if (typeof module !== 'undefined') module.exports = { watchSVG };
