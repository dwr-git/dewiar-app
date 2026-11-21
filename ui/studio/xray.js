/* «Рентген» ответа (план «Качество», владелец 21.11: «пользователь в простой красивой структурированной форме видит, что
   увидела Лира, как она думала… картой принятия решений, графовыми узлами… мысли Лиры видимыми»). Кнопка «Рентген» под
   ответом в «Чате» → по центру карта хода: услышала → поняла → собрала → модель → сделала → проверила → ответила.
   Узел — что было на этом шаге одной строкой и цветом: всё хорошо, поправила, не вышло, не понадобилось. Нажали на узел —
   подробности ниже: из чего подсказка (полоса по весу частей), какие действия и чем кончились, какие проверки сработали,
   журнал хода. «Что ушло в модель» — полный текст подсказки (хранится только для последних ответов). Данные — ядро
   (core/xray.py: xray_get). */
const XR = { cur: null, sel: "route" };
const XR_PARTS = [["sys", "Правила и персонаж"], ["tools", "Описания действий"], ["prof", "О человеке"], ["hist", "Разговор"], ["ask", "Справка к вопросу"]];
const XR_KIND = { dewiar: "облако Dewiar", cloud: "сервис по ключу", local: "своя модель", server: "сервер Dewiar дома", none: "мозг не подключён" };
const XR_ST = { heard: "Услышала", route: "Поняла", prompt: "Собрала", model: "Модель", acts: "Сделала", checks: "Проверила", answer: "Ответила" };
const XR_ICO = {
  heard: '<path d="M12 4.5a3 3 0 0 1 3 3v4a3 3 0 0 1-6 0v-4a3 3 0 0 1 3-3z"/><path d="M6.5 11a5.5 5.5 0 0 0 11 0M12 16.5v3"/>',
  route: '<path d="M5 12h6M11 12l4-5h4M11 12l4 5h4"/>',
  prompt: '<path d="M6 5.5h12M6 9.5h12M6 13.5h8M6 17.5h5"/>',
  model: '<circle cx="12" cy="12" r="6.5"/><path d="M12 5.5v13M5.5 12h13"/>',
  acts: '<path d="M14.5 6.5 17.5 9.5 9 18H6v-3z"/>',
  checks: '<path d="M12 4.5 18.5 7v5c0 4-3 6.5-6.5 7.5C8.5 18.5 5.5 16 5.5 12V7z"/><path d="m9.3 12 1.9 1.9 3.6-3.8"/>',
  answer: '<path d="M5.5 6.5h13v9h-7l-4 3v-3h-2z"/>',
};
const xrTok = (n) => Number(n || 0).toLocaleString("ru-RU");
const xrSec = (v) => v == null ? "" : (v < 10 ? (+v).toFixed(1) : Math.round(v)).toString().replace(".", ",") + " с";

function xrNodes(r) {
  const p = r.prompt, m = r.model, acts = r.acts || [], ch = r.checks || [], rt = r.route || {};
  const total = p ? Object.values(p.parts || {}).reduce((a, b) => a + (+b || 0), 0) : 0;
  const bad = acts.filter(a => !a.ok).length, win = m && m.window;
  const n = [];
  n.push({ k: "heard", s: "ok", t: r.src ? r.src[0].toUpperCase() + r.src.slice(1) : "", d: r.q });
  n.push({ k: "route", s: rt.kind === "none" ? "fail" : "ok",
    t: rt.kind === "cmd" ? "Быстрая команда" : rt.kind === "model" ? "Вопрос для модели" : "Нечем ответить",
    d: rt.kind === "cmd" ? `${rt.label} — без модели, сразу` : rt.kind === "model" ? "Нужна модель: разговор, рассуждение или действие" : "Ни команда, ни модель не ответили" });
  n.push(p ? { k: "prompt", s: win && total > win * 0.85 ? "warn" : "ok", t: `≈ ${xrTok(total)} токенов`,
    d: `${(p.tools || []).length} действий на выбор, ${p.turns || 0} реплик разговора` + (win && total > win * 0.85 ? " — окно почти полное" : "") }
    : { k: "prompt", s: "skip", t: "Не понадобилось", d: "Ответ без модели — подсказка не собиралась" });
  n.push(m ? { k: "model", s: "ok", t: m.model || m.name || "модель", d: [XR_KIND[m.kind] || m.kind, win ? `окно ${xrTok(win)}` : ""].filter(Boolean).join(" · ") }
    : { k: "model", s: "skip", t: "Не понадобилась", d: "" });
  n.push({ k: "acts", s: bad ? "fail" : acts.length ? "ok" : "skip",
    t: acts.length ? (bad ? `${acts.length - bad} из ${acts.length} вышло` : `${acts.length} ${acts.length === 1 ? "действие" : acts.length < 5 ? "действия" : "действий"}`) : "Без действий",
    d: acts.slice(0, 3).map(a => a.title || a.name).join(", ") });
  n.push({ k: "checks", s: ch.length ? "warn" : "ok", t: ch.length ? `Поправила ${ch.length}` : "Всё чисто",
    d: ch.length ? ch[0].replace(/^✋\s*/, "").slice(0, 90) : "Проверки ответа не нашли ошибок" });
  const a = r.answer;
  n.push({ k: "answer", s: r.cancelled ? "skip" : a ? "ok" : "fail", t: r.cancelled ? "Остановлено" : a ? `за ${xrSec(r.t != null ? r.t : a.t)}` : "Ответа нет",
    d: a ? (a.first != null ? `первое слово через ${xrSec(a.first)}` : (a.text || "").slice(0, 90)) : "" });
  return n;
}

function xrOpen(id) {
  if (!id) return;
  core.call("xray_get", { id, full: true }).then(r => { XR.cur = r; XR.sel = (r.route || {}).kind === "model" ? "prompt" : "route"; xrShow(); })
    .catch(e => toast(e.message));
}
function xrShow() {
  const r = XR.cur; if (!r) return;
  let ov = $("#xr-ov");
  if (!ov) {
    ov = document.createElement("div"); ov.id = "xr-ov"; ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true"); ov.setAttribute("aria-labelledby", "xr-h");
    ov.innerHTML = `<article class="xr-card"><header><div><h2 id="xr-h">Рентген ответа</h2><p class="xr-q"></p></div><button class="xr-x" aria-label="Закрыть">✕</button></header>
      <ol class="xr-map" aria-label="Как Лира шла к ответу"></ol><div class="xr-det" aria-live="polite"></div></article>`;
    document.body.appendChild(ov);
    ov.addEventListener("click", (e) => {
      if (e.target === ov || e.target.closest(".xr-x")) return xrClose();
      const nd = e.target.closest(".xr-n"); if (nd) { XR.sel = nd.dataset.k; xrShow(); return; }
      const fb = e.target.closest("[data-xfull]"); if (fb) { const pre = $(".xr-full", ov); if (pre) pre.hidden = !pre.hidden; fb.setAttribute("aria-expanded", pre && !pre.hidden ? "true" : "false"); }
    });
    ov.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); xrClose(); }
      if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && e.target.closest(".xr-n")) {
        const all = $$(".xr-n", ov), i = all.indexOf(e.target.closest(".xr-n")) + (e.key === "ArrowRight" ? 1 : -1);
        if (all[i]) { all[i].focus(); all[i].click(); }
      }
    });
  }
  $(".xr-q", ov).textContent = `«${(r.q || "").length > 160 ? r.q.slice(0, 160).trim() + "…" : r.q}»`;
  const nodes = xrNodes(r);
  $(".xr-map", ov).innerHTML = nodes.map(n => `<li><button type="button" class="xr-n ${n.s}${XR.sel === n.k ? " sel" : ""}" data-k="${n.k}" aria-pressed="${XR.sel === n.k}">`
    + `<span class="xr-i"><svg viewBox="0 0 24 24" aria-hidden="true">${XR_ICO[n.k]}</svg></span><b>${XR_ST[n.k]}</b><span class="xr-t">${escH(n.t)}</span>`
    + `<small>${escH(n.d || "")}</small></button></li>`).join("");
  $(".xr-det", ov).innerHTML = xrDetail(r, XR.sel);
  ov.classList.add("on");
  const sel = $(".xr-n.sel", ov); if (sel && !ov.contains(document.activeElement)) sel.focus({ preventScroll: true });
}
function xrClose() { const ov = $("#xr-ov"); if (ov) ov.classList.remove("on"); }

function xrLog(r, st) {
  const lines = (r.log || []).filter(l => !st || l.st === st);
  if (!lines.length) return "";
  return `<h4>Журнал хода${st ? " — этот шаг" : ""}</h4><ol class="xr-log">${lines.slice(0, 120).map(l =>
    `<li class="${l.lv === "W" || l.lv === "E" ? "w" : ""}" data-st="${escH(l.st || "")}"><time>${xrSec(l.t)}</time><span>${escH(l.m)}</span></li>`).join("")}</ol>`;
}
function xrDetail(r, k) {
  const p = r.prompt || {}, m = r.model, rt = r.route || {};
  if (k === "heard") return `<h3>Что услышала</h3><blockquote>${escH(r.q || "")}</blockquote><p class="xr-mute">Откуда: ${escH(r.src || "")}. ${new Date((r.ts || 0) * 1000).toLocaleString("ru-RU")}</p>` + xrLog(r, "heard");
  if (k === "route") {
    const path = (r.path || []).length ? `<p class="xr-mute">По пути сработало ещё: ${escH(r.path.join(", "))}</p>` : "";
    return `<h3>Как поняла вопрос</h3><p>${rt.kind === "cmd" ? `Это быстрая команда «${escH(rt.label)}». Лира выполнила её сама, без модели: так быстрее и надёжнее.`
      : rt.kind === "model" ? "Быстрой команды для этих слов нет, поэтому Лира собрала подсказку и спросила модель."
      : "Ни одна команда не подошла, а модель не ответила."}</p>${path}` + xrLog(r, "");
  }
  if (k === "prompt") {
    if (!r.prompt) return `<h3>Подсказка</h3><p class="xr-mute">Для быстрой команды модель не нужна, и подсказка не собиралась.</p>`;
    const parts = XR_PARTS.map(([key, name]) => [key, name, +((p.parts || {})[key] || 0)]).filter(x => x[2] > 0);
    const total = parts.reduce((a, x) => a + x[2], 0) || 1, win = m && m.window;
    const bar = `<div class="xr-bar" role="img" aria-label="Из чего подсказка: ${parts.map(x => `${x[1]} ${xrTok(x[2])}`).join(", ")}">`
      + parts.map(x => `<i class="p-${x[0]}" style="flex:${x[2]}"></i>`).join("") + (win && win > total ? `<i class="p-free" style="flex:${win - total}"></i>` : "") + `</div>`;
    const legend = `<ul class="xr-leg">${parts.map(x => `<li><i class="p-${x[0]}"></i>${x[1]}<b>${xrTok(x[2])}</b><small>${Math.round(x[2] / total * 100)} %</small></li>`).join("")}`
      + (win ? `<li><i class="p-free"></i>Свободно в окне<b>${xrTok(Math.max(0, win - total))}</b></li>` : "") + `</ul>`;
    const ctx = (p.ctx || []).length ? `<h4>Справка к вопросу</h4><ul class="xr-list">${p.ctx.map(c => `<li>${escH(c)}</li>`).join("")}</ul>` : "";
    const tools = (p.tools || []).length ? `<h4>Действия на выбор · ${p.tools.length}</h4><p class="xr-tags">${p.tools.map(t => `<code>${escH(t)}</code>`).join(" ")}</p>` : "";
    const full = r.full ? `<button class="btn small" type="button" data-xfull aria-expanded="false">Что ушло в модель — целиком</button><div class="xr-full" hidden>`
      + `<h4>Инструкция модели</h4><pre>${escH(r.full.system || "")}</pre>${(r.full.msgs || []).map(mm => `<h4>${mm.role === "user" ? "Человек" : mm.role === "assistant" ? "Лира" : escH(mm.role)}</h4><pre>${escH(mm.text)}</pre>`).join("")}</div>`
      : `<p class="xr-mute">Полный текст подсказки хранится только для последних ответов.</p>`;
    return `<h3>Из чего собрана подсказка · ≈ ${xrTok(total)} токенов${win ? ` из ${xrTok(win)}` : ""}</h3>${bar}${legend}${ctx}${tools}${full}` + xrLog(r, "prompt");
  }
  if (k === "model") {
    if (!m) return `<h3>Модель</h3><p class="xr-mute">Не понадобилась — ответила быстрая команда.</p>`;
    return `<h3>Кто думал</h3><dl class="xr-dl"><dt>Модель</dt><dd><code>${escH(m.model || "")}</code></dd><dt>Профиль</dt><dd>${escH(m.name || "")}</dd>`
      + `<dt>Где думает</dt><dd>${escH(XR_KIND[m.kind] || m.kind || "")}</dd><dt>Окно</dt><dd>${m.window ? xrTok(m.window) + " токенов" : "неизвестно"}</dd>`
      + (r.answer && r.answer.tokens ? `<dt>Токены</dt><dd>${Object.entries(r.answer.tokens).map(([a, b]) => `${a} ${xrTok(b)}`).join(", ")}</dd>` : "") + `</dl>` + xrLog(r, "model");
  }
  if (k === "acts") {
    const acts = r.acts || [];
    if (!acts.length) return `<h3>Действия</h3><p class="xr-mute">В этом ответе Лира ничего не выполняла — только говорила.</p>` + xrLog(r, "acts");
    return `<h3>Что сделала</h3><ol class="xr-acts">${acts.map(a => `<li class="${a.ok ? "ok" : "fail"}"><b>${escH(a.title || a.name)}</b> <code>${escH(a.name)}</code>`
      + `<span class="xr-st">${a.ok ? "получилось" : "не вышло"} · ${xrSec(a.t)}</span>${a.args ? `<pre>${escH(a.args)}</pre>` : ""}${a.result ? `<p>${escH(a.result)}</p>` : ""}</li>`).join("")}</ol>` + xrLog(r, "acts");
  }
  if (k === "checks") {
    const ch = r.checks || [];
    return `<h3>Проверки ответа</h3>` + (ch.length ? `<p>Лира проверила свой ответ и поправила ${ch.length === 1 ? "одно место" : `места: ${ch.length}`}:</p><ul class="xr-list">${ch.map(c => `<li>${escH(c.replace(/^✋\s*/, ""))}</li>`).join("")}</ul>`
      : `<p class="xr-mute">Проверки (обещала — сделала, правда о сделанном, повторы, язык) ничего не нашли.</p>`);
  }
  if (k === "answer") {
    const a = r.answer;
    return `<h3>Ответ</h3>` + (a ? `<blockquote>${escH(a.text)}</blockquote><p class="xr-mute">${a.first != null ? `Первое слово — через ${xrSec(a.first)}, ` : ""}весь ход — ${xrSec(r.t)}.</p>`
      : `<p class="xr-mute">${r.cancelled ? "Ответ остановили." : "Ответа не было."}</p>`) + xrLog(r, "answer");
  }
  return "";
}
document.addEventListener("click", (ev) => {
  const b = ev.target.closest && ev.target.closest("[data-xray]"); if (!b) return;
  ev.stopPropagation(); xrOpen(b.dataset.xray);
});
