const flakes = Array.from({ length: 160 }, (_, i) => ({ x: (i * 97.13) % 1, y: (i * 61.7) % 1, r: 1.5 + (i % 5), s: 0.6 + (i % 7) / 9, ph: i }));
const houses = Array.from({ length: 14 }, (_, i) => ({ x: i / 14, w: 0.05 + (i * 37 % 5) / 100, h: 0.18 + (i * 53 % 9) / 40 }));
function draw(ctx, t, w, h) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#0B1636"); g.addColorStop(0.7, "#24305E"); g.addColorStop(1, "#3A3F73");
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  const moon = ctx.createRadialGradient(w * .78, h * .2, 0, w * .78, h * .2, h * .22);
  moon.addColorStop(0, "rgba(255,244,214,.95)"); moon.addColorStop(.25, "rgba(255,244,214,.9)"); moon.addColorStop(.27, "rgba(255,244,214,.18)"); moon.addColorStop(1, "rgba(255,244,214,0)");
  ctx.fillStyle = moon; ctx.fillRect(0, 0, w, h);
  for (const b of houses) {
    const bx = b.x * w, bw = b.w * w + 40, bh = b.h * h, by = h - bh;
    ctx.fillStyle = "#141B3D"; ctx.fillRect(bx, by, bw, bh);
    for (let wy = by + 24; wy < h - 30; wy += 36) for (let wx = bx + 14; wx < bx + bw - 20; wx += 28) {
      const on = Math.sin(wx * 12.9 + wy * 78.2) > 0.2;
      if (on) { ctx.fillStyle = `rgba(255,${200 + 30 * Math.sin(t * 2 + wx)},120,.85)`; ctx.fillRect(wx, wy, 12, 16); }
    }
  }
  ctx.fillStyle = "#E9EEFF"; ctx.fillRect(0, h - 26, w, 26);
  for (const f of flakes) {
    const y = ((f.y + t * f.s * 0.12) % 1) * h, x = (f.x * w + Math.sin(t * 1.3 + f.ph) * 24 + w) % w;
    ctx.globalAlpha = 0.5 + f.r / 12; ctx.beginPath(); ctx.arc(x, y, f.r, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
  }
  ctx.globalAlpha = 1;
}
