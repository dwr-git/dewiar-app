/* «Что я умею» (18.10: «у нас есть функции, про которые никто не знает») — data/tricks.json, тот же список, что на
   телефоне («Ещё» → «Что я умею»). Здесь — то, что работает на компьютере: ▶ — фраза уходит помощнику (как сказать
   голосом); фраза с «…» — в «Чат», дописать; сочетания клавиш — просто подсказка. */
/* 28.10, владелец: «мелковато всё… иконки разделов крупнее и симпатичнее, чтобы не превращалось в одну большую мелко
   описанную страницу». Теперь сверху — плитки разделов (значок, название, сколько фраз), ниже — фразы выбранного раздела
   крупными карточками в две колонки. Раздел запоминается до перезапуска студии. */
let TRICKS = null, TR_SEL = 0;
const TR_LOOK = {          // подложка, цвет значка, рисунок — как плитки «Вопрос — ответ»
  talk: ["#DDE3F7", "#3F4BD8", "M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6a2.5 2.5 0 0 1-2.5 2.5H11l-4 3.5V15h0A2 2 0 0 1 5 13z M9 9.5h6 M9 12h3.5"],
  time: ["#F6E6CF", "#8A5300", "M12 21a8 8 0 1 0 0-16a8 8 0 1 0 0 16z M12 9v4l2.5 1.5 M10 3h4"],
  day: ["#D9EFE7", "#12704F", "M5 5h14v14H5z M8.5 12l2.3 2.3L15.5 9.5"],
  notes: ["#E6DEF6", "#5B36A8", "M7 4h8l3 3v13H7z M15 4v3h3 M10 11h5 M10 14.5h5 M10 18h3"],
  find: ["#DDE3F7", "#3F4BD8", "M11 18a7 7 0 1 0 0-14a7 7 0 1 0 0 14z M20 20l-4-4"],
  sound: ["#F6DDE6", "#A3284F", "M9 17V6l10-2v11 M9 17a2.5 2.5 0 1 1-5 0a2.5 2.5 0 1 1 5 0z M19 15a2.5 2.5 0 1 1-5 0a2.5 2.5 0 1 1 5 0z M9 9.5l10-2"],
  phone: ["#F6E6CF", "#8A5300", "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2"],
  close: ["#F6DDE6", "#A3284F", "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  pc: ["#D9EFE7", "#12704F", "M4 5h16v11H4z M9 20h6 M12 16v4"]
};
const TR_BY_NAME = { "Узнать и найти": "find" };
function trGroups() {
  return (TRICKS.groups || []).map(g => Object.assign({}, g, { key: g.id || TR_BY_NAME[g.name] || "talk",
    pcItems: g.items.filter(x => (x.where || []).includes("pc")) })).filter(g => g.pcItems.length);
}
const trIcon = (key, cls) => { const [bg, ink, d] = TR_LOOK[key] || TR_LOOK.talk;
  return `<i class="${cls || ""}" style="background:${bg}" aria-hidden="true"><svg viewBox="0 0 24 24" style="stroke:${ink}"><path d="${d}"/></svg></i>`; };
function trRender() {
  const box = $("#tr-box"); if (!box || !TRICKS) return;
  const gs = trGroups(); if (!gs.length) { box.textContent = ""; return; }
  if (TR_SEL >= gs.length) TR_SEL = 0;
  const g = gs[TR_SEL];
  const n = (k) => `${k} ${typeof plural === "function" ? plural(k, "фраза", "фразы", "фраз") : "фраз"}`;
  box.innerHTML = `<div class="tr-tiles" role="tablist">${gs.map((x, i) => `<button class="tr-tile${i === TR_SEL ? " on" : ""}" role="tab" aria-selected="${i === TR_SEL}" data-i="${i}">`
      + `${trIcon(x.key)}<b>${escH(x.name)}</b><em>${n(x.pcItems.length)}</em></button>`).join("")}</div>`
    + `<div class="tr-panel"><div class="tr-ph">${trIcon(g.key, "big")}<div><h2>${escH(g.name)}</h2><small>${n(g.pcItems.length)} · скажите голосом или нажмите ▶</small></div></div>`
    + `<div class="tr-list">${g.pcItems.map(x => `<div class="trk${x.key ? " key" : ""}"><div><b>${x.key ? escH(x.say) : "«" + escH(x.say) + "»"}</b><span>${escH(x.what)}</span></div>`
      + (x.key || x.noplay ? "" : `<button class="tplay" data-say="${escH(x.say)}"${x.fill ? ' data-fill="1"' : ""} title="${x.fill ? "В «Чат» — дописать" : "Отправить помощнику"}" aria-label="${x.fill ? "В «Чат» — дописать" : "Отправить помощнику"}">`
        + `${SVG(x.fill ? '<path d="M4 20h4L19 9l-4-4L4 16z"/>' : '<path d="M8 5.5v13l10.5-6.5z"/>')}</button>`) + `</div>`).join("")}</div></div>`;
  $$("#tr-box .tr-tile").forEach(b => b.onclick = () => { TR_SEL = +b.dataset.i; trRender(); });
  $$("#tr-box .tplay").forEach(b => b.onclick = async () => {
    const say = b.dataset.say;
    if (b.dataset.fill) { $('nav button[data-p="chat"]').click(); const t = $("#ch-text"); t.value = say.replace(/…$/, " ").replace(/:\s*…?$/, ": "); t.focus(); return; }
    b.disabled = true;
    try { await core.call("say", { text: say }); toast("Отправил помощнику — смотрите виджет"); } catch (e) { toast(e.message); }
    setTimeout(() => b.disabled = false, 1500);
  });
}
async function loadTricks() {
  const box = $("#tr-box"); if (!box) return;
  try { TRICKS = TRICKS || await core.call("tricks"); } catch (e) { box.textContent = e.message; return; }
  if (!TRICKS || !Array.isArray(TRICKS.groups)) { TRICKS = null; return; }
  trRender();
}
