/* Студия Dewiar: значки разделов и справка «?» у заголовков.
   ICONS — свой набор контуров SVG 24×24 (в духе Lucide), встроен в код: студия работает без интернета. Ключ — data-p
   кнопки меню и id раздела без «p-»; при загрузке значки вставляются в меню и заголовки разделов.
   Справка берётся из window.DEWIAR_HELP (assets/help.js); «▶» у примера шлёт фразу ассистенту командой say.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область: при загрузке здесь нужны
   только $/$$ (core.js); escH (folder.js) и SVG (welcome.js) — при открытии справки. */
/* ---------- иконки ---------- */
const ICONS = {
  home: '<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="2"/>',
  chat: '<path d="M20.5 11.5a7.5 7.5 0 0 1-11.2 6.5L4 19.5l1.6-4.6A7.5 7.5 0 1 1 20.5 11.5z"/><path d="M8.5 10.5h7M8.5 13.5h4.5"/>',
  tricks: '<path d="M12 3.5l1.9 4.6 4.9.4-3.7 3.2 1.1 4.8L12 14l-4.2 2.5 1.1-4.8-3.7-3.2 4.9-.4z"/><path d="M5 20.5h14"/>',
  // 30.10, владелец: «не очень красивое сердечко» — переписка с близкими: облачко с сердцем (у «Чата» — облачко со строками)
  close: '<path d="M6.5 4h11A2.5 2.5 0 0 1 20 6.5v8a2.5 2.5 0 0 1-2.5 2.5h-6L7 20.5V17h-.5A2.5 2.5 0 0 1 4 14.5v-8A2.5 2.5 0 0 1 6.5 4z"/><path d="M12 13.6s-3.1-1.8-3.1-4a1.65 1.65 0 0 1 3.1-.8 1.65 1.65 0 0 1 3.1.8c0 2.2-3.1 4-3.1 4z"/>',
  ref: '<path d="M9 3.5l1.4 4.1 4.1 1.4-4.1 1.4L9 14.5l-1.4-4.1L3.5 9l4.1-1.4z"/><circle cx="18.5" cy="6" r="1.6"/><circle cx="17.5" cy="18.5" r="1.6"/><circle cx="6.5" cy="19.5" r="1.2"/><path d="m13.6 7.8 3.4-1.1M12.6 12.6l3.8 4.6M8.2 15.9l-1.1 2.3"/>',
  vault: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/><path d="M12 14.5v2.5"/>',
  // 28.10, владелец: «Платежи очень похожи на Заметки» — кошелёк вместо чека
  pay: '<path d="M5 7.5V6.8A2.3 2.3 0 0 1 7.3 4.5H17v3"/><rect x="3.5" y="7.5" width="17" height="12" rx="2.6"/><path d="M20.5 11.5h-4a2 2 0 0 0 0 4h4"/><circle cx="16.6" cy="13.5" r=".6"/>',
  notes: '<path d="M6.5 3.5h8l4 4v13h-12z"/><path d="M14.5 3.5v4h4M9 12h6M9 15.5h6M9 9h2.5"/>',
  course: '<path d="M3 9l9-4.5L21 9l-9 4.5z"/><path d="M7 11v4.5c0 1.4 2.2 2.8 5 2.8s5-1.4 5-2.8V11"/><path d="M21 9v5"/>',
  qa: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.8 1c0 1.7-2.4 2-2.4 3.6"/><path d="M12 17.2v.1"/>',
  family: '<circle cx="8" cy="7" r="2.6"/><circle cx="16" cy="7" r="2.6"/><circle cx="12" cy="13.5" r="2"/><path d="M3.5 20v-3.2A3.3 3.3 0 0 1 6.8 13.5h2.4M20.5 20v-3.2a3.3 3.3 0 0 0-3.3-3.3h-2.4M9 20v-1.2a3 3 0 0 1 6 0V20"/>',
  clients: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14a6.5 6.5 0 0 1 3.5 6"/>',
  mailing: '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M3.5 7l8.5 6 8.5-6"/>',
  sitechat: '<rect x="2.5" y="4" width="19" height="14" rx="2.5"/><path d="M2.5 8h19"/><circle cx="5" cy="6" r=".5"/><path d="M13.5 15.5a3 3 0 0 1 3-3h1a3 3 0 0 1 0 6h-2.2l-1.8 1.3z"/>',
  lessons: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9.2v5.6l4.8-2.8z"/>',
  team: '<rect x="3.5" y="7.5" width="17" height="12" rx="2.5"/><path d="M9 7.5V5.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5.5v2"/><path d="M9.2 13.4l2 2 3.6-3.6"/>',
  kids: '<circle cx="12" cy="13" r="7"/><path d="M7.2 8.4 6 4.5l3.6 2M16.8 8.4 18 4.5l-3.6 2"/><circle cx="9.6" cy="12.4" r="1.4"/><circle cx="14.4" cy="12.4" r="1.4"/><path d="M11 16h2"/>',
  music: '<path d="M9 18V5.5l10-2v12.5"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/><path d="M9 9.5l10-2"/>',
  personas: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.4 2.7-5.4 6-5.4s6 2 6 5.4"/><circle cx="17.2" cy="9" r="2.4"/><path d="M16 14.7c3 .2 5 1.8 5 5.3"/>',
  memory: '<circle cx="12" cy="12" r="2.6"/><circle cx="5" cy="6" r="1.8"/><circle cx="19" cy="6.5" r="1.8"/><circle cx="6" cy="18.5" r="1.8"/><circle cx="18.5" cy="18" r="1.8"/><path d="m6.5 7.2 3.6 3.2M17.5 7.6l-3.5 2.9M7.4 17.4l2.9-3.3M17 16.8l-2.9-3"/>',
  reminders: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 17.2h.01M12 17.2h.01"/>',
  prompter: '<rect x="3" y="4.5" width="18" height="12.5" rx="3"/><path d="M7.5 9h9M7.5 12.5h5.5"/><path d="M9.5 20.5h5"/>',
  tasks: '<path d="M10 6h10M10 12h10M10 18h10"/><path d="m3.5 6 1.5 1.5L8 4.5M3.5 12l1.5 1.5L8 10.5M3.5 18l1.5 1.5L8 16.5"/>',
  me: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.2 3.6-6.6 8-6.6s8 2.4 8 6.6"/>',
  diary: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3"/><path d="M15.5 7.2a2.6 2.6 0 1 1-3.1 3.6 2.1 2.1 0 0 0 3.1-3.6z"/>',
  soul: '<path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2z"/><path d="M18.5 2.5l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z"/>',
  const: '<path d="M6 3.5h9.5L19 7v13.5H6z"/><path d="M15 3.5V7h4"/><path d="M9 11h7M9 14h7M9 17h4.5"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  senior: '<path d="M12 20.5s-7.5-4.5-7.5-10a4.2 4.2 0 0 1 7.5-2.6 4.2 4.2 0 0 1 7.5 2.6c0 5.5-7.5 10-7.5 10z"/><path d="M8.5 12h2l1-2 1.6 4 1-2h1.4"/>',
  ideas: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2V16h5v-.1c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"/>',
  watch: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  pbot: '<path d="M21 4 3 11l6 2.4M21 4l-3 15.5-6.6-5M21 4 9 13.4v5.6l2.4-4.5"/>',
  council: '<circle cx="12" cy="6.2" r="2.4"/><circle cx="5" cy="13" r="2.2"/><circle cx="19" cy="13" r="2.2"/><path d="M8 20.5a4 4 0 0 1 8 0"/><path d="M12 10.5v3M7.2 14.6l2.6 1.6M16.8 14.6l-2.6 1.6"/>',
  docs: '<path d="M6 3.5h8l4 4V13"/><path d="M14 3.5v4h4"/><path d="M6 3.5v17h6"/><path d="M9 9h4M9 12.5h5"/><circle cx="16" cy="16.5" r="3"/><path d="m18.2 18.7 2.3 2.3"/>',
  dw: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 3.5v5M12 15.5v5M3.5 12h5M15.5 12h5"/>',
  devices: '<rect x="2.5" y="5" width="13" height="9.5" rx="1.8"/><path d="M1.5 17.5h11"/><rect x="16" y="8" width="5.5" height="11" rx="1.5"/><path d="M18.4 16.5h.7"/>',
  connect: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.4 1.4"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.4-1.4"/>',
  brain: '<path d="M12 3.5 13.9 8l4.6 1.9-4.6 1.9L12 16.4l-1.9-4.6-4.6-1.9L10.1 8z"/><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
  ears: '<path d="M4 12v0M8 8.5v7M12 5v14M16 8v8M20 11v2"/>',
  voice: '<path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z"/><path d="M15.5 9.5a3.5 3.5 0 0 1 0 5M18 7a7 7 0 0 1 0 10"/>',
  hands: '<path d="M14.5 6.5a4 4 0 0 0-5.3 5.3L3.5 17.5l3 3 5.7-5.7a4 4 0 0 0 5.3-5.3l-2.5 2.5-2.3-.7-.7-2.3z"/>',
  skills: '<path d="m12 3 9 4.6-9 4.6-9-4.6z"/><path d="m3 12.2 9 4.6 9-4.6M3 16.6l9 4.6 9-4.6"/>',
  look: '<path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.9-.8 1.9-1.8 0-.5-.2-.9-.5-1.3-.3-.3-.5-.7-.5-1.2 0-1 .8-1.8 1.8-1.8h2.1a3.7 3.7 0 0 0 3.7-3.7C20.5 6.9 16.7 3.5 12 3.5z"/><circle cx="7.6" cy="11" r="1.1"/><circle cx="10" cy="7.4" r="1.1"/><circle cx="14.4" cy="7.4" r="1.1"/>',
  sound: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  about: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.01"/>',
  servers: '<rect x="3.5" y="4" width="17" height="6.5" rx="2"/><rect x="3.5" y="13.5" width="17" height="6.5" rx="2"/><path d="M7.5 7.3h.01M7.5 16.8h.01M11 7.3h5.5M11 16.8h5.5"/>',
  safety: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.3 7.5 9.5 4.3-1.2 7.5-4.9 7.5-9.5V6z"/><path d="m8.8 12 2.3 2.3 4.3-4.6"/>',
  features: '<rect x="3.5" y="5" width="17" height="6" rx="3"/><circle cx="17.5" cy="8" r="1.6"/><rect x="3.5" y="13" width="17" height="6" rx="3"/><circle cx="6.5" cy="16" r="1.6"/>',
};
$$("nav button[data-p]").forEach(b => { const i = b.dataset.p === "diary" ? ICONS.soul : ICONS[b.dataset.p]; if (i) b.insertAdjacentHTML("afterbegin", `<svg class="ni" viewBox="0 0 24 24">${i}</svg>`); });
// заголовок с id переписывается кодом целиком (textContent) — значок в нём не выжил бы, такие пропускаем
$$("main section[id^='p-']").forEach(s => { const i = ICONS[s.id.slice(2)], h = s.querySelector("h1"); if (i && h && !h.id) h.insertAdjacentHTML("afterbegin", `<svg class="hi" viewBox="0 0 24 24">${i}</svg>`); });
/* «?» у заголовка каждого раздела — как он работает, как настроить, что сказать голосом */
// раздел студии → раздел руководства на сайте (server/dwrapp/guide.php, текст — data/guide.json)
const GUIDE_URL = "https://dewiar.pro/dwrapp/guide.php";
const GUIDE_OF = { ideas: "ideas", devices: "sync", personas: "personas", memory: "notes-memory", calendar: "calendar-money", close: "close", ref: "invite-friend", notes: "notes-memory", music: "music", pay: "payments", vault: "vault", snapshot: "snapshot", reminders: "reminders", tasks: "tasks",
  me: "notes-memory", folder: "folder-docs", docs: "my-docs", senior: "senior", watch: "watch", dw: "brain-account", connect: "install", brain: "brain-account", ears: "talk", voice: "voices",
  hands: "hands", skills: "skills-mcp-servers", sound: "talk", servers: "skills-mcp-servers", safety: "privacy", prompter: "prompter", about: "troubleshooting" };
function showHelp(k) {
  const H = (window.DEWIAR_HELP || {})[k]; if (!H) return;
  const li = (a) => (a || []).map(x => `<li>${escH(x)}</li>`).join("");
  const tries = (H.try || []).map((x, i) => `<div class="try"><div><b>«${escH(x.say)}»</b><span>→ ${escH(x.get)}</span></div>${x.noplay ? "" :
    `<button class="tplay" data-i="${i}" title="Отправить ассистенту">${SVG('<path d="M8 5.5v13l10.5-6.5z"/>')}</button>`}</div>`).join("");
  $("#help-body").innerHTML = `<h2>${escH(H.title)}</h2><h4>Что это</h4><p>${escH(H.what)}</p>` +
    (H.how && H.how.length ? `<h4>Как пользоваться</h4><ul>${li(H.how)}</ul>` : "") +
    (tries ? `<h4>Попробуйте</h4><p class="hint" style="margin:-2px 0 8px">Скажите голосом или нажмите ▶ — фраза уйдёт ассистенту.</p>${tries}` : "") +
    (H.say && H.say.length ? `<h4>Скажите голосом</h4><ul class="say">${li(H.say)}</ul>` : "") +
    (H.tips && H.tips.length ? `<h4>Советы</h4><ul>${li(H.tips)}</ul>` : "") +
    `<p class="hguide"><a href="${GUIDE_URL}#${GUIDE_OF[k] || ""}" target="_blank" rel="noopener">Подробное руководство с примерами и снимками экрана</a></p>`;
  $$("#help-body .tplay").forEach(b => b.onclick = async () => {
    const x = H.try[+b.dataset.i]; b.disabled = true;
    try { await core.call("say", { text: x.say }); toast("Отправил ассистенту — смотрите виджет"); } catch (e) { toast(e.message); }
    setTimeout(() => b.disabled = false, 1500);
  });
  $("#help").classList.add("open");
}
$$("main section[id^='p-']").forEach(s => {
  const k = s.id.slice(2), h = s.querySelector("h1"); if (!h || !(window.DEWIAR_HELP || {})[k]) return;
  if (h.id) { const sp = document.createElement("span"); sp.id = h.id; h.removeAttribute("id"); sp.append(...h.childNodes); h.appendChild(sp); }   // id переезжает на вложенный span: код меняет текст в нём и не затирает кнопку «?»
  const b = document.createElement("button"); b.className = "hbtn"; b.textContent = "?"; b.title = "Как работает этот раздел";
  b.onclick = (e) => { e.stopPropagation(); showHelp(k); }; h.appendChild(b);
});
$("#help-x").onclick = () => $("#help").classList.remove("open");
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#help").classList.remove("open"); });
document.querySelectorAll("nav button[data-p]").forEach(b => b.addEventListener("click", () => $("#help").classList.remove("open")));   // другой раздел — справка прошлого закрывается
