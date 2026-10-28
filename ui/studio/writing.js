/* «Пишу» в «Документах» (0.68; писатель 28.10: «Лира — в моём редакторе?», план владельца: «Документы» и для своих текстов).
   Сколько слов написано сегодня в своих текстах из папок «Документов», цель на день, две недели столбиками, дни подряд
   и в каких файлах. Ядро (core/writing.py): writing_get, writing_goal {goal}. Текст никуда не уходит — только числа. */
const WR = { d: null };
const wrN = (n) => Number(n || 0).toLocaleString("ru-RU");
const wrWords = (n) => { n = Math.abs(n | 0); const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "слово" : a >= 2 && a <= 4 && (b < 12 || b > 14) ? "слова" : "слов"; };

async function loadWriting() {
  try { WR.d = await core.call("writing_get"); } catch (e) { return; }
  wrRender();
}

function wrRender() {
  const d = WR.d; if (!d || !$("#wr-card")) return;
  const none = !d.files;
  $("#wr-card").classList.toggle("none", none);
  $("#wr-empty").hidden = !none;
  if (none) return;
  $("#wr-today").textContent = wrN(d.today); $("#wr-u").textContent = wrWords(d.today);
  const g = d.goal || 0, pct = g ? Math.min(100, Math.round(d.today / g * 100)) : 0;
  $("#wr-goal").hidden = !g; $("#wr-fill").style.width = pct + "%";
  $("#wr-card").classList.toggle("met", !!g && d.today >= g);
  if (document.activeElement !== $("#wr-goal-n")) $("#wr-goal-n").value = g || "";
  wrBars(d.days || [], g);
  const f = [];
  if (g) f.push(d.today >= g ? `<li class="ok"><b>Цель дня — есть</b><span>${wrN(d.today)} из ${wrN(g)}</span></li>` : `<li><b>До цели ${wrN(g - d.today)}</b><span>${pct}% из ${wrN(g)}</span></li>`);
  f.push(`<li><b>${wrN(d.week)}</b><span>${wrWords(d.week)} за 7 дней</span></li>`);
  if (d.streak >= 2) f.push(`<li><b>${d.streak} ${d.streak % 10 === 1 && d.streak % 100 !== 11 ? "день" : [2, 3, 4].includes(d.streak % 10) && !(d.streak % 100 >= 12 && d.streak % 100 <= 14) ? "дня" : "дней"} подряд</b><span>пишете от 50 слов в день</span></li>`);
  if ((d.touched || []).length) f.push(`<li class="wr-files"><b>Сегодня — в</b><span>${d.touched.slice(0, 3).map(t => `«${escH(t.name.replace(/\.(md|txt|docx|odt|html?)$/i, ""))}» <em>+${wrN(t.n)}</em>`).join(", ")}</span></li>`);
  f.push(`<li class="wr-all"><span>Всего в ваших текстах — ${wrN(d.total)} ${wrWords(d.total)}, файлов: ${wrN(d.files)}</span></li>`);
  $("#wr-facts").innerHTML = f.join("");
}

/* две недели — столбики одного цвета, сегодня ярче; цель — тонкая линия; наведите — число и дата */
function wrBars(days, goal) {
  const svg = $("#wr-bars"), W = Math.max(220, Math.round(svg.getBoundingClientRect().width) || 300), H = 92, pad = 4, n = days.length || 1;
  const max = Math.max(goal || 0, ...days.map(x => x.n), 10);
  const bw = (W - pad * 2) / n, gap = Math.max(4, bw * 0.34);
  svg.setAttribute("viewBox", `0 0 ${W} ${H + 16}`); svg.setAttribute("height", H + 16);
  const fmt = (iso) => new Date(iso + "T12:00").toLocaleDateString("ru-RU", { weekday: "short", day: "numeric", month: "short" });
  let h = "";
  if (goal) { const y = H - goal / max * (H - 6); h += `<line class="wr-gline" x1="0" x2="${W}" y1="${y}" y2="${y}"/>`; }
  days.forEach((x, i) => {
    const bh = x.n ? Math.max(3, x.n / max * (H - 6)) : 0, xx = pad + i * bw + gap / 2, w = bw - gap, y = H - bh, today = i === n - 1;
    const r = Math.min(4, w / 2, bh);
    if (bh) h += `<path class="wr-bar${today ? " now" : ""}" d="M${xx},${H}V${y + r}Q${xx},${y} ${xx + r},${y}H${xx + w - r}Q${xx + w},${y} ${xx + w},${y + r}V${H}Z"/>`;
    else h += `<rect class="wr-zero" x="${xx}" y="${H - 2}" width="${w}" height="2" rx="1"/>`;
    h += `<rect class="wr-hit" x="${pad + i * bw}" y="0" width="${bw}" height="${H + 16}" data-t="${escH(fmt(x.d))}: ${wrN(x.n)} ${wrWords(x.n)}"/>`;
    if (today || i === 0 || i === 7) h += `<text class="wr-lbl" x="${xx + w / 2}" y="${H + 13}" text-anchor="middle">${today ? "сегодня" : escH(new Date(x.d + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "short" }))}</text>`;
  });
  svg.innerHTML = h;
  const tip = $("#wr-tip");
  $$(".wr-hit", svg).forEach(r => { r.onmouseenter = () => (tip.textContent = r.dataset.t); r.onmouseleave = () => (tip.textContent = "Две недели"); });
}

(function wrWire() {
  const gi = $("#wr-goal-n"); if (!gi) return;
  gi.onchange = async () => { try { WR.d = await core.call("writing_goal", { goal: +gi.value || 0 }); wrRender(); toast(+gi.value ? "Цель на день сохранена" : "Цель убрана"); } catch (e) { toast(e.message); } };
})();
window.loadWriting = loadWriting;
