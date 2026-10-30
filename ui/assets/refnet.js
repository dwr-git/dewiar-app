/* «Моё созвездие» — приглашённые друзья картиной (телефон: «Мозг» → «Пригласить друга»; студия: «Dewiar.pro» →
   «Пригласить друзей»). В центре — вы; каждый приглашённый — звезда: пока он пробует Dewiar, вокруг неё дорисовывается
   кольцо дней (days из need), засчитали — звезда золотая и вам талеры; маленькие спутники — те, кого пригласил уже он
   сам. Сверху — звание по числу засчитанных друзей и сколько до следующего. Новая золотая звезда с прошлого раза —
   вспышка (что уже видели — в localStorage, ключ seenKey).
   DewiarRefNet.render(el, d, {me, seenKey, big, by, sel, onPick}) — d как у cloud.php ?p=/ref: {invited: [{name, days, need,
   paid, sub, label?, close?}], earned, bonus, days}. Всё рисуется SVG без внешних файлов; цвета — свои (ночное небо в любой теме).
   light — светлое «дневное» небо для светлых тем; x.img, o.meImg, o.byImg — фото в звёздах (data: или https:).
   big — раздел «Рефералы»: звёзды крупнее, под ними имена (label — имя из «Близких», если друг уже там), туманность и мерцание,
   сверху — звезда того, кто позвал вас (by — его имя); звезду можно нажать: onPick(i) или onPick("by"), sel — выбранная, calm — перерисовка без появления звёзд заново. */
(function (root) {
  "use strict";
  const RANKS = [[0, "Искра"], [1, "Огонёк"], [3, "Звезда"], [5, "Созвездие"], [10, "Галактика"], [25, "Вселенная"]];
  const COLORS = ["#9BD4FF", "#FF9FD0", "#7CF0CF", "#B79CFF", "#FFC37A", "#A5E36B", "#8FA2FF", "#FF8F80"];
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const tal = (x) => String(Math.round((+x || 0) * 100) / 100).replace(".", ",");
  const hash = (s) => [...String(s)].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const plural = (n, a, b, c) => { const m = n % 10, h = n % 100; return m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 10 || h >= 20) ? b : c; };
  const f = (v) => +v.toFixed(1);

  const CSS = `.rn{position:relative;border-radius:22px;overflow:hidden;color:#EEF0FF;font-family:inherit;
    background:radial-gradient(120% 90% at 50% 40%,#1d1a3c 0%,#0e0d1e 62%,#09080f 100%)}
  .rn svg{display:block;width:100%;height:auto;stroke:none;stroke-width:1;fill:none}   /* у телефона общее правило svg рисует контуры — здесь их нет */
  .rn .rk{position:relative;padding:16px 16px 0;display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
  .rn .rk b{display:block;font-size:17px;font-weight:700;letter-spacing:.01em}
  .rn .rk small{display:block;font-size:12.5px;color:rgba(238,240,255,.62);margin-top:2px;max-width:15em;line-height:1.35}
  .rn .coin{display:flex;align-items:center;gap:7px;font-weight:700;font-size:20px;color:#FFD27A;white-space:nowrap}
  .rn .coin i{width:22px;height:22px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#FFF1C2,#FFC24B 45%,#C98712);box-shadow:0 0 14px rgba(255,194,75,.55)}
  .rn .st{display:flex;gap:6px;padding:0 12px 14px;flex-wrap:wrap}
  .rn .st span{flex:1 1 70px;text-align:center;padding:8px 6px;border-radius:14px;background:rgba(255,255,255,.06);font-size:12px;color:rgba(238,240,255,.6);line-height:1.25}
  .rn .st span b{display:block;font-size:18px;color:#fff;font-weight:700}
  .rn .bar{height:5px;border-radius:5px;background:rgba(255,255,255,.1);margin:8px 0 0;width:150px;overflow:hidden}
  .rn .bar i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#8B8CF7,#FFC24B)}
  .rn .nd{transform-box:fill-box;transform-origin:center;animation:rnIn .7s cubic-bezier(.2,.9,.3,1.3) both}
  .rn .gold .halo{animation:rnTw 3.2s ease-in-out infinite}
  .rn .me .halo{animation:rnTw 4.5s ease-in-out infinite}
  .rn .burst{transform-box:fill-box;transform-origin:center;animation:rnBurst 1.6s ease-out 2 both}
  .rn .orb{transform-origin:220px 220px;animation:rnSpin 120s linear infinite}
  .rn.calm .nd,.rn.calm .burst{animation:none}   /* перерисовка по выбору звезды — без повторного появления */
  .rn .hit{cursor:pointer;outline:none}
  .rn .hit:focus-visible{stroke:#fff;stroke-width:2;stroke-dasharray:3 4}
  .rn .tw{animation:rnTw 2.6s ease-in-out infinite}
  .rn.big{border-radius:28px;background:radial-gradient(90% 70% at 50% 46%,#2a2160 0%,#151233 46%,#0a0917 78%,#07060d 100%)}
  .rn.big .rk{padding:22px 24px 0}
  .rn.big .rk b{font:600 24px "Unbounded",inherit;letter-spacing:.01em}
  .rn.big .rk small{font-size:13.5px;max-width:22em}
  .rn.big .bar{width:220px;height:6px}
  .rn.big .coin{font-size:26px}.rn.big .coin i{width:28px;height:28px}
  .rn.big svg{max-height:min(640px,70vh);margin:-34px auto -18px}
  .rn.big .st{padding:0 18px 20px;gap:8px}
  .rn.big .st span{background:rgba(255,255,255,.07);font-size:12.5px;padding:10px 6px}.rn.big .st span b{font-size:22px}
  .rn.light{color:#1f2440;background:radial-gradient(90% 75% at 50% 44%,#ffffff 0%,#f1f3fc 52%,#e4e8f6 100%)}
  .rn.light .rk small{color:rgba(31,36,64,.62)}
  .rn.light .st span{background:rgba(255,255,255,.72);color:rgba(31,36,64,.6);box-shadow:0 6px 16px -12px rgba(40,50,110,.45)}
  .rn.light .st span b{color:#1f2440}
  .rn.light .bar{background:rgba(70,80,140,.12)}
  .rn.light .coin{color:#b07a10}
  .rn.light .hit:focus-visible{stroke:#6a6cf0}
  @keyframes rnIn{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:scale(1)}}
  @keyframes rnTw{0%,100%{opacity:.55}50%{opacity:1}}
  @keyframes rnBurst{0%{opacity:.95;transform:scale(.6)}100%{opacity:0;transform:scale(2.6)}}
  @keyframes rnSpin{to{transform:rotate(360deg)}}
  @media (prefers-reduced-motion:reduce){.rn .nd,.rn .halo,.rn .burst,.rn .orb{animation:none!important}}`;

  function place(n, big, by) {      // кольца: 8, 14, 20 звёзд; дальше — «+N»
    const rings = big ? [[8, 132, 24], [14, 192, 17], [20, 244, 12]] : [[8, 112, 17], [14, 160, 13], [20, 200, 10]], out = [];
    let i = 0;
    for (const [cap, r, size] of rings) {
      const k = Math.min(cap, n - i); if (k <= 0) break;
      // сверху над «вами» — звезда того, кто позвал (by): первое кольцо сдвигаем на полшага, чтобы линия к ней шла между звёзд
      const off = (out.length || (big && by) ? 0.5 : 0) * (2 * Math.PI / k) - Math.PI / 2 + (r === 160 || r === 192 ? 0.18 : 0);
      for (let j = 0; j < k; j++) { const a = off + j * 2 * Math.PI / k; out.push({ x: 220 + r * Math.cos(a), y: 220 + r * Math.sin(a), a, size }); }
      i += k;
    }
    return out;
  }

  // фото человека в звезде (29.10, владелец: «чтобы и фото поддерживалось, если загрузил себе на аватарку»): только data: и
  // https: — картинка из «Близких» (их фото по согласию), круг по размеру звезды
  function photo(src, x, y, r, id) {
    if (!/^(data:image\/|https:)/.test(String(src || ""))) return "";
    return `<clipPath id="${id}"><circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}"/></clipPath><image href="${esc(src)}" x="${f(x - r)}" y="${f(y - r)}" width="${f(2 * r)}" height="${f(2 * r)}" clip-path="url(#${id})" preserveAspectRatio="xMidYMid slice"/>`;
  }

  function render(el, d, o) {
    o = o || {};
    if (!document.getElementById("rn-css")) { const s = document.createElement("style"); s.id = "rn-css"; s.textContent = CSS; document.head.appendChild(s); }
    // light — дневное небо для светлых тем (29.10, владелец: «рефералы в совсем другом стиле, тёмный такой»): те же звёзды
    // и линии, только тушью по светлому; цвет звёзд и золото — как были
    const Lt = !!o.light, ink = (a) => Lt ? `rgba(60,70,130,${a})` : `rgba(255,255,255,${a})`, txt = Lt ? "#3b4366" : "rgba(238,240,255,.86)";
    const big = !!o.big, list = (d && d.invited) || [], paid = list.filter(x => x.paid).length, subs = list.reduce((a, x) => a + (+x.sub || 0), 0);
    const rank = RANKS.filter(r => paid >= r[0]).pop(), next = RANKS.find(r => r[0] > paid);
    let seen = [];
    try { seen = JSON.parse(localStorage.getItem(o.seenKey || "dw_refnet_seen") || "[]"); } catch (e) { }
    const pos = place(list.length, big, o.by), shown = pos.length, more = list.length - shown;
    // фон: неподвижные звёзды неба (одни и те же каждый раз)
    let sky = "", h = 12345;
    const SK = big ? 600 : 440, S0 = 220 - SK / 2;
    for (let i = 0; i < (big ? 150 : 70); i++) { h = (h * 1103515245 + 12345) >>> 0; const x = S0 + h % SK; h = (h * 1103515245 + 12345) >>> 0; const y = S0 + h % SK; h = (h * 1103515245 + 12345) >>> 0;
      const tw = big && i % 9 === 0;          // в большом небе часть звёзд мерцает — каждая в свой такт
      sky += `<circle ${tw ? `class="tw" style="animation-delay:${(h % 26) / 10}s"` : ""} cx="${x}" cy="${y}" r="${f((h % 10) / 10 + (tw ? .9 : .3))}" fill="${Lt ? "#7d84d6" : "#fff"}" opacity="${f(((tw ? .5 : .12) + (h % 30) / 100) * (Lt ? .55 : 1))}"/>`; }
    if (big) sky = `<ellipse cx="150" cy="170" rx="230" ry="150" fill="url(#rnNebA)"/><ellipse cx="320" cy="300" rx="220" ry="140" fill="url(#rnNebB)"/>
      <ellipse cx="300" cy="110" rx="170" ry="110" fill="url(#rnNebC)"/>` + sky;
    let edges = "", nodes = "";
    list.slice(0, shown).forEach((x, i) => {
      const p = pos[i], c = COLORS[hash(x.name) % COLORS.length], gold = !!x.paid, key = x.name + "|" + (x.since || "");
      const fresh = gold && !seen.includes(key);
      edges += `<line x1="220" y1="220" x2="${f(p.x)}" y2="${f(p.y)}" stroke="${gold ? "url(#rnGold)" : ink(Lt ? .32 : .22)}" stroke-width="${gold ? 1.8 : 1.1}" ${gold ? "" : 'stroke-dasharray="3 5"'} stroke-linecap="round"/>`;
      const prog = gold ? 1 : Math.max(0, Math.min(1, (+x.days || 0) / Math.max(1, +x.need || 1))), R = p.size + 4, L = 2 * Math.PI * R;
      let sat = "";
      const k = Math.min(5, +x.sub || 0);
      for (let j = 0; j < k; j++) { const a = p.a + (j - (k - 1) / 2) * 0.42, rr = p.size + 13; sat += `<circle cx="${f(p.x + rr * Math.cos(a))}" cy="${f(p.y + rr * Math.sin(a))}" r="2.6" fill="${c}" opacity=".85"/>`; }
      nodes += `<g class="nd ${gold ? "gold" : ""}" style="animation-delay:${180 + i * 70}ms"><title>${esc(x.name)}${gold ? " — засчитан" : ` — ${+x.days || 0} из ${+x.need || 0} дн.`}${x.sub ? `, пригласил ${x.sub}` : ""}</title>
        <circle class="halo" cx="${f(p.x)}" cy="${f(p.y)}" r="${p.size + 10}" fill="url(#${gold ? "rnGlowGold" : "rnGlow"})"/>
        ${fresh ? `<circle class="burst" cx="${f(p.x)}" cy="${f(p.y)}" r="${p.size + 6}" fill="none" stroke="#FFD27A" stroke-width="2"/>` : ""}
        <circle cx="${f(p.x)}" cy="${f(p.y)}" r="${R}" fill="none" stroke="${ink(.12)}" stroke-width="2.4"/>
        <circle cx="${f(p.x)}" cy="${f(p.y)}" r="${R}" fill="none" stroke="${gold ? "#FFC24B" : c}" stroke-width="2.4" stroke-linecap="round"
          stroke-dasharray="${f(L * prog)} ${f(L)}" transform="rotate(-90 ${f(p.x)} ${f(p.y)})"/>
        <circle cx="${f(p.x)}" cy="${f(p.y)}" r="${p.size}" fill="${gold ? "url(#rnCoin)" : c}" opacity="${gold ? 1 : .9}"/>
        ${x.img ? photo(x.img, p.x, p.y, p.size - (gold ? 2 : 0), "rnp" + i) : p.size >= 13 ? `<text x="${f(p.x)}" y="${f(p.y + p.size * .36)}" text-anchor="middle" font-size="${f(p.size * .95)}" font-weight="700" fill="${gold ? "#6b4100" : "#141226"}">${esc((x.name || "?").slice(0, 1).toUpperCase())}</text>` : ""}
        ${sat}
        ${x.close ? `<circle cx="${f(p.x + p.size * .78)}" cy="${f(p.y - p.size * .78)}" r="${big ? 6.5 : 5}" fill="#FF7FB6"/><circle cx="${f(p.x + p.size * .78)}" cy="${f(p.y - p.size * .78)}" r="${big ? 2.4 : 1.8}" fill="#fff"/>` : ""}
        ${big && p.size >= 17 ? `<text x="${f(p.x)}" y="${f(p.y + p.size + 21)}" text-anchor="middle" font-size="12.5" fill="${txt}">${esc(String(x.label || x.name || "").slice(0, 14))}</text>` : ""}
        ${o.sel === i ? `<circle cx="${f(p.x)}" cy="${f(p.y)}" r="${p.size + 9}" fill="none" stroke="${Lt ? "#6a6cf0" : "#fff"}" stroke-width="2"/>` : ""}
        ${o.onPick ? `<circle class="hit" data-i="${i}" tabindex="0" role="button" aria-label="${esc(x.label || x.name)}" cx="${f(p.x)}" cy="${f(p.y)}" r="${p.size + 14}" fill="transparent"/>` : ""}</g>`;
    });
    const ghosts = list.length ? "" : place(6).map((p, i) => `<g class="nd" style="animation-delay:${200 + i * 90}ms"><circle cx="${f(p.x)}" cy="${f(p.y)}" r="17" fill="none" stroke="${ink(.3)}" stroke-dasharray="3 4"/><text x="${f(p.x)}" y="${f(p.y + 6)}" text-anchor="middle" font-size="18" fill="${ink(.45)}">+</text></g>`).join("");
    // рамка — по самому дальнему кольцу: пока друзей немного, картина не тонет в пустоте
    let ext = (list.length ? Math.max(...pos.map(q => Math.hypot(q.x - 220, q.y - 220) + q.size + (big ? 34 : 20))) : big ? 190 : 150) + (more > 0 ? 18 : 0) + 8;
    // тот, кто позвал вас, — звезда сверху: ваша «линия» вверх
    let upline = "";
    if (big && o.by) {
      const ry = 220 - ext + 4;
      // вертикальной линии градиент «по рамке» не нарисовать (рамка нулевой ширины) — цвет сплошной
      upline = `<line x1="220" y1="${f(ry + 20)}" x2="220" y2="180" stroke="${Lt ? "rgba(90,120,200,.5)" : "rgba(155,212,255,.55)"}" stroke-width="1.6" stroke-dasharray="2 6" stroke-linecap="round"/>
        <g class="nd" style="animation-delay:120ms"><circle class="halo" cx="220" cy="${f(ry)}" r="34" fill="url(#rnGlow)"/><circle cx="220" cy="${f(ry)}" r="18" fill="#9BD4FF"/>
        ${o.byImg ? photo(o.byImg, 220, ry, 18, "rnpby") : `<text x="220" y="${f(ry + 6)}" text-anchor="middle" font-size="16" font-weight="700" fill="#141226">${esc(String(o.by).slice(0, 1).toUpperCase())}</text>`}
        <text x="220" y="${f(ry - 28)}" text-anchor="middle" font-size="12.5" fill="${txt}">Вас позвал(а) ${esc(String(o.by).slice(0, 16))}</text>
        ${o.sel === "by" ? `<circle cx="220" cy="${f(ry)}" r="27" fill="none" stroke="${Lt ? "#6a6cf0" : "#fff"}" stroke-width="2"/>` : ""}
        ${o.onPick ? `<circle class="hit" data-i="by" tabindex="0" role="button" aria-label="Вас позвал(а) ${esc(o.by)}" cx="220" cy="${f(ry)}" r="32" fill="transparent"/>` : ""}</g>`;
    }
    const top = upline ? 220 - ext - 70 : 220 - ext;     // над звездой «кто позвал» — место для подписи под шапкой
    const vb = `${f(220 - ext)} ${f(top)} ${f(ext * 2)} ${f(220 + ext - top)}`;
    const svg = `<svg viewBox="${vb}" role="img" aria-label="Созвездие приглашённых друзей: ${list.length} ${plural(list.length, "друг", "друга", "друзей")}, засчитано ${paid}">
      <defs>
        <radialGradient id="rnGlow"><stop offset="0" stop-color="#9BD4FF" stop-opacity=".35"/><stop offset="1" stop-color="#9BD4FF" stop-opacity="0"/></radialGradient>
        <radialGradient id="rnGlowGold"><stop offset="0" stop-color="#FFC24B" stop-opacity=".55"/><stop offset="1" stop-color="#FFC24B" stop-opacity="0"/></radialGradient>
        <radialGradient id="rnMe" cx=".35" cy=".3"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#C9B8FF"/><stop offset="1" stop-color="#7a5cf0"/></radialGradient>
        <radialGradient id="rnMeGlow"><stop offset="0" stop-color="#B79CFF" stop-opacity=".6"/><stop offset="1" stop-color="#B79CFF" stop-opacity="0"/></radialGradient>
        <radialGradient id="rnCoin" cx=".35" cy=".3"><stop offset="0" stop-color="#FFF1C2"/><stop offset=".45" stop-color="#FFC24B"/><stop offset="1" stop-color="#C98712"/></radialGradient>
        <radialGradient id="rnNebA"><stop offset="0" stop-color="#7B5CFF" stop-opacity="${Lt ? .14 : .34}"/><stop offset="1" stop-color="#7B5CFF" stop-opacity="0"/></radialGradient>
        <radialGradient id="rnNebB"><stop offset="0" stop-color="#FF6FB5" stop-opacity="${Lt ? .1 : .2}"/><stop offset="1" stop-color="#FF6FB5" stop-opacity="0"/></radialGradient>
        <radialGradient id="rnNebC"><stop offset="0" stop-color="#3EC8FF" stop-opacity="${Lt ? .12 : .18}"/><stop offset="1" stop-color="#3EC8FF" stop-opacity="0"/></radialGradient>
        <linearGradient id="rnGold" gradientUnits="userSpaceOnUse" x1="220" y1="220" x2="420" y2="220"><stop offset="0" stop-color="#B79CFF"/><stop offset="1" stop-color="#FFC24B"/></linearGradient>
      </defs>
      ${sky}
      <g class="orb" opacity=".5"><circle cx="220" cy="220" r="112" fill="none" stroke="${ink(Lt ? .2 : .07)}" stroke-dasharray="1 7"/><circle cx="220" cy="220" r="160" fill="none" stroke="${ink(Lt ? .15 : .05)}" stroke-dasharray="1 9"/></g>
      ${edges}${ghosts}${nodes}
      ${upline}
      <g class="me"><circle class="halo" cx="220" cy="220" r="${big ? 78 : 56}" fill="url(#rnMeGlow)"/><circle cx="220" cy="220" r="${big ? 40 : 30}" fill="url(#rnMe)"/>
        ${o.meImg ? photo(o.meImg, 220, 220, big ? 37 : 28, "rnpme") + (big ? `<text x="220" y="${big ? 282 : 266}" text-anchor="middle" font-size="13" font-weight="700" fill="${txt}">${esc(o.me || "Вы")}</text>` : "") : `<text x="220" y="${big ? 227 : 226}" text-anchor="middle" font-size="${big ? 17 : 15}" font-weight="700" fill="#24164f">${esc(o.me || "Вы")}</text>`}</g>
      ${more > 0 ? `<text x="220" y="${f(220 + ext - 12)}" text-anchor="middle" font-size="14" fill="${ink(.6)}">и ещё ${more}</text>` : ""}
    </svg>`;
    const toNext = next ? next[0] - paid : 0, frac = next ? (paid - rank[0]) / (next[0] - rank[0]) : 1;
    el.innerHTML = `<div class="rn${big ? " big" : ""}${Lt ? " light" : ""}${o.calm ? " calm" : ""}">
      <div class="rk"><div><b>${esc(rank[1])}</b><small>${next ? `До «${esc(next[1])}» — ещё ${toNext} ${plural(toNext, "засчитанный друг", "засчитанных друга", "засчитанных друзей")}` : "Высшее звание — спасибо, что зовёте друзей!"}</small>
        <div class="bar"><i style="width:${Math.round(frac * 100)}%"></i></div></div>
        <div class="coin" title="Получено за приглашения"><i></i>+${tal(d && d.earned)}</div></div>
      ${svg}
      <div class="st"><span><b>${list.length}</b>${plural(list.length, "друг", "друга", "друзей")}</span><span><b>${paid}</b>засчитано</span><span><b>${subs}</b>в их сетях</span></div></div>`;
    if (o.onPick) {                    // звезду можно нажать (и выбрать с клавиатуры)
      const pick = (t) => { const v = t.getAttribute("data-i"); o.onPick(v === "by" ? "by" : +v); };
      el.querySelectorAll(".hit").forEach(c => { c.addEventListener("click", () => pick(c));
        c.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(c); } }); });
    }
    // золотые звёзды запоминаем как увиденные — вспышка только один раз
    try { localStorage.setItem(o.seenKey || "dw_refnet_seen", JSON.stringify(list.filter(x => x.paid).map(x => x.name + "|" + (x.since || "")).slice(-200))); } catch (e) { }
    return { paid, rank: rank[1], fresh: list.filter(x => x.paid && !seen.includes(x.name + "|" + (x.since || ""))).length };
  }

  // цвет звезды друга — тот же и в списке рядом (по имени от сервера)
  root.DewiarRefNet = { render, RANKS, color: (name) => COLORS[hash(name) % COLORS.length] };
})(typeof window !== "undefined" ? window : globalThis);
