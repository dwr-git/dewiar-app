/* Студия Dewiar, «Клиенты» → вкладка «CRM» (0.69; запрос бизнеса 29.10: «связать с лидами в CRM — Битрикс24»).
   Не подключено — два пути: Битрикс24 (входящий вебхук: три шага, где его взять) и свой вебхук (Make, n8n, обработчик
   amoCRM — POST JSON). Подключено — адрес портала (ключ студия не видит), «Новых клиентов — сразу в CRM», «Проверить»,
   «Отключить». В карточке клиента — кнопка «В Битрикс24» и отметка «лид №…». Ядро — crm.py: crm_get/connect/forget/auto/test/send. */
let CRM_ST = null;
async function crmState() {
  try { CRM_ST = await core.call("crm_get"); } catch (e) { CRM_ST = null; }
  if (CR && CR.card && $("#cr-card")) crCard();
  return CRM_ST;
}

async function crmLoad() {
  const st = await crmState(), box = $("#crm-wrap"); if (!box) return;
  if (!st || !st.connected) {
    box.innerHTML = `<div class="crm-grid">
      <form class="crm-card" id="crm-bx"><h3>Битрикс24</h3>
        <p>Клиент уходит лидом: имя, компания, телефон, почта и о чём договорились. Новые записи потом добавляются в его ленту комментариями.</p>
        <ol class="crm-steps"><li>В Битрикс24 откройте «Приложения» → «Разработчикам» → «Другое» → «Входящий вебхук».</li>
          <li>В «Настройке прав» отметьте «CRM» и сохраните.</li>
          <li>Скопируйте «Вебхук для вызова REST API» и вставьте сюда.</li></ol>
        <label class="f">Ссылка вебхука<input type="url" id="crm-bx-url" spellcheck="false" autocomplete="off" placeholder="https://ваш-портал.bitrix24.ru/rest/1/…/"></label>
        <button class="btn primary" type="submit">Подключить Битрикс24</button></form>
      <form class="crm-card" id="crm-wh"><h3>Своя CRM или таблица</h3>
        <p>Для amoCRM, Make, n8n, Zapier или своего сервера: на ссылку придёт POST с JSON — клиент, записи и событие «lead» или «update».</p>
        <label class="f">Ссылка вебхука<input type="url" id="crm-wh-url" spellcheck="false" autocomplete="off" placeholder="https://hook.eu1.make.com/…"></label>
        <button class="btn" type="submit">Подключить</button></form>
    </div>
    <p class="crm-note">Ссылка — это ключ к вашей CRM. Она хранится только на этом компьютере и в Dewiar больше никуда не уходит.</p>`;
    const go = (kind, inp) => async (e) => {
      e.preventDefault(); const url = $(inp).value.trim(); if (!url) return $(inp).focus();
      const b = e.target.querySelector("button"); b.disabled = true; b.textContent = "Проверяю…";
      try { await core.call("crm_connect", { kind, url }); toast("CRM подключена"); crmLoad(); }
      catch (er) { toast(er.message, 5000); b.disabled = false; b.textContent = kind === "bitrix" ? "Подключить Битрикс24" : "Подключить"; }
    };
    $("#crm-bx").onsubmit = go("bitrix", "#crm-bx-url");
    $("#crm-wh").onsubmit = go("webhook", "#crm-wh-url");
    return;
  }
  const last = st.last;
  const lastTxt = !last ? "Пока ничего не отправлялось." : last.ok
    ? `Последним ушёл ${escH(last.name || "клиент")} — ${new Date(last.at * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}.`
    : `<span class="crm-bad">Новый клиент не ушёл: ${escH(last.err || "ошибка")}</span>`;
  box.innerHTML = `<div class="crm-card crm-on"><div class="crm-head"><i class="crm-dot" aria-hidden="true"></i><div><h3>${escH(st.name)} подключён</h3><small>${escH(st.host)}</small></div></div>
    <label class="crm-tg"><span><b>Новых клиентов — сразу в CRM</b><small>Карточка, заведённая голосом или здесь, уйдёт лидом сама.</small></span>
      <span class="tg"><input type="checkbox" id="crm-auto" aria-label="Новых клиентов — сразу в CRM"${st.auto ? " checked" : ""}><i></i></span></label>
    <p class="crm-note">${lastTxt} Отдельного клиента можно отправить кнопкой в его карточке или голосом: «передай Иванова в Битрикс».</p>
    <div class="actions"><button class="btn" id="crm-test">Проверить связь</button><button class="btn danger" id="crm-off">Отключить</button></div></div>`;
  $("#crm-auto").onchange = (e) => core.call("crm_auto", { on: e.target.checked }).then(() => toast(e.target.checked ? "Новые клиенты будут уходить сами" : "Только по кнопке")).catch(er => toast(er.message));
  $("#crm-test").onclick = () => core.call("crm_test").then(() => toast("Связь есть")).catch(er => toast(er.message, 5000));
  $("#crm-off").onclick = async () => { if (!await ask(`Отключить ${st.name}? Клиенты в Dewiar останутся, в CRM — тоже.`, { ok: "Отключить" })) return;
    core.call("crm_forget").then(() => { toast("Отключено"); crmLoad(); }).catch(er => toast(er.message)); };
}

window.crmCardBtn = (c) => {
  if (!CRM_ST || !CRM_ST.connected) return "";
  const where = CRM_ST.kind === "bitrix" ? "Битрикс24" : "CRM";
  const sent = c.crm && c.crm.kind === CRM_ST.kind && c.crm.host === CRM_ST.host;
  return `<button class="btn small" id="cr-crm" title="${sent ? `Уже в ${where} (№${escH(c.crm.id)}) — добавить новые записи` : `Завести лид в ${where}`}">${sent ? `В ${where} · №${escH(c.crm.id)}` : `В ${where}`}</button>`;
};
window.crmCardBind = (c) => {
  const b = $("#cr-crm"); if (!b) return;
  b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await core.call("crm_send", { id: c.id });
      toast(r.new ? `Лид №${r.id} заведён` : r.n ? `Добавлено записей: ${r.n}` : "Всё уже там — новых записей нет", 3000);
      if (r.client && CR.cur === c.id) { CR.card = r.client; crCard(); }
    } catch (e) { toast(e.message, 5000); b.disabled = false; }
  };
};
window.crmLoad = crmLoad;
window.crmState = crmState;
