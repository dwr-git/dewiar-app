//@ Телефон и веб-версия, часть 12: инструменты модели, руки в других приложениях, камера, интернет.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- инструменты модели ---------- */
const O = (props, req) => ({ type: "object", properties: props, required: req || [] });
const STR = { type: "string" }, NUM = { type: "number" };

/* ---------- руки в других приложениях: служба специальных возможностей (Hands.java) ----------
   Модель открывает приложение (open_app), читает экран (phone_screen — элементы с номерами), нажимает, вводит, листает.
   После каждого действия к ответу инструмента прикладывается свежий экран — модели не нужен лишний круг на чтение.
   Служба выключена — инструмент отвечает, как её включить (Настройки → Ещё → «Управлять приложениями»). */
let handsAsked = 0;
const HANDS_OFF = "Управление другими приложениями выключено. Скажи пользователю одной-двумя фразами: чтобы я мог(ла) нажимать в других приложениях, "
  + "включите это один раз — Настройки Dewiar → Ещё → «Управлять приложениями» → в списке «Специальные возможности» выберите Dewiar и включите; "
  + "если Dewiar там серый — сначала Настройки → Приложения → Dewiar → ⋮ → «Разрешить ограниченные настройки». "
  + "Не выполняй просьбу другим способом и не притворяйся, что сделал(а).";
/* №529 (04.11, Xiaomi, обновление 0.9.16 → 0.9.21): «С последним обновлением абсолютно отказывается что-либо делать».
   После обновления приложения Android (особенно MIUI/HyperOS) выключает или не запускает заново службу «Управлять
   приложениями» — модель открывала «Настройки», получала «выключено» и останавливалась, а человек был уверен, что всё
   включено («всё у тебя открыто»). Теперь телефон помнит, что руки работали (S.handsOk), и говорит прямо: выключилось
   после обновления — включите снова; включено, но служба не запущена — выключите и включите. При запуске — строка в журнал. */
function handsOff() {
  const st = typeof D.handsState === "function" ? D.handsState() : "";
  const tail = " Не выполняй просьбу другим способом и не притворяйся, что сделал(а).";
  if (st === "pending") return "«Управлять приложениями» включено в настройках Android, но служба не запустилась — так бывает после обновления приложения. "
    + "Скажи пользователю одной-двумя фразами: Настройки Android → Специальные возможности → Dewiar — выключить и включить снова (или Настройки Dewiar → Ещё → «Управлять приложениями»)." + tail;
  if (S.handsOk) return "«Управлять приложениями» выключилось — после обновления приложения Android часто отключает эту службу сам. "
    + "Скажи пользователю одной-двумя фразами: включите снова — Настройки Dewiar → Ещё → «Управлять приложениями» → в «Специальных возможностях» выберите Dewiar и включите; "
    + "если Dewiar там серый — сначала Настройки → Приложения → Dewiar → ⋮ → «Разрешить ограниченные настройки»." + tail;
  return HANDS_OFF;
}
/* при запуске и возвращении в приложение: руки работают — запоминаем; работали, а теперь нет — в журнал и карточкой */
let handsLogged = false, handsCardShown = false;
function handsWatch(boot) {
  if (D.web || typeof D.handsState !== "function") return;
  let st = ""; try { st = D.handsState(); } catch (e) { return; }
  if (boot) plog("info", "🖐 управлять приложениями: " + ({ on: "включено", pending: "включено в Android, служба не запущена", none: "нет в этой сборке" }[st] || "выключено"));
  if (st === "on") { if (!S.handsOk) { S.handsOk = true; saveS(); } handsLogged = handsCardShown = false; return; }
  if (st === "none") { if (S.handsOk) { delete S.handsOk; saveS(); } return; }
  if (!S.handsOk) return;
  if (!handsLogged) { handsLogged = true; plog("warn", "🖐 «Управлять приложениями» работало, а теперь " + (st === "pending" ? "служба не запущена" : "выключено") + " — похоже, после обновления; прошу включить снова"); }
  if (handsCardShown || busy || $("#card").innerHTML || $(".sheet.on")) return;      // карточку — на свободный экран (или при следующем возвращении)
  handsCardShown = true;
  showCard(`<div class="card hands-lost"><p><b>Управлять приложениями — выключено.</b> ${st === "pending" ? "Android не запустил эту службу после обновления: выключите и снова включите Dewiar в «Специальных возможностях»." : "После обновления Android отключил эту службу. Включите её снова — и я опять смогу нажимать в других приложениях."}</p><button class="btn p w" id="hands-again">Включить</button></div>`);
  const b = $("#hands-again"); if (b) b.onclick = () => { handsAsked = Date.now(); if (!D.openSettings("accessibility")) toast("Откройте Настройки Android → Специальные возможности → Dewiar"); showCard(""); };
}
const HANDS_TOOLS = [
  { name: "phone_screen", description: "Прочитать, что сейчас на экране телефона (в любом приложении): название приложения и пронумерованные элементы — кнопки, поля ввода, тексты, списки. "
      + "Нужен, чтобы что-то сделать в другом приложении по просьбе пользователя: сначала open_app, потом phone_screen, потом phone_tap / phone_type / phone_scroll. "
      + "Перед последним шагом, который нельзя отменить (отправить сообщение или письмо, оплатить, купить, удалить, опубликовать), спроси подтверждение, если пользователь не просил прямо об этом действии. "
      + "Пароли и коды не вводи — попроси пользователя.", parameters: O({}) },
  { name: "phone_tap", description: "Нажать на экране: id — номер элемента из phone_screen, или text — надпись на экране. long — долгое нажатие. В ответ — что стало на экране.",
    parameters: O({ id: NUM, text: STR, long: { type: "boolean" } }) },
  { name: "phone_type", description: "Ввести текст в поле: id — номер поля из phone_screen (без id — поле с курсором или первое на экране). submit true — нажать «Ввод» (поиск). Текст заменяет то, что было в поле. В ответ — что стало на экране.",
    parameters: O({ id: NUM, text: STR, submit: { type: "boolean" } }, ["text"]) },
  { name: "phone_scroll", description: "Пролистать экран или список: dir down (дальше) | up (назад); id — номер списка (необязательно). В ответ — что стало на экране.",
    parameters: O({ dir: { type: "string", enum: ["down", "up"] }, id: NUM }, ["dir"]) },
  { name: "phone_nav", description: "Системные кнопки: back — назад, home — домой, recents — недавние приложения, notifications — шторка уведомлений, dewiar — вернуться в Dewiar.",
    parameters: O({ action: { type: "string", enum: ["back", "home", "recents", "notifications", "dewiar"] } }, ["action"]) },
];
const HANDS_SET = new Set(HANDS_TOOLS.map(t => t.name));
const HANDS_PAGE = "https://dewiar.pro/dwrapp/download.php";
/* №818 (17.11, Олег: «скачать версию с руками — ссылка не работает», ERR_TOO_MANY_REDIRECTS): постоянного файла
   Dewiar-hands.apk на сайте может не быть (его кладёт «Опубликовать», когда загружены оба APK) — тогда сайт уводил по кругу.
   Берём файл из описания выпуска (latest.json, то же, что обновление); нет его — страница «Скачать» и честная подсказка. */
async function handsUrl() {
  try {
    const a = (JSON.parse((await http("GET", UPD_URL, { timeout: 8000 })).body || "{}").android) || {};
    if (a.hands_apk) return UPD_URL.replace(/latest\.json$/, a.hands_apk);
  } catch (e) { }
  return "";
}
function handsCard() {
  const st = typeof D.handsState === "function" ? D.handsState() : "";
  if (st === "none") return `<p class="hint" style="margin:0 0 10px">Ассистент может сам нажимать кнопки, вводить текст и листать в других приложениях: «напиши маме в Telegram…», «найди в YouTube…». Для этого нужна расширенная версия Dewiar — она ставится поверх этой, всё сохранится.
    Android предупредит, что приложение просит «специальные возможности»: так он встречает любое приложение не из магазина, которое умеет нажимать за вас. Если установка не идёт — Настройки → Google → Play Защита → на время выключить проверку приложений.</p>
    <button class="btn p w" id="hands-dl">Скачать версию с «руками»</button>`;
  if (st === "on") return `<div class="row2"><span class="res ok" style="flex:1;margin:0">Включено</span><button class="btn" id="hands-go">Настройки</button></div>
    <p class="hint" style="margin:8px 0 0">Просите голосом: «напиши маме в Telegram, что я задержусь», «найди в YouTube новости», «включи вайфай». Перед отправкой, оплатой и удалением ассистент спросит. Пароли не читаются и не вводятся.</p>`;
  if (st === "pending") return `<p class="hint" style="margin:0 0 10px">Включено в настройках Android — подключается…</p><button class="btn p w" id="hands-go">Настройки</button>`;
  // Android 13+: приложения не из магазина в «Специальных возможностях» серые («Ограниченная настройка») — сначала
  // разрешить их на странице Dewiar (отчёт №87, 18.10: «почему нельзя выбрать помощника» — Dewiar серый в списке)
  const back = handsAsked && Date.now() - handsAsked < 10 * 60000;
  // Идея №144 (05.11): «новичок пять раз переключался между экранами и не понимал, что включать» — по шагам, с названиями
  // пунктов как на экране, у Xiaomi, Samsung, Huawei — их подписи; серый Dewiar и «Ограниченная настройка» — отдельно
  const dev = handsDevice(), where = HANDS_WHERE[dev] || HANDS_WHERE[""];
  const s13 = androidSdk() >= 33;
  return `<p class="hint" style="margin:0 0 10px">Ассистент сможет сам нажимать кнопки, вводить текст и листать в других приложениях — по вашей просьбе голосом: «напиши маме в Telegram…», «найди в YouTube…». Включается один раз, около минуты:</p>
    ${back ? `<p class="res bad" style="margin:0 0 10px">Не включилось? Если Dewiar в списке серый или пишет «Ограниченная настройка» — это защита Android 13+ для приложений не из Google Play: сделайте шаг 1 и потом снова шаг 2.</p>` : ""}
    <ol class="steps hsteps hguide">
      ${s13 ? `<li><b>Снимите защиту Android 13+.</b> Нажмите «1. Страница Dewiar» → откроется «О приложении» → вверху справа <b>⋮</b> → <b>«Разрешить ограниченные настройки»</b> → подтвердите отпечатком или PIN-кодом.
        <small>Пункта ⋮ нет? Сначала сделайте шаг 2 и нажмите на серый Dewiar — Android скажет «Ограниченная настройка»; закройте окно, вернитесь сюда и снова «1. Страница Dewiar» — ⋮ появится.</small></li>` : ""}
      <li><b>Включите Dewiar в «Специальных возможностях».</b> Нажмите «${s13 ? "2. " : ""}Включить» → откроются «Специальные возможности» → <b>«${where[0]}»</b>${where[1]} → <b>Dewiar</b> → переключатель <b>«Использовать Dewiar»</b> → <b>«Разрешить»</b>.
        <small>Не видите Dewiar — прокрутите вниз: он в разделе «${where[0]}», а не среди системных служб.</small></li>
      <li><b>Вернитесь в Dewiar</b> (кнопка «Назад»): здесь появится «Включено». Проверьте: «Лира, открой YouTube и найди новости».</li>
    </ol>
    <details class="hfaq"><summary>Что-то не так?</summary>
      <p><b>Dewiar серый, переключатель не нажимается.</b> Это «Ограниченная настройка» Android 13+ — сделайте шаг 1.</p>
      <p><b>Включил, а через время снова выключено.</b> Android и оптимизация батареи иногда отключают службу после обновления. Включите снова; на Xiaomi — ещё «Автозапуск» и «Без ограничений» в «Контроле активности» для Dewiar.</p>
      <p><b>Страшное предупреждение «полный контроль над устройством».</b> Так Android пишет про любое приложение, которое умеет нажимать за вас. Dewiar нажимает только по вашей просьбе, пароли не читает и не вводит, перед отправкой, оплатой и удалением спрашивает.</p>
    </details>
    ${s13 ? `<div class="row2"><button class="btn p" id="hands-app" style="flex:1">1. Страница Dewiar</button><button class="btn" id="hands-go" style="flex:1">2. Включить</button></div>`
      : `<div class="row2"><button class="btn p" id="hands-go" style="flex:1">Включить</button></div>`}`;
}
/* Где в «Специальных возможностях» лежат службы скачанных приложений — у разных марок по-разному (идея №144) */
const HANDS_WHERE = {          // [пункт, пояснение]
  xiaomi: ["Скачанные приложения", " (на старых MIUI — «Расширенные настройки» → «Спец. возможности»)"],
  samsung: ["Установленные приложения", ""],
  huawei: ["Загруженные службы", ""],
  "": ["Скачанные приложения", " (или «Установленные службы», «Загруженные службы» — смотря какой телефон)"],
};
function handsDevice() {
  let d = ""; try { d = String(JSON.parse(D.info() || "{}").device || "").toLowerCase(); } catch (e) { }
  return /xiaomi|redmi|poco/.test(d) ? "xiaomi" : /samsung/.test(d) ? "samsung" : /huawei|honor/.test(d) ? "huawei" : "";
}
function androidSdk() { try { return +JSON.parse(D.info() || "{}").sdk || 0; } catch (e) { return 0; } }
function wireHands() {
  const dl = $("#hands-dl");
  if (dl) dl.onclick = async () => {
    const u = await handsUrl();
    if (u) return D.openUrl(u);
    toast("Версию с управлением приложениями ещё не выложили на сайт — открываю страницу «Скачать»: загляните чуть позже", 6000);
    D.openUrl(HANDS_PAGE);
  };
  const b = $("#hands-go");
  if (b) b.onclick = () => { handsAsked = Date.now(); if (!D.openSettings("accessibility")) toast("Откройте Настройки Android → Специальные возможности → Dewiar"); };
  const ap = $("#hands-app");
  if (ap) ap.onclick = () => { handsAsked = Date.now(); if (!D.openSettings("app")) toast("Настройки → Приложения → Dewiar → ⋮ → «Разрешить ограниченные настройки»"); };
}
async function handsAfter(res) {
  // действие сделано — экран меняется не сразу: ждём и прикладываем свежий экран (модели не нужен лишний круг)
  if (res === "OFF") return handsOff();
  if (/^Ошибка|^Пароли/.test(res)) return res;
  await sleep(900);
  const scr = D.handsScreen();
  return scr === "OFF" ? res : res + "\n\nТеперь на экране:\n" + scr;
}
async function handsTool(name, a) {
  if (name === "phone_screen") { const r = D.handsScreen(); if (r !== "OFF" && !S.handsOk) { S.handsOk = true; saveS(); } return r === "OFF" ? handsOff() : r; }
  if (name === "phone_tap") {
    const id = Math.round(+a.id || 0);
    if (!id && !a.text) return "Ошибка: укажи id элемента из phone_screen или text — надпись на экране.";
    return handsAfter(id ? D.handsTap(id, !!a.long) : D.handsTapText(String(a.text)));
  }
  if (name === "phone_type") return handsAfter(D.handsType(Math.round(+a.id || 0), String(a.text || ""), !!a.submit));
  if (name === "phone_scroll") return handsAfter(D.handsScroll(Math.round(+a.id || 0), a.dir === "up" ? "up" : "down"));
  if (name === "phone_nav") {
    if (a.action === "dewiar") { D.toFront(); return "Dewiar снова на экране."; }
    return handsAfter(D.handsNav(String(a.action || "back")));
  }
  return "Ошибка: неизвестное действие.";
}

/* Калькулятор модели (как tools.calc_eval на компьютере): числа, + - * / % ( ), 17% → 0.17, round abs min max sqrt,
   даты days_until / days_between / weekday / date_add. Свой разбор — без eval. */
// Бюджет, лимит, «заложим 70 тысяч» — план, а не трата (как core/tools.py is_plan)
function isPlanMoney(t) {
  return /(?:^|[^а-яё])(?:бюджет|лимит)[а-яё]*\s+(?:на|для)(?![а-яё])|^\s*(?:бюджет|лимит|план)|заложи|запланир|планиру|(?:увелич|уменьш|повыш|сниж)[а-яё]*\s+(?:с|до)\s+\d/i.test(t || "")
    && !/из бюджета|потрат|купил|оплат|заплат|получил|пришл|зарплат/i.test(t || "");
}
function calcEval(src) {
  const WD = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
  const day = (x) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(x)); if (!m) throw new Error(`дата «${x}» — нужна в виде ГГГГ-ММ-ДД`); return new Date(+m[1], +m[2] - 1, +m[3]); };
  const today = () => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const F = { round: (x, n) => +(+x).toFixed(n || 0), abs: Math.abs, min: Math.min, max: Math.max, sqrt: Math.sqrt, floor: Math.floor, ceil: Math.ceil,
    days_until: (x) => Math.round((day(x) - today()) / 864e5), days_between: (a, b) => Math.round((day(b) - day(a)) / 864e5),
    weekday: (x) => WD[day(x).getDay()], date_add: (x, n) => { const d = day(x); d.setDate(d.getDate() + (+n)); return iso(d); }, today: () => iso(today()) };
  let s = String(src).replace(/×/g, "*").replace(/÷/g, "/").replace(/\^/g, "**").replace(/(\d)\s+(?=\d{3}\b)/g, "$1").replace(/(\d),(\d)/g, "$1.$2");
  if (!s.trim() || s.length > 300) throw new Error("пустое или слишком длинное выражение");
  const toks = s.match(/\d+(?:\.\d+)?|"[^"]*"|[A-Za-z_]+|\*\*|[-+*/%(),]|\S/g) || [];
  let i = 0;
  const peek = () => toks[i], eat = (t) => { if (toks[i] !== t) throw new Error(`ожидалось «${t}»`); i++; };
  const prim = () => {
    const t = toks[i++];
    if (t === undefined) throw new Error("выражение оборвалось");
    if (t === "(") { const v = expr(); eat(")"); return v; }
    if (t === "-") return -unary();
    if (t === "+") return unary();
    if (/^\d/.test(t)) { let v = +t; if (peek() === "%" && !/^[\d(]/.test(toks[i + 1] || "")) { i++; v /= 100; } return v; }
    if (t[0] === '"') return t.slice(1, -1);
    if (F[t] && peek() === "(") { i++; const args = []; if (peek() !== ")") { args.push(expr()); while (peek() === ",") { i++; args.push(expr()); } } eat(")"); return F[t](...args); }
    throw new Error("можно только числа, + - * / % ( ) и функции: " + Object.keys(F).join(", "));
  };
  const unary = () => prim();
  const pow = () => { const b = unary(); if (peek() === "**") { i++; const e = pow(); if (Math.abs(e) > 100) throw new Error("слишком большая степень"); return b ** e; } return b; };
  const term = () => { let v = pow(); for (;;) { const t = peek(); if (t === "*" || t === "/" || t === "%") { i++; const r = pow(); if ((t === "/" || t === "%") && r === 0) throw new Error("деление на ноль"); v = t === "*" ? v * r : t === "/" ? v / r : v % r; } else return v; } };
  const expr = () => { let v = term(); for (;;) { const t = peek(); if (t === "+" || t === "-") { i++; const r = term(); v = t === "+" ? v + r : v - r; } else return v; } };
  const v = expr();
  if (i < toks.length) throw new Error(`не понял: «${toks.slice(i).join(" ")}»`);
  return v;
}

function toolSpecs() {
  if (S.llm.trial) return [];                     // пробный разговор на сайте — без действий (сервер их и не пропустит)
  const t = [
    { name: "set_reminder", description: "Поставить напоминание, будильник или таймер. when — когда, словами пользователя («через 20 минут», «завтра в 9», «в пятницу в 18:30», «27 октября в 10») — время посчитает телефон по своим часам, сам не считай; at — дата и время ISO (ГГГГ-ММ-ДДTЧЧ:ММ, местное) — только если when не подходит. kind: reminder | alarm (будильник) | timer. repeat: '' | daily | weekdays | weekly; дни недели («по будням, кроме пятницы», «пн-чт», «по понедельникам и средам») — словами в when, телефон поймёт сам.",
      parameters: O({ text: STR, when: STR, at: STR, in_minutes: NUM, kind: { type: "string", enum: ["reminder", "alarm", "timer"] }, repeat: { type: "string", enum: ["", "daily", "weekdays", "weekly"] } }, ["text"]) },
    { name: "list_reminders", description: "Какие напоминания и будильники стоят.", parameters: O({}) },
    { name: "calc", description: "Посчитать точно: любые вычисления (проценты, суммы, скидки, деление) и даты. Считай ВСЕГДА этим инструментом, не в уме. Выражение: 2350 * 17 / 100, (1200 - 15%) * 3; даты ГГГГ-ММ-ДД: days_until(\"2027-01-01\") — сколько дней до даты (таймер «на столько же минут» — in_minutes равно этому числу), days_between(\"2026-10-01\", \"2026-12-31\"), weekday(\"2026-10-14\").",
      parameters: O({ expression: STR }, ["expression"]) },
    { name: "cancel_reminder", description: "Отменить напоминание или будильник (id из list_reminders или слова из текста).", parameters: O({ id: STR }, ["id"]) },
    { name: "mark_done", description: "Отметить дела сделанными: пользователь говорит, что сделал («я позвонила Игорю и сделала тренировку», «отметь как исполненное», «готово, купил хлеб»). items — каждое дело отдельно и коротко, как оно называется («Позвонить Игорю», «Тренировка»); подходящее напоминание на сегодня закроется само. undo: true — снять отметку, если отметили по ошибке.",
      parameters: O({ items: { type: "array", items: STR }, undo: { type: "boolean" } }, ["items"]) },
    { name: "done_report", description: "Что пользователь сделал и его достижения: days — за сколько дней (1 — сегодня, 7 — неделя). Для «что я сегодня сделал», «сколько дел за неделю», «какие у меня достижения».", parameters: O({ days: NUM }) },
    { name: "call", description: "Позвонить по телефону: who — имя из контактов («мама», «Лёша») или номер. Человеку из «Близких» звони через close_call.", parameters: O({ who: STR }, ["who"]) },
    { name: "send_sms", description: "Подготовить SMS: who — имя или номер, text — текст. Откроется приложение сообщений, отправит пользователь.", parameters: O({ who: STR, text: STR }, ["text"]) },
    { name: "open_app", description: "Открыть приложение на телефоне по названию.", parameters: O({ name: STR }, ["name"]) },
    { name: "route", description: "Маршрут на карте: «как дойти до…», «проложи маршрут», «построй пешком дворами», геоточка или ссылка на карту. to — куда: адрес с городом, место или координаты, ссылка на карту; from — откуда (пусто — от того места, где пользователь сейчас); mode — walk (пешком, по умолчанию) | transit | car | bike; app — yandex | google (пусто — какие карты стоят). Карта сама строит кратчайший путь (пешком — и дворами); не выдумывай улицы и время.",
      parameters: O({ to: STR, from: STR, mode: { type: "string", enum: ["walk", "transit", "car", "bike"] }, app: { type: "string", enum: ["yandex", "google"] } }, ["to"]) },
    { name: "calendar_list", description: "Календарь телефона (Google и другие календари человека): что запланировано. from — с какого дня ГГГГ-ММ-ДД (пусто — сегодня), days — на сколько дней (1 — один день, 7 — неделя), query — слово для поиска («Игорь», «стоматолог»). Для «что у меня завтра», «когда встреча с …», «свободен ли я в пятницу». Отвечай по найденному, не выдумывай встреч.",
      parameters: O({ from: STR, days: NUM, query: STR }) },
    { name: "calendar_add", description: "Записать встречу в календарь телефона — когда просят записать в календарь или назначить встречу (просто «запомни» — это remember). title — что, start — начало ГГГГ-ММ-ДДTЧЧ:ММ (местное; только дата — на весь день), minutes — длительность (по умолчанию 60), location — где. Первый вызов ничего не записывает — он скажет, о чём спросить; после «да» пользователя вызови снова с теми же данными и confirmed: true.",
      parameters: O({ title: STR, start: STR, minutes: NUM, location: STR, confirmed: { type: "boolean" } }, ["title", "start"]) },
    { name: "open_url", description: "Открыть сайт или ссылку в браузере (YouTube, карты, поиск). Не для радио — для него play_radio.", parameters: O({ url: STR }, ["url"]) },
    { name: "play_radio", description: "Включить радио онлайн прямо здесь, в приложении: query — название станции («Европа Плюс», «Маяк», «Рекорд»), жанр или настроение («джаз», «рок», «классика», «что-нибудь спокойное»), пусто — на мой вкус. На любую просьбу про радио или «включи музыку» — только этот инструмент: не открывай сайты, Яндекс Музыку и другие приложения.",
      parameters: O({ query: STR }) },
    { name: "radio_control", description: "Радио, которое уже играет здесь: pause — пауза, resume — продолжить, stop — выключить, next — другая станция, prev — предыдущая (та, что играла до этой).",
      parameters: O({ action: { type: "string", enum: ["pause", "resume", "stop", "next", "prev"] } }, ["action"]) },
    { name: "media_control", description: "Кнопки плеера ДРУГОГО приложения на телефоне (Яндекс Музыка, Spotify, VK Музыка, YouTube Music) — как на наушниках: next — следующий трек, prev — предыдущий, pause — пауза, play — играть. Радио здесь, в приложении, — radio_control.",
      parameters: O({ action: { type: "string", enum: ["next", "prev", "pause", "play"] } }, ["action"]) },
    { name: "web_search", description: "Найти в интернете свежие сведения. Не выдумывай результаты.", parameters: O({ query: STR }, ["query"]) },
    { name: "show_images", description: "Показать картинки к тому, о чём рассказываешь (руны и орнаменты, животные, растения, картины, здания, места) — появятся на экране под ответом. Вызывай, когда это лучше увидеть или просят «покажи». query — 2–5 ключевых слов, лучше по-английски; count — 1–6 (обычно 3–4). Не говори «вот изображение», не вызвав инструмент.",
      parameters: O({ query: STR, count: NUM, caption: STR }, ["query"]) },
    { name: "read_webpage", description: "Прочитать страницу по ссылке (текст). Длинная — начало и места со словами find (или вопроса).",
      parameters: O({ url: STR, find: { type: "string", description: "что ищешь на длинной странице: «Доллар США», «15 октября»" } }, ["url"]) },
    { name: "world_time", description: "Который час сейчас в другом городе или стране (по часовому поясу). Время в других городах не считай в уме — только этим.", parameters: O({ city: STR }, ["city"]) },
    { name: "weather", description: "Погода сейчас и на ближайшие дни: city — город (если пользователь не назвал — из памяти о нём).", parameters: O({ city: STR, days: NUM }, ["city"]) },
    { name: "world_news", description: "Интересное в мире сегодня: подборка любопытных новостей (наука, космос, техника, природа, кино…) с учётом вкуса пользователя. Для «что интересного в мире?», «расскажи новость», «что нового в науке?». topic — тема, если назвал: science, space, tech, ai, health, nature, culture, money, travel, food, sport, curious.",
      parameters: O({ topic: STR }) },
    { name: "flashlight", description: "Фонарик: on true/false.", parameters: O({ on: { type: "boolean" } }, ["on"]) },
    { name: "phone_settings", description: "Открыть нужный экран настроек телефона: bluetooth, wifi, internet (Wi‑Fi и мобильный интернет), nfc, airplane (режим полёта), display (яркость, экран), sound, data (мобильная сеть), hotspot (точка доступа), location (геолокация). Включить или выключить Bluetooth, Wi‑Fi, режим полёта приложениям Android сам не даёт — открой экран этим инструментом; дальше переключатель нажимают руки (phone_screen, phone_tap) или пользователь.",
      parameters: O({ section: { type: "string", enum: Object.keys(PHONE_SET) } }, ["section"]) },
    { name: "take_photo", description: "Сфотографировать камерой телефона и посмотреть на снимок: camera front — фронтальная (на пользователя: «сфотографируй меня», «как я выгляжу»), back — основная (на то, что перед телефоном: «что это», «прочитай надпись»). Снимок придёт следующим сообщением — опиши его или ответь на вопрос.",
      parameters: O({ camera: { type: "string", enum: ["front", "back"] }, question: STR }) },
    { name: "set_volume", description: "Громкость: action up|down|set|mute|unmute, percent для set.", parameters: O({ action: { type: "string", enum: ["up", "down", "set", "mute", "unmute"] }, percent: NUM }, ["action"]) },
    { name: "battery", description: "Заряд батареи телефона.", parameters: O({}) },
    { name: "save_note", description: "Записать заметку или список (title — коротко, text — содержимое). folder — папка, только если её назвали («в папку Работа»).", parameters: O({ title: STR, text: STR, folder: STR }, ["title", "text"]) },
    { name: "find_notes", description: "Найти в заметках по словам.", parameters: O({ query: STR }, ["query"]) },
    ...(kidsOn() ? [] : [{ name: "suggest_idea", description: "Предложить идею разработчику Dewiar («Идеи Лиры»): когда просят «предложи идею…» или согласились предложить то, чего ты не умеешь. title — суть одной фразой, text — подробнее. Похожая уже есть — голос уйдёт за неё. Без согласия не вызывай.", parameters: O({ title: STR, text: STR }, ["title"]) }]),
    { name: "recall", description: "Вспомнить, о чём говорили и что делали за последние дни (журнал разговоров на телефоне и сделанное): «что мы делали на этой неделе», «о чём я спрашивал вчера». days — за сколько дней (1–14), query — слова для поиска (можно пусто).", parameters: O({ days: NUM, query: STR }) },
    { name: "open_made", description: "Открыть на экране то, что ты уже сделал на телефоне (make_app: калькулятор, игра, страница): «покажи калькулятор», «где программа, которую ты сделал». title — часть названия; пусто — последнее.", parameters: O({ title: STR }) },
    { name: "show_photo", description: "Снова показать на экране последний снимок с камеры (take_photo), с кнопкой «Сохранить».", parameters: O({}) },
    { name: "remember", description: "Запомнить надолго факт о пользователе одной фразой в третьем лице.", parameters: O({ fact: STR }, ["fact"]) },
    { name: "money_add", description: `Записать уже сделанный расход или полученный доход. Бюджет, лимит, план («бюджет на мебель — 50 тысяч», «заложим 70») — не расход: это remember. kind expense|income, amount — число, currency (по умолчанию ${CUR}), category по-русски, note.`,
      parameters: O({ kind: { type: "string", enum: ["expense", "income"] }, amount: NUM, currency: STR, category: STR, note: STR }, ["kind", "amount"]) },
    { name: "month_summary", description: "Итоги месяца пользователя («Мой месяц с Лирой»): сделанные дела и траты — когда спрашивают «как прошёл мой месяц», «итоги октября», «что я сделал за месяц». month — 2026-10, prev — прошлый, пусто — текущий.", parameters: O({ month: STR }) },
    { name: "money_report", description: "Итоги по деньгам: period today|week|month|year.", parameters: O({ period: { type: "string", enum: ["today", "week", "month", "year"] } }) },
    // идея №75 (30.10): «убрать ошибочную запись или дубль, поменять валюту — голосом нельзя»
    { name: "money_find", description: "Найти записи о деньгах, чтобы удалить или исправить («удали вчерашний кофе», «такси записалось дважды», «это было в гривнах»). date или from/to — ГГГГ-ММ-ДД (пусто — последний месяц), amount — сумма, text — слова из заметки или категории, currency — код. Потом — money_fix с id.",
      parameters: O({ date: STR, from: STR, to: STR, amount: NUM, text: STR, currency: STR }) },
    { name: "money_fix", description: "Удалить (action delete) или исправить (action update: amount, currency, category, note) записи по id из money_find. Первый вызов ничего не меняет — скажет, о чём спросить; после «да» пользователя вызови снова с теми же данными и confirmed: true.",
      parameters: O({ ids: { type: "array", items: STR }, action: { type: "string", enum: ["delete", "update"] }, amount: NUM, currency: STR, category: STR, note: STR, confirmed: { type: "boolean" } }, ["ids", "action"]) },
    { name: "call_persona", description: "Позвать другого персонажа команды по имени (он ответит своим голосом).", parameters: O({ name: STR }, ["name"]) },
    { name: "make_app", description: "Сделать мини-программу или страницу прямо на телефоне: калькулятор, игра, таймер, конвертер, викторина, шпаргалка, открытка, презентация (слайды листаются кнопками и свайпом). html — ОДИН самодостаточный HTML-файл: CSS и JS внутри, без внешних файлов и библиотек, компактный код; под экран телефона (крупные кнопки), тёмная тема, по-русски. title — короткое название. Программа сразу откроется на экране и сохранится в «Мой день» → «Сделанное».",
      parameters: O({ title: STR, html: STR }, ["title", "html"]) },
    ...(clLoad().people.length ? [{ name: "close_send", description: "Написать человеку из «Близких» (переписка между помощниками Dewiar: дойдёт в его приложение, его помощник скажет вслух). Только когда пользователь прямо просит написать, передать или сказать кому-то из близких. to — имя, как сказал пользователь («Андрею», «маме»); text — само сообщение от лица пользователя («Задержусь на полчаса»), без «передай». «Напомни всем в группе Семья в субботу в 10 про дачу» — to: группа, text: о чём («Едем на дачу»), remind_when: когда («в субботу в 10») — напоминание встанет у всех.",
      parameters: O({ to: STR, text: STR, remind_when: STR }, ["to", "text"]) },
      { name: "close_call", description: "Позвонить человеку из «Близких» через Dewiar (аудио или видео — video true). Только когда пользователь прямо просит позвонить кому-то из близких.", parameters: O({ to: STR, video: { type: "boolean" } }, ["to"]) },
      { name: "close_where", description: "Где сейчас близкий — по радару «Рядом» (только если он сам показывает вам своё место): сколько до него, в какую сторону, когда обновлено. «где мама?», «далеко ли Андрей?». who — имя.", parameters: O({ who: STR }, ["who"]) },
      { name: "close_wave", description: "Помахать близкому 👋 — у него на экране волны и голос «… машет вам». «помаши маме», «помаши Андрею рукой». to — имя.", parameters: O({ to: STR }, ["to"]) },
      { name: "close_read", description: "Последние сообщения от близких (и мои им): «что мне писали», «что ответила мама»; группа — «что ответили в группе Семья», «кто что берёт?» (собери ответы по людям). who — имя, группа или пусто — все.", parameters: O({ who: STR }) }] : []),
    { name: "app_help", description: "Руководство Dewiar — как пользоваться самим этим приложением: где кнопка или раздел, как настроить, как пригласить близкого или друга, сканер, стили, напоминания на часах, синхронизация, данные. Вызывай ПЕРВЫМ, когда спрашивают про Dewiar и его функции («как…», «где…», «есть ли у тебя…», «что ты умеешь…»: семейный бюджет, видеоуроки, близкие, устройства), — не выдумывай меню и не говори «такого нет», не проверив. query — о чём спросили.", parameters: O({ query: STR }, ["query"]) },
    { name: "scan_code", description: "Открыть сканер кодов камерой: QR, Aztec, печать Dewiar, штрихкоды и Data Matrix товаров. «Отсканируй код», «прочитай QR», «проверь честный знак». Результат обработается сам.", parameters: O({}) },
    { name: "send_message", description: "Отправить текст через мессенджер: app — max (по умолчанию), telegram, whatsapp, viber, vk; text — готовый текст сообщения. Откроется приложение, получателя выберет пользователь.",
      parameters: O({ app: { type: "string", enum: ["max", "telegram", "whatsapp", "viber", "vk"] }, text: STR }, ["text"]) },
  ];
  if (typeof D.handsState === "function") t.push(...HANDS_TOOLS);
  // №528: «Я уже работаю на актуальной версии» — не проверив. Версия и обновление — только этим действием
  if (!D.web && !kidsOn()) t.push({ name: "app_update", description: "Версия и обновление самого Dewiar на этом телефоне: check — узнать, какая версия стоит и есть ли новее (с сайта dewiar.pro); install — проверить и, если есть новее, обновить (скачается и откроется установка). Вызывай на любой вопрос о версии приложения или просьбу обновиться. Не говори «у меня последняя версия» и «я не могу обновиться», не вызвав его.",
    parameters: O({ action: { type: "string", enum: ["check", "install"] } }, ["action"]) });
  if (loggedIn()) t.push({ name: "ask_knowledge", description: "Спросить Знания пользователя на сайте Dewiar — его документы и папки, публичную библиотеку. Ответ с источниками. base — название папки или раздела, если пользователь его назвал.",
    parameters: O({ question: STR, base: STR }, ["question"]) });
  if (Object.keys(mind().tasks || {}).length) t.push({ name: "remove_task", description: "Удалить большую задачу из «Мой день» → «Сделанное» (и на компьютере): «удали задачу …», «хватит напоминать про задачу». name — часть названия.", parameters: O({ name: STR }, ["name"]) },
    { name: "answer_task", description: "Ответить на вопрос задачи, которая «ждёт ответа»: text — ответ пользователя; name — часть названия (пусто — единственная ждущая).", parameters: O({ name: STR, text: STR }, ["text"]) });
  // «Документы» с телефона (0.62): вопрос — компьютеру, он ищет в своих папках (search_documents), ответ — в «Сделанное»
  // «Мои файлы» (0.98): копия текста файлов компьютера есть здесь — ищем сами, даже когда компьютер выключен; нет — спрашиваем его
  if (((S.sync.on && syncChan() && pcSeen()) || docList().length) && !kidsOn()) t.push({ name: "pc_documents", description: "Найти в «Моих файлах» пользователя — его документах с компьютера (договоры, счета, полисы, инструкции): «что в договоре про сроки», «найди счёт от Ромашки», «какой номер полиса в моих файлах». question — вопрос словами пользователя. Вернёт найденные места с названием файла; отвечай по ним.", parameters: O({ question: STR }, ["question"]) });
  if (S.sync.on && syncChan() && pcSeen()) t.push({ name: "start_task", description: "Передать большую задачу компьютеру пользователя: исследование с отчётом, документ, презентация, работа с файлами или кодом. title — коротко, goal — что сделать и какой нужен результат, подробно. Ход и итог появятся в «Мой день» → «Сделанное»."
      + devComputersText() + " on — на каком компьютере, если назвали («на рабочем»); пусто — любой свободный. Тот не на связи — спроси пользователя и вызови снова с if_off: wait (сделать, когда включится) или cloud (сейчас в облаке).",
    parameters: O({ title: STR, goal: STR, on: STR, if_off: { type: "string", enum: ["", "wait", "cloud"] } }, ["goal"]) });
  if ((S.home.token || haOn()) && !D.web) t.push({ name: "smart_home", description: "Умный дом (Яндекс и Home Assistant): action list (устройства, сценарии и показания датчиков — температура, влажность)|on|off|brightness|brighter|dimmer|temperature|scenario; target — устройство и/или комната словами («свет в спальне», «весь свет», «кондиционер»), value — число.",
    parameters: O({ action: { type: "string", enum: ["list", "on", "off", "brightness", "brighter", "dimmer", "temperature", "scenario"] }, target: STR, value: NUM }, ["action"]) });
  t.push(...wkTools());                                  // «Работа»: поручения руководителя (work.js), если есть работа
  if (typeof cliTools === "function") t.push(...cliTools());   // «Клиенты» и «Сделки» (clients.js)
  t.push(...bsTools());                                  // «Сотрудники»: вы — руководитель, доска с компьютера (boss.js)
  if (kidsOn()) { const k = kidsTools(); return t.filter(x => k.has(x.name)); }   // детский режим — только безопасное
  return D.web ? t.filter(x => !WEB_NO_TOOLS.has(x.name)) : t;
}

/* Аргументы — к описанию инструмента: модели присылают список вместо строки, «5» вместо 5, {"q": …} вместо {"query": …}. */
function coerceArgs(name, a) {
  a = a && typeof a === "object" && !Array.isArray(a) ? Object.assign({}, a) : { text: String(a || "") };
  const spec = toolSpecs().find(t => t.name === name), props = (spec && spec.parameters && spec.parameters.properties) || {};
  const req = (spec && spec.parameters && spec.parameters.required) || [];
  const missing = req.filter(k => !(k in a)), unknown = Object.keys(a).filter(k => !(k in props));
  if (Object.keys(props).length && missing.length === 1 && unknown.length === 1) { a[missing[0]] = a[unknown[0]]; delete a[unknown[0]]; }
  for (const k of Object.keys(a)) {
    const want = (props[k] || {}).type, v = a[k];
    if (want === "string" && Array.isArray(v)) a[k] = v.map(x => typeof x === "string" ? x : JSON.stringify(x)).join(k === "text" ? "\n" : " ");
    else if (want === "string" && v && typeof v === "object") a[k] = JSON.stringify(v);
    else if (want === "string" && v != null && typeof v !== "string") a[k] = String(v);
    else if (want === "number" && typeof v === "string" && v.trim() && !isNaN(+v.replace(",", "."))) a[k] = +v.replace(",", ".");
    else if (want === "boolean" && typeof v === "string") a[k] = /^(true|1|да|yes)$/i.test(v.trim());
  }
  return a;
}
/* Выполнить инструмент модели. -> строка для модели (ошибка — «Ошибка: …» с подсказкой, что сказать человеку);
   take_photo -> {text, image}, call_persona -> {text, switchTo} — их разбирает ask(). */
async function runTool(name, a) {
  hUse("pt:" + name);
  if (kidsOn() && !kidsTools().has(name)) return "Ошибка: в детском режиме этого нельзя. Скажи по-доброму, что это можно только вместе с мамой или папой.";
  if (HANDS_SET.has(name)) return handsTool(name, a || {});
  a = coerceArgs(name, a);
  switch (name) {
    case "suggest_idea": return ideaSuggest(a.title, a.text);     // «Идеи Лиры» голосом (ideas.js, 0.61)
    case "set_reminder": {
      let at = null;
      if (a.in_minutes) at = new Date(Date.now() + a.in_minutes * 60000);
      else if (a.when && !a.at) { const w = parseWhen(a.when); if (w) { at = w.at; if ((!a.repeat || /^d:/.test(w.repeat)) && w.repeat) a.repeat = w.repeat; } }
      else if (a.at) { at = new Date(a.at); if (isNaN(at)) { const w = parseWhen(a.at); at = w && w.at; } }
      // «по будням, кроме пятницы» (30.10): модель часто передаёт repeat: weekdays и теряет «кроме» — дни берём из слов человека
      { const said = String(turnAsk || "").split("\n\nВложения:")[0];
        if (/кроме|за исключением|но не (?:в|во|по)\s|с понедельника по|с вторника по|(?:пн|вт|ср|чт|пт|сб|вс)\s*[-–—]\s*(?:пн|вт|ср|чт|пт|сб|вс)|по (?:понедельникам|вторникам|средам|четвергам|пятницам|субботам|воскресеньям)\s*(?:,|и)/i.test(said)) {
          const w = parseWhen(said);
          if (w && /^d:|^weekly$|^daily$|^weekdays$/.test(w.repeat) && w.repeat !== a.repeat) { a.repeat = w.repeat; if (at && !isNaN(at)) at = rollRepeat(at, a.repeat); } } }
      // «через 20 минут» — считаем сами от часов телефона, а не берём у модели: она могла посчитать от старого времени
      // из разговора (16.10: «сколько времени» — «14:17» в 15:57)
      { const said = String(turnAsk || "").split("\n\nВложения:")[0];
        if (!a.repeat && /(^|[^а-яё])через\s+(?:\S+\s+){0,3}?(?:секунд|минут|час|полчаса|полтора)/i.test(said) && !/кажд/i.test(said)) {
          const w = parseWhen(said); if (w && w.rel && (!at || isNaN(at) || Math.abs(w.at - at) > 90000)) at = w.at; }
        // №338 (пакет 27.10): «напоминание 7:40» в 7:16 — модель дала in_minutes=7 («7 мин 40 с»), и зазвенело в 7:23.
        // Человек назвал часы и минуты — верим его словам, а не модели
        // №776 (16.11): «в четверг 6:00 и 7:00 мотошкола» — два времени в одной фразе: второе напоминание тоже вставало на
        // первое (6:00). Верим словам, только когда время в них одно
        else if (!a.repeat && (said.match(/(^|[^\d:])([01]?\d|2[0-3])[:.][0-5]\d(?!\d)/g) || []).length === 1 && !/кажд|по будн|по выходн/i.test(said)) {
          const w = parseWhen(said); if (w && !w.rel && !w.repeat && (!at || isNaN(at) || Math.abs(w.at - at) > 90000)) at = w.at; } }
      // №776 (16.11): «напоминание в четверг 6:00» — модель поставила «завтра» (вторник). Человек назвал один день недели,
      // а не «завтра/сегодня» — дату берём по его словам: ближайший такой день, время — как посчитано
      { const said = String(turnAsk || "").split(/\n\nВложения:/)[0].toLowerCase();
        const WD = [/^воскресень/, /^понедельник/, /^вторник/, /^сред/, /^четверг/, /^пятниц/, /^суббот/];   // индекс — getDay()
        const days = [...new Set([...said.matchAll(/(?:^|[^а-яё])(понедельник\S*|вторник\S*|сред[ауые]|четверг\S*|пятниц[аеуы]|суббот[аеуы]|воскресень[еяю])/g)]
          .map(m => WD.findIndex(rx => rx.test(m[1]))))];
        if (!a.repeat && days.length === 1 && at && !isNaN(at) && !/завтра|сегодня|кажд|по (?:понед|вторн|сред|четв|пятн|субб|воскр)/.test(said) && at.getDay() !== days[0]) {
          const d = new Date(at); d.setDate(d.getDate() + (((days[0] - d.getDay()) + 7) % 7 || 7)); at = d; } }
      if (!at || isNaN(at)) return "Ошибка: не понял время — спроси у пользователя, когда напомнить.";
      let moved = "";                                    // «на 17:00», а уже 17:26 — на завтра в 17:00, а не в прошлое
      if (at < new Date(Date.now() - 60000) && !a.repeat) { while (at < new Date()) at = new Date(at.getTime() + 864e5); moved = " Это время сегодня уже прошло — поэтому на завтра; так и скажи."; }
      else if (a.repeat) {                               // «по будням в 17:30», а уже 17:43 — первое в следующий будний, а не звонок сразу (№56)
        const r = rollRepeat(at, a.repeat);
        if (r.getTime() !== at.getTime()) { if (at < new Date(Date.now() - 60000)) moved = ` Сегодня это время уже прошло — первое напоминание ${whenText(r)}; так и скажи.`; at = r; }
      }
      // в сообщении были фото или файлы («вот скрины, напомни завтра обсудить их с Сашей») — они к напоминанию, в его заметку
      const n = turnAtt.length ? remindNote(a.text || "", at, turnAsk, turnAtt) : null; if (n) turnAtt = [];
      const x = addAlarm(n ? n.title : a.text || "Напоминание", at, a.kind || "reminder", a.repeat || "", n ? n.id : "");
      showCard(alarmCard(x));
      return `Поставлено: ${whenText(at)}${a.repeat ? ", " + repRu(a.repeat) : ""} — ${x.title} (id ${x.id}).${moved}` +
        (n ? ` Вложения из сообщения (${n.att.length}) приложены к напоминанию — в срок они откроются прямо из него; можно так и сказать.` : "");
    }
    case "calc": {
      try { const r = calcEval(String(a.expression || "")); return `${a.expression} = ${typeof r === "number" ? String(+r.toFixed(10)).replace(".", ",") : r}`; }
      catch (e) { return "Ошибка: " + e.message; }
    }
    case "list_reminders": {
      const l = JSON.parse(D.alarms() || "[]").sort((x, y) => x.at - y.at), jobs = (mind().jobs || []).filter(j => !j.paused);
      const out = l.map(x => `${x.id}: ${whenText(new Date(x.at))}${x.repeat ? " (" + repRu(x.repeat) + ")" : ""} — ${x.title}`);
      if (jobs.length) out.push("Дела по расписанию (делает компьютер): " + jobs.map(j => `${jobShort(j)}${j.at ? " — " + whenText(new Date(j.at)) : ""}`).join("; "));
      return out.length ? out.join("\n") : "Напоминаний нет.";
    }
    case "cancel_reminder": {
      const l = JSON.parse(D.alarms() || "[]"), q = String(a.id || "").toLowerCase();
      // пустой запрос совпал бы с первым же напоминанием — ищем по словам, только если они есть
      const x = l.find(i => i.id === a.id) || (q.trim() ? l.find(i => i.title.toLowerCase().includes(q.trim())) : null);
      if (!x) return "Такого напоминания нет.";
      alarmCancelAll(x.id); syncSoon(); return `Отменено: ${x.title}.`;
    }
    case "mark_done": {
      const items = (Array.isArray(a.items) ? a.items : String(a.items || a.text || "").split(/\s*[;\n]\s*/)).map(x => String(x || "").trim()).filter(Boolean).slice(0, 12);
      if (!items.length) return "Ошибка: не понял, какое дело отметить — спроси коротко.";
      if (a.undo) {
        const today = doneStats().items.slice().reverse(), gone = [];
        for (const t of items) { const w = stems(t), x = today.find(i => !gone.includes(i) && stems(i.title).some(s => w.includes(s))) || (items.length === 1 && today.find(i => !gone.includes(i))); if (x) { doneUndo(x.id); gone.push(x); } }
        if ($("#sh-day.on") && dayTab === "rem") renderDay();
        return gone.length ? `Отметка снята: ${gone.map(x => "«" + x.title + "»").join(", ")}. Сегодня сделано ${doneStats().today}.` : "Среди сегодняшних отметок такого нет.";
      }
      const r = markDone(items, "voice");
      if ($("#sh-day.on") && dayTab === "rem") renderDay();
      return doneSay(r);
    }
    case "done_report": return doneReport(a.days);
    case "call": {
      // №637 (10.11): маленькая модель (qwen3:8b) звала call на «поставь будильник», «включи радио», «какая погода» — Лира
      // раз за разом просила доступ к контактам, а на «какое завтра число» однажды набрала номер. Звоним, только когда звонить
      // и просили (или только что спросили «кому?»), и никогда — без имени
      let said = String(turnAsk || "").split("\n\nВложения:")[0];
      if (!said) { const u = (history || []).filter(m => m && m.role === "user").pop(); said = u ? String(typeof u.content === "string" ? u.content : "") : ""; }   // передали другому персонажу — его слова
      if (!callAsked(said)) { plog("info", "📞 call без просьбы позвонить — не звоню, контакты не прошу"); return CALL_UNASKED; }
      if (!String(a.who || "").trim()) return "Ошибка: не сказано, кому звонить. Спроси коротко, кому позвонить; доступ к контактам не проси.";
      const r = await doCall(a.who || ""); if (r && r.ok === false) callAskAt = Date.now(); return r.text;
    }
    case "send_sms": {
      let num = String(a.who || "").replace(/[^\d+]/g, "");
      if (a.who && num.length < 5) { let c = JSON.parse(D.contact(a.who) || "{}"); if (c.need && await needPerm(CONTACTS)) c = JSON.parse(D.contact(a.who) || "{}"); num = c.number || ""; }
      D.sms(num, a.text || ""); return (num ? "Открыл сообщение — пользователь проверит и отправит." : "Открыл сообщение без получателя — пусть выберет сам.") + notCloseHint(a.who);
    }
    case "open_app": {
      const n = openAppSmart(a.name || "");
      if (!n) return `Приложение «${a.name}» не найдено.`;
      if (typeof D.handsState !== "function" || D.handsState() !== "on") return `Открыто: ${n}.`;
      await sleep(1500);                              // приложение запускается — сразу показываем модели его экран
      const scr = D.handsScreen();
      return `Открыто: ${n}.` + (scr && scr !== "OFF" ? "\n\nНа экране:\n" + scr : "");
    }
    case "route": return routeTool(a);
    case "calendar_list": return calendarList(a);
    case "calendar_add": return calendarAdd(a);
    case "open_url": { let u = String(a.url || ""); if (!/^https?:|^[a-z]+:/.test(u)) u = "https://" + u; return D.openUrl(u) ? "Открыто." : "Не открылось."; }
    case "play_radio": {
      const r = await radio.play(a.query || "");
      if (!r.ok) return r.text;
      return `Играет радио «${r.station.name}». Остановить — «стоп» или «пауза», другая станция — «дальше».` +
        (r.others.length ? ` Другие по запросу: ${r.others.join(", ")}.` : "") + " Скажи коротко, одной фразой, что включено.";
    }
    case "radio_control": {
      const act = a.action || "pause";
      if (act === "next") { const r = await radio.next(); return r.ok ? `Играет «${r.station.name}».` : r.text; }
      if (act === "prev") { const r = await radio.prev(); return r.ok ? `Играет «${r.station.name}».` : r.text; }
      if (!radio.on() && act !== "resume") return "Радио сейчас не играет.";
      if (act === "stop") { radio.stop(); return "Радио выключено."; }
      if (act === "resume") return radio.resume() ? "Радио снова играет." : "Нечего продолжать — скажи, какое радио включить.";
      radio.pause(); return "На паузе.";
    }
    case "media_control": {                       // идея №170: плеер другого приложения — медиа-клавишей
      if (D.web) return "Ошибка: в браузере нельзя управлять другими приложениями — только радио здесь (radio_control).";
      const act = ["next", "prev", "pause", "play"].includes(a.action) ? a.action : "toggle";
      const r = devMedia(act);
      if (!r.sent) return "Ошибка: телефон не принял кнопку плеера — скажи, что переключить можно в самом приложении.";
      return { next: "Нажато «следующий трек»", prev: "Нажато «предыдущий трек»", pause: "Нажата пауза", play: "Нажато «играть»", toggle: "Нажато «пауза/играть»" }[act]
        + (r.active || act === "play" ? "." : " — но музыка в телефоне не играла: если ничего не изменилось, пусть включит плеер.");
    }
    case "web_search": return await webSearch(a.query || "");
    case "show_images": return await webImages(a.query || "", a.count);
    case "read_webpage": {
      // экзамен 16.10: модель шесть раз звала read_webpage без адреса («Invalid host: https://») — адрес из слов человека
      // («посмотри сайт https://www.python.org/», «открой python.org»), как на компьютере (engine_tools, QUERY_TOOLS)
      let url = String(a.url || "").trim();
      if (!/[a-zа-я0-9]\.[a-zа-я]{2,}/i.test(url)) {
        const m = LBRX("(https?:\\/\\/[^\\s«»\"'<>]+)|(?<![@\\w.-])((?:[a-zа-я0-9-]+\\.)+(?:ru|рф|by|com|org|net|io|dev|pro|info|ua|kz|me|app|ai|tv|su)(?:\\/[^\\s«»\"'<>]*)?)", "i").exec(String(turnAsk || "").split("\n\nВложения:")[0]);
        if (!m) return "Ошибка: не пришёл адрес страницы — возьми его из слов пользователя и вызови read_webpage с url.";
        url = (m[1] || m[2]).replace(/[.,;:!?)]+$/, "");
      }
      // видео по ссылке (18.10): текст ролика — в субтитрах, их достаёт компьютер (core/video.py, yt-dlp); здесь — только
      // описание. Не выдумывать содержание: честно сказать и, если компьютер подключён, предложить передать задачу ему
      if (/^https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?|shorts\/|live\/)|youtu\.be\/|rutube\.ru\/(?:video|shorts)\/|vk\.com\/video|vkvideo\.ru\/video)/i.test(url)) {
        const desc = await readPage(url, a.find || "");
        return desc + "\n\n(Это только страница видео — описание, без текста ролика. Скажи об этом честно и не выдумывай содержание. "
          + (S.sync.on && syncChan() && pcSeen() ? "Конспект по самому ролику сделает компьютер: предложи передать ему задачу (start_task: конспект видео по ссылке, сохранить заметкой со ссылкой)." : "Конспект по самому ролику умеет Dewiar на компьютере.") + ")";
      }
      return await readPage(url, a.find || "");
    }
    case "world_time": { const r = await worldTime(a.city || ""); return r ? r + " [Посчитано по часовому поясу — называй именно это время.]" : `Город «${a.city || ""}» не нашёлся — уточни. Время не считай в уме.`; }
    case "weather": return await weather(a.city || "", a.days || 3);
    case "world_news": return await worldNewsTool(WORLD_TOPICS.some(x => x[0] === a.topic) ? a.topic : "");
    case "flashlight": return devTorch(!!a.on) ? (a.on ? "Фонарик включён." : "Фонарик выключен.") : "Фонарика нет.";
    case "phone_settings": {
      const sec = PHONE_SET[a.section] ? a.section : "", name = PHONE_SET[sec];
      if (!sec) return "Такого экрана нет — выбери section из списка.";
      if (SANDBOX) SANDBOX.dev.push({ name: "phone_settings", args: sec, argsObj: { section: sec }, t: Date.now() });
      else if (!D.openSettings(sec)) return `Экран «${name}» на этом телефоне не открылся — подскажи пользователю: Настройки → ${name}.`;
      const hands = typeof D.handsState === "function" && D.handsState() === "on";
      return hands ? `Открыт экран настроек «${name}». Дальше: phone_screen — посмотри экран и нажми нужный переключатель (phone_tap), потом проверь.`
        : `Открыт экран настроек «${name}» — скажи пользователю коротко нажать переключатель (сам ты нажать не можешь). Не говори «включила».`;
    }
    case "take_photo": {
      // камера — только по просьбе (отчёт №92, 19.10: на «ты сказала, что на айфоне можно веб-версией?» сама сфотографировала)
      if (turnAsk && !PHOTO_ASK_RX.test(String(turnAsk))) {
        plog("warn", "take_photo без просьбы — не снимаю");
        return "Снимок не сделан: пользователь не просил камеру. Без прямой просьбы не фотографируй — ответь словами на его вопрос.";
      }
      const shot = await takePhoto(a.camera === "back" ? "environment" : "user");
      if (!shot.ok) return "Ошибка: " + shot.error;
      if (shot.dark) return { text: `Снимок сделан ${a.camera === "back" ? "основной (задней)" : "фронтальной"} камерой, но кадр почти чёрный — камера ничего не видит. `
        + "Не выдумывай, что на нём. Скажи пользователю, что темно или камера закрыта (лежит объективом вниз, пальцем, чехлом), и предложи повторить"
        + (a.camera === "back" ? " — или снять фронтальной." : " — или основной камерой."), image: shot.dataUrl };
      return { text: "Снимок сделан, показан пользователю на экране телефона (под твоим обликом, с кнопкой «Сохранить») и приложен следующим сообщением — посмотри на него и ответь" + (a.question ? `: ${a.question}` : ".") + " Не говори, что не можешь показать: он уже на экране.", image: shot.dataUrl };
    }
    case "set_volume": return `Громкость ${devVolume(a.action, a.percent || (a.action === "set" ? 0 : 20))}%.`;
    case "battery": { const b = JSON.parse(D.battery() || "{}"); return `Заряд ${b.percent}%${b.charging ? ", заряжается" : ""}.`; }
    case "save_note": {
      // дело со временем — в «Дела», а не в заметки (отчёт №94, 19.10: «запиши встречу с Ирой на вторник в 12 и напомни за
      // день» — заметка с ответом Патрика, в «Делах» пусто, утром тишина)
      if (turnAsk && apptAsk(turnAsk)) { plog("info", "📝 дело со временем — не в заметки, а напоминанием"); return APPT_NOTE; }
      // стихи, список идей, ответ на вопрос — в чат, а не в заметки без спроса (экзамен 11.10)
      // «что я записывал про ремонт?» — вопрос, а не просьба записать (экзамен 13.10: найденную заметку сохраняла второй раз)
      if (turnAsk && !/запиш|записать|сохран|запомн|занеси|зафиксир|в\s+файл|конспект|(?:в|во)\s+заметк|заметк[уа](?![а-яё])|созда\w*\s+заметк|нов\w+\s+заметк|допиши|добавь\s+в/i.test(turnAsk))
        return "Записывать не нужно: пользователь не просил сохранять. Это не ошибка — ничего о записи и сбоях не говори, просто ответь на вопрос прямо в чате (список — пунктами в самом ответе).";
      const att = noteAttSave(turnAtt); turnAtt = [];             // фото и файлы этого хода — в заметку
      const fold = folderName(a.folder);
      const n = notes(); n.push(Object.assign({ id: uid("n"), title: a.title, text: a.text, time: Date.now() }, att.length ? { att } : {}, fold ? { folder: fold } : {})); saveNotes(n);
      return `Записано: «${a.title}»` + (fold ? ` в папку «${fold}»` : "") + (att.length ? ` (вложений: ${att.length})` : "") + "."; }
    case "recall": return recall(a.days, a.query);
    case "open_made": {
      const l = apps(), q = String(a.title || "").toLowerCase().trim();
      const ap = q ? l.slice().reverse().find(x => x.title.toLowerCase().includes(q) || q.includes(x.title.toLowerCase().slice(0, 6))) : l[l.length - 1];
      if (!ap) return l.length ? "Такого среди сделанного нет. Есть: " + l.slice(-6).map(x => `«${x.title}»`).join(", ") + "." : "На телефоне ещё ничего не сделано.";
      setTimeout(() => { showCard(appCard(ap)); openApp(ap.id); }, 50);
      return `«${ap.title}» — на экране. Скажи одной фразой; найти потом — «Мой день» → «Сделанное».`;
    }
    case "show_photo": {
      const p = lastPhoto();
      if (!p) return "Снимков пока нет — сделай take_photo.";
      setTimeout(() => showPhotoCard(p), 50);
      return "Снимок снова на экране, под ним кнопка «Сохранить». Скажи об этом одной фразой.";
    }
    case "find_notes": {
      // «покажи заметки», «все», «последние» — это не слова для поиска: отдаём последние заметки. Раньше такие слова
      // ничего не находили, и Лира говорила «заметок пока нет», хотя они были (отзыв 11.10)
      const all = notes().slice().sort((x, y) => (+y.time || 0) - (+x.time || 0));
      const w = String(a.query || "").toLowerCase().replace(/ё/g, "е").split(/[\s,.]+/).filter(x => x.length > 2 && !NOTE_GENERIC.test(x)).map(x => x.slice(0, 5));
      const f = w.length ? all.filter(n => w.some(x => (n.title + " " + n.text).toLowerCase().replace(/ё/g, "е").includes(x))).slice(0, 8) : [];
      const show = (l) => l.map(n => `«${n.title}» (${whenText(new Date(+n.time || Date.now()))}): ${noteShown(n.text).slice(0, 600)}${(n.att || []).length ? ` [вложений: ${n.att.length}]` : ""}`).join("\n\n");
      if (f.length) return show(f);
      if (!all.length) return "Заметок пока нет.";
      return (w.length ? "По этим словам в заметках ничего нет. " : "") + `Всего заметок: ${all.length}. Последние:\n\n` + show(all.slice(0, 10));
    }
    case "remember": { const f = String(a.fact || a.text || a.content || "").trim();
      if (!f) return "Ошибка: не пришло, что запомнить — вызови remember ещё раз с fact (сам факт одной фразой).";
      memAdd(f); return "Запомнил."; }
    case "money_add": {
      if (isPlanMoney(`${a.category || ""} ${a.note || ""}`)) return "Не записано: это план (бюджет, лимит), а не трата или доход. Запомни его как факт (remember), например «Бюджет на мебель — 65 тысяч рублей».";
      const m = money(); const x = { id: uid("m"), date: isoLocal(new Date()).slice(0, 10), kind: a.kind === "income" ? "income" : "expense", amount: +a.amount || 0,
        currency: (a.currency || CUR).toUpperCase(), category: a.category || (a.kind === "income" ? "Доход" : "Разное"), note: a.note || "" };
      if (!x.amount) return "Ошибка: нет суммы."; m.push(x); saveMoney(m);
      try { famShareSpend(x); } catch (e) { plog("warn", "семья: " + e.message); }   // общий бюджет: расход — семье
      return `Записано: ${x.kind === "income" ? "+" : "−"}${x.amount} ${x.currency}, ${x.category}.`;
    }
    case "money_report": return moneyReport(a.period || "month").text;
    case "money_find": {
      const today = isoLocal(new Date()).slice(0, 10), from = a.from || a.date || isoLocal(new Date(Date.now() - 31 * 864e5)).slice(0, 10), to = a.to || a.date || today;
      const words = String(a.text || "").toLowerCase().replace(/ё/g, "е").match(/[\wа-я]{3,}/g) || [];
      const found = money().filter(x => x.date >= from && x.date <= to && (a.amount == null || a.amount === "" || Math.abs(+x.amount - +a.amount) < 0.011)
        && (!a.currency || String(x.currency).toUpperCase() === String(a.currency).toUpperCase())
        && words.every(w => `${x.note || ""} ${x.category || ""}`.toLowerCase().replace(/ё/g, "е").includes(w.slice(0, Math.max(3, w.length - 2)))))
        .sort((p, q) => q.date < p.date ? -1 : 1).slice(0, 20);
      if (!found.length) return `С ${from} по ${to} таких записей нет. Скажи человеку и спроси, когда это было или на какую сумму.`;
      return "Найдено (id — для money_fix):\n" + found.map(x => `${x.id}: ${moneyLine(x)}`).join("\n") + (found.length > 1 ? "\nПохожих несколько — уточни, какую, если человек не сказал «все»." : "");
    }
    case "money_fix": {
      const ids = (a.ids || []).map(String), m = money(), rows = m.filter(x => ids.includes(String(x.id)));
      if (!rows.length) return "Ошибка: таких записей нет — найди заново money_find.";
      const del = (a.action || "delete") === "delete", patch = {};
      ["amount", "currency", "category", "note"].forEach(k => { if (a[k] != null && a[k] !== "") patch[k] = k === "currency" ? String(a[k]).toUpperCase().slice(0, 6) : k === "amount" ? +a[k] : String(a[k]); });
      const what = rows.slice(0, 5).map(moneyLine).join("; ");
      if (!del && !Object.keys(patch).length) return "Ошибка: что поменять — amount, currency, category или note?";
      if (!a.confirmed) return `Спроси пользователя: «${del ? "Удалить" : "Исправить (" + Object.entries(patch).map(([k, v]) => ({ amount: "сумма", currency: "валюта", category: "категория", note: "что" })[k] + " → " + v).join(", ") + ")"} ${what}?» Только после «да» вызови money_fix снова с теми же данными и confirmed: true.`;
      if (del) saveMoney(m.filter(x => !ids.includes(String(x.id)))); else { rows.forEach(x => Object.assign(x, patch)); saveMoney(m); }
      return del ? `Удалено записей: ${rows.length}.` : "Исправлено: " + rows.map(moneyLine).join("; ") + ".";
    }
    case "month_summary": return monthSummary(a.month);                // «Мой месяц с Лирой» (0.61)
    case "close_send": {
      if (a.remind_when) {                                   // «Лира в группе»: напоминание у всех участников (groups.js)
        const g = grOf(a.to) || grMatch(a.to); if (!g) return "Ошибка: напомнить всем можно только в группе своих — назови группу («в группу Семья»).";
        const w = parseWhen(String(a.remind_when)); if (!w || !w.at || isNaN(w.at)) return `Ошибка: не понял, когда напомнить («${a.remind_when}») — спроси день и время.`;
        await grSend(g.gid, a.text || "", [], { rem: { at: w.at.getTime(), t: String(a.text || "").slice(0, 300) } });
        return `Отправлено в группу «${g.name}»: у каждого участника (и у тебя) встанет напоминание ${whenText(w.at)}. Скажи коротко, что напомнишь всем.`;
      }
      const it = await clSend(a.to || "", a.text || ""); return `Отправлено ${it.to}. Скажи коротко, что отправила.`; }
    case "close_read": return clRecent(a.who || "");
    case "work_tasks": case "work_act": return await wkTool(name, a || {});
    case "client_note": case "client_info": case "client_next": case "client_list": case "deal_add": case "deal_stage": case "deals_list": return await cliTool(name, a || {});
    case "team_status": case "team_assign": case "team_message": return await bsTool(name, a || {});
    case "close_where": return await radWhereText(a.who || "");
    case "close_wave": { const p = await radWave(a.to || ""); return `Помахала: ${p.name} увидит и услышит «машет вам». Скажи коротко.`; }
    // №666 (12.11): «как только распознается — я сразу внесу расход» — а код разбирает сканер, не модель; потом модель
    // вписала трату с чужой суммой. Обещать и выдумывать сумму — нельзя
    case "scan_code": scanCode(); return window.t("tool.scan_code.opened");
    case "app_help": return guideAnswer(a.query || "");
    case "app_update": return await updateSay(a.action === "install");
    case "close_call": { const p = await clCall(a.to || "", !!a.video); return `Звоню ${p.name}. Ничего не говори — идёт звонок.`; }
    case "call_persona": {
      const p = findPersona(a.name);
      if (!p) return "Такого персонажа нет.";
      return { text: `${p.name} сейчас ответит сам.`, switchTo: p.id };
    }
    case "make_app": {
      { const no = makeAppRefusal(turnAsk); if (no) return no; }
      const html = String(a.html || "").trim();
      if (!/<(?:html|body|div|script|button|canvas|main|section)\b/i.test(html)) return "Ошибка: html не пришёл — пришли весь HTML-файл в поле html (компактный код).";
      if (!/<\/(?:html|body|script|div|main|section)>\s*$/i.test(html)) return "Ошибка: HTML оборвался на середине — сделай короче и пришли целиком.";
      const ap = saveApp(a.title || "Программа", html);
      setTimeout(() => { showCard(appCard(ap)); openApp(ap.id); }, 50);
      lastDone = `Сделано: «${ap.title}» — уже на экране. Потом найдёте в «Мой день» → «Сделанное» или скажите «покажи ${ap.title.toLowerCase()}».`;
      return `Сделано: «${ap.title}» — на экране телефона, сохранено в «Мой день» → «Сделанное» (снова открыть — open_made). Скажи об этом одной фразой и где её найти, код не пересказывай.`;
    }
    case "pc_documents": {
      const q = String(a.question || "").trim(); if (q.length < 3) return "Ошибка: скажи, что найти в документах.";
      const local = docList().length;
      if (local) {
        let hits = []; try { hits = await docSearch(q, 5); } catch (e) { plog("warn", "Мои файлы: поиск — " + e.message); }
        if (hits.length) return "Нашлось в «Моих файлах» (копия текста с компьютера, работает и без него):\n"
          + hits.map((h, k) => `[${k + 1}] «${h.name}» (${h.path}):\n${clip(h.text, 900)}`).join("\n\n")
          + "\n\nОтветь по этим местам коротко и назови файл. Чего здесь нет — не выдумывай: скажи, что в файлах этого не нашлось. Открыть файл целиком — «Мой день» → «Заметки» → «Мои файлы».";
      }
      const pcs = (syncStatus.devices || []).filter(x => x.pc && x.name !== "Облако Dewiar").sort((x, y) => (y.seen || 0) - (x.seen || 0));
      if (!pcs.length || !(S.sync.on && syncChan())) return local ? `В «Моих файлах» (${docN(local)}) об этом ничего не нашлось. Скажи об этом честно одной фразой.` : "Ошибка: компьютер с Dewiar не найден — документы ищет программа на компьютере.";
      if (local && !pcOnline()) return `В «Моих файлах» (${docN(local)}) об этом ничего не нашлось, а компьютер «${pcs[0].name}» сейчас не на связи. Скажи об этом честно одной фразой.`;
      try { taskToPc("Документы: " + q.slice(0, 50), "Ответь на вопрос по моим документам на этом компьютере: найди нужное в моих папках (search_documents), "
        + "ответь коротко, процитируй главное место и назови файл. Не нашёл — так и скажи. Вопрос: " + q, pcs[0].name); } catch (e) { return "Не получилось: " + e.message; }
      return (pcOnline() ? `Спросила компьютер «${pcs[0].name}» — он ищет в своих папках; ответ придёт через минуту в «Мой день» → «Сделанное», пришлю уведомление.`
        : `Компьютер «${pcs[0].name}» сейчас не на связи — вопрос дождётся, когда он включится; ответ придёт в «Сделанное».`) + " Ответа ЕЩЁ НЕТ — скажи об этом одной фразой.";
    }
    case "start_task": {
      if (a.on) { try { const r = devTaskOn(a); if (r) return r; } catch (e) { return "Ошибка: " + e.message; } }   // «на рабочем компьютере…» (devices.js)
      try { taskToPc(a.title || String(a.goal || "").slice(0, 60), a.goal || a.title || ""); } catch (e) { return "Не получилось: " + e.message; }
      return (pcOnline() ? "Задача отправлена компьютеру — он возьмёт её в течение минуты; пока не взял, она видна в «Мой день» → «Сделанное» как «ждёт, когда компьютер возьмёт»." : "Компьютер сейчас не на связи — задачу делает облако Dewiar.")
        + " Ход и итог — в «Мой день» → «Сделанное»; когда будет готово, пришлю уведомление, а файлы можно будет открыть и сохранить прямо здесь."
        + " Результата ЕЩЁ НЕТ — он появится через несколько минут или дольше. Скажи одной фразой, что взялась (взялся) и сообщишь, когда будет готово; не говори «готово», «сделала», «вот презентация» — это неправда, пока задача не закончилась.";
    }
    case "smart_home": return await homeTool(a);
    case "send_message": {
      // «Напиши Андрею…», а Андрея нет в «Близких» — сообщение откроется в мессенджере (получателя выберет человек), и
      // модели — сказать об этом честно (экзамен: «Готово, открыла MAX» — как будто Андрей уже получил)
      const r = sendTo(a.app || "max", a.text || "");
      return typeof r === "string" ? r + notCloseNote(turnAsk) : r;
    }
    case "ask_knowledge": return await askKnowledge(a.question || "", a.base || "");
    case "remove_task": case "answer_task": {
      const f = taskFind(a.name || "");
      if (!f) return "Такой задачи нет. Задачи: " + (Object.values(mind().tasks).map(t => `«${t.title}» (${TASK_RU[t.status] || t.status})`).join(", ") || "нет");
      if (name === "answer_task") { if (!String(a.text || "").trim()) return "Нужен текст ответа."; taskCmd(f[0], "answer", a.text); return `Ответ передан задаче «${f[1].title}» — она продолжит.`; }
      taskCmd(f[0], "delete"); return `Задача «${f[1].title}» удалена — и здесь, и на компьютере; напоминаний о ней больше не будет.`;
    }
  }
  return "Неизвестный инструмент.";
}

/* HTML → простой текст: для поиска и чтения страниц (раздел «интернет» — ниже, после камеры) */
const stripHtml = (h) => h.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ")
  .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();
/* ---------- камера: «сфотографируй меня и опиши» ----------
   Снимает сам интерфейс (getUserMedia в WebView; доступ даёт MainActivity.onPermissionRequest при разрешении CAMERA):
   отсчёт 3-2-1, кадр JPEG до 1024 px — модели картинкой; почти чёрный кадр помечается dark, чтобы модель не выдумывала. */
const CAMERA = "android.permission.CAMERA";
async function visionModel() {                     // облако Dewiar: для снимка — модель, которая видит картинки
  if (!S.llm.cloud) return "";
  try {
    const md = await cloudGet(cloudBase(), S.llm.api_key, "/models");
    const cur = (md.data || []).find(m => m.id === S.llm.model);
    if (cur && cur.vision) return "";
    const v = (md.data || []).find(m => m.vision);
    return v ? v.id : "";
  } catch (e) { return ""; }
}
let camAt = 0;
function lum(v, w = 32, h = 24) {                  // средняя яркость кадра 0…255 — чёрный кадр не отдаём модели
  try { const c = document.createElement("canvas"); c.width = w; c.height = h; const x = c.getContext("2d"); x.drawImage(v, 0, 0, w, h);
    const d = x.getImageData(0, 0, w, h).data; let sum = 0; for (let i = 0; i < d.length; i += 4) sum += d[i] * .3 + d[i + 1] * .59 + d[i + 2] * .11; return sum / (w * h); }
  catch (e) { return 255; }
}
/* Снимок — в разговоре, с кнопкой «Сохранить» (в «Загрузки»); последний хранится (last_photo.txt) — show_photo покажет снова. */
const lastPhoto = () => { try { return fileGet("last_photo.txt") || ""; } catch (e) { return ""; } };
function photoCard(url) {
  return `<div class="appc"><img class="shot" src="${url}" alt="Снимок"><div class="row2"><button class="btn" onclick="savePhoto()">Сохранить в «Загрузки»</button></div></div>`;
}
function savePhoto() {
  const u = lastPhoto(), b64 = u.split(",")[1] || "";
  const d = new Date(), name = `Dewiar ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}-${pad(d.getMinutes())}.jpg`;
  const where = b64 && D.saveDownloadB64 ? D.saveDownloadB64(name, "image/jpeg", b64) : "";
  toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
}
async function takePhoto(facing) {
  // камера, закрытая секунду назад, ещё освобождается — второй снимок подряд вышел бы чёрным
  if (Date.now() - camAt < 1500) await sleep(1500 - (Date.now() - camAt));
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return { ok: false, error: "камера недоступна в этой версии Android" };
  if (!(await needPerm(CAMERA))) return { ok: false, error: "нет разрешения на камеру — разрешите камеру для Dewiar в настройках телефона" };
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false }); }
  catch (e) { return { ok: false, error: "камера не открылась (" + (e.message || e.name) + ")" }; }
  const box = document.createElement("div");
  box.id = "cam"; box.innerHTML = `<video autoplay playsinline muted class="${facing === "user" ? "mirror" : ""}"></video><b></b>`;
  document.body.appendChild(box);
  const v = box.querySelector("video"), cnt = box.querySelector("b");
  try {
    v.srcObject = stream; await v.play().catch(() => {});
    for (let i = 0; i < 50 && !v.videoWidth; i++) await sleep(100);
    for (let i = 0; i < 12 && lum(v) < 14; i++) await sleep(200);     // первые кадры у камеры тёмные — ждём, пока «проснётся»
    for (const n of ["3", "2", "1"]) { cnt.textContent = n; D.vibrate(15); await sleep(650); }
    cnt.textContent = ""; box.classList.add("flash");
    let light = lum(v);
    for (let i = 0; i < 6 && light < 14; i++) { await sleep(300); light = lum(v); }   // кадр всё ещё чёрный — ещё немного подождём
    const k = Math.min(1, 1024 / Math.max(v.videoWidth || 1, v.videoHeight || 1)), cv = document.createElement("canvas");
    cv.width = Math.round((v.videoWidth || 640) * k); cv.height = Math.round((v.videoHeight || 480) * k);
    cv.getContext("2d").drawImage(v, 0, 0, cv.width, cv.height);
    const dataUrl = cv.toDataURL("image/jpeg", 0.85);
    await sleep(250);
    try { fileSave("last_photo.txt", dataUrl); } catch (e) { }
    showPhotoCard(dataUrl);
    return { ok: true, dataUrl, dark: light < 14 };
  } finally {
    stream.getTracks().forEach(t => t.stop());
    try { v.srcObject = null; } catch (e) { }
    box.remove();
    camAt = Date.now();
  }
}

/* ---------- интернет: поиск (DuckDuckGo), страница, погода (open-meteo) ----------
   Провайдер режет поисковик или сайт («Connection reset») — ищем и читаем через сервер Dewiar (cloud.php ?p=/search, /fetch),
   как агент на сайте. Нужен вход в аккаунт dewiar.pro или ключ Dewiar. */
async function dewiarWeb(kind, value) {
  if (S.net.web_via === false) throw new Error("запасной путь через сервер Dewiar выключен в настройках");
  const c = syncCred();
  if (!c) throw new Error("нет входа в аккаунт dewiar.pro и ключа Dewiar");
  const r = await http("GET", c.base + "?p=/" + kind + "&" + (kind === "search" || kind === "images" ? "q=" : "url=") + encodeURIComponent(value), { headers: { Authorization: "Bearer " + c.token }, timeout: 40000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status !== 200) throw new Error((d.error && d.error.message) || "сервер ответил " + r.status);
  return d;
}
/* Картинки к рассказу (как core/images.py на компьютере): ищем как поисковик картинок — DuckDuckGo Картинки (тот же
   поисковик, что у web_search, безопасный поиск), не открылся — через сервер Dewiar, запасной путь — Wikimedia Commons
   (свободные изображения с автором и лицензией). Показываются под ответом (frameAnswer) и остаются в истории. */
const COMMONS = "https://commons.wikimedia.org/w/api.php", DDG_IMG = "https://duckduckgo.com";
const PIC_SKIP = /\b(?:logo|icon|flag of|coat of arms|map of|locator|signature)\b/i;
const picSite = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return ""; } };
const picClean = (v) => String(v || "").replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/\s+/g, " ").trim();
const webPic = (src, full, page, title) => ({ src, full: full || src, page: page || full || src, title: picClean(title).slice(0, 120) || picSite(page) || "картинка",
  desc: "", author: "", license: "", site: picSite(page || full), source: "web" });
async function ddgImages(q, n) {
  const base = window.DEWIAR_DDG || DDG_IMG, UA = { "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36", "Accept-Language": "ru-RU,ru;q=0.9" };
  const r = await http("GET", base + "/?" + new URLSearchParams({ q, iax: "images", ia: "images", kp: "1" }), { headers: UA, timeout: 15000 });
  const m = /vqd=["']?([\d-]+)/.exec(r.body || "");
  if (!m) throw new Error("поисковик картинок не дал ключ");
  const r2 = await http("GET", base + "/i.js?" + new URLSearchParams({ l: "ru-ru", o: "json", q, vqd: m[1], f: ",,,,,", p: "1" }), { headers: Object.assign({ Referer: base + "/", Accept: "application/json" }, UA), timeout: 15000 });
  const out = [];
  for (const x of (JSON.parse(r2.body || "{}").results || [])) {
    if (!x.thumbnail || (x.width || 999) < 200 || /\.svg$/i.test(x.image || "") || PIC_SKIP.test(x.title || "")) continue;
    out.push(webPic(x.thumbnail, x.image, x.url, x.title)); if (out.length >= n) break;
  }
  return out;
}
async function commonsImages(q, n) {
  const p = new URLSearchParams({ action: "query", format: "json", generator: "search", gsrnamespace: "6", gsrlimit: "16",
    gsrsearch: q + " filetype:bitmap", prop: "imageinfo", iiprop: "url|extmetadata|mime|size", iiurlwidth: "480",
    iiextmetadatafilter: "ObjectName|ImageDescription|Artist|LicenseShortName", iiextmetadatalanguage: "ru" });
  const j = JSON.parse((await http("GET", (window.DEWIAR_COMMONS || COMMONS) + "?" + p, { headers: { "User-Agent": "Dewiar-Android (voice assistant; https://dewiar.pro)" }, timeout: 15000 })).body || "{}");
  const items = [];
  for (const pg of Object.values((j.query || {}).pages || {}).sort((a, b) => (a.index || 0) - (b.index || 0))) {
    const ii = (pg.imageinfo || [])[0] || {}, meta = ii.extmetadata || {};
    if (!ii.thumburl || !/^image\//.test(ii.mime || "") || ii.mime === "image/svg+xml" || (ii.width || 0) < 200) continue;
    const name = String(pg.title || "").replace(/^File:|\.[a-z0-9]+$/gi, "").replace(/_/g, " ");
    if (PIC_SKIP.test(name)) continue;
    items.push({ src: ii.thumburl, full: (ii.width || 0) > 1280 ? ii.thumburl.replace(/\/\d+px-/, "/1280px-") : (ii.url || ii.thumburl), page: ii.descriptionurl || "",
      title: (picClean((meta.ObjectName || {}).value) || name).slice(0, 120), desc: picClean((meta.ImageDescription || {}).value).slice(0, 200),
      author: picClean((meta.Artist || {}).value).slice(0, 80), license: picClean((meta.LicenseShortName || {}).value).slice(0, 40), site: "commons.wikimedia.org", source: "commons" });
    if (items.length >= n) break;
  }
  return items;
}
async function webImages(q, count) {
  q = String(q || "").trim(); if (!q) return "Ошибка: пустой запрос — что показать?";
  const n = Math.max(1, Math.min(6, +count || 4));
  const ways = [["DuckDuckGo", () => ddgImages(q, n)],
    ["сервер Dewiar", async () => ((await dewiarWeb("images", q)).results || []).filter(x => x.src).slice(0, n).map(x => webPic(x.src, x.full, x.page, x.title))],
    ["Wikimedia Commons", () => commonsImages(q, n)]];
  let items = [], err = null, answered = false, via = "";
  for (const [name, fn] of ways) {
    try { items = await fn(); answered = true; } catch (e) { err = e; plog("info", `🖼 картинки: ${name} не ответил (${e.message})`); continue; }
    if (items.length) { via = name; break; }
  }
  if (!items.length && !answered && err) return "Картинки сейчас не загрузились (" + err.message + ") — скажи об этом коротко.";
  if (!items.length) return "Картинок по этому запросу не нашлось. Не говори, что показала их; можно попробовать запрос проще или по-английски.";
  turnMedia = (turnMedia || []).concat(items).slice(0, 12);
  plog("info", `🖼 картинки: «${clip(q)}» — ${items.length} (${via})`);
  const sites = [...new Set(items.map(x => x.site).filter(Boolean))].slice(0, 4);
  const from = items.every(x => x.source === "commons") ? "Wikimedia Commons" : "поиск картинок" + (sites.length ? " (сайты: " + sites.join(", ") + ")" : "");
  return `На экране показано картинок: ${items.length} (${from}). Что на них (подписи с сайтов):\n` + items.map((x, i) => `${i + 1}. ${x.title}${x.desc ? " — " + x.desc.slice(0, 120) : ""}${x.source !== "commons" && x.site ? " [" + x.site + "]" : ""}`).join("\n")
    + "\nГовори о них как о показанных («на второй картинке…»), но описывай только то, что следует из подписей; не выдумывай деталей. Подпись не о том — не выдавай картинку за нужную.";
}
/* картинка в ответе: нажали — на весь экран (без ухода в браузер), долгое нажатие — источник в браузере */
function wirePics(root) {
  if (!root) return;
  root.querySelectorAll(".dw-pic").forEach(a => {
    a.onclick = (e) => { e.preventDefault(); picView(a.dataset.full || a.querySelector("img").src, a.title || "", a.href, a.dataset.src || a.querySelector("img").src); };
  });
}
function picView(src, title, page, thumb) {
  let v = $("#picview");
  if (!v) { v = document.createElement("div"); v.id = "picview"; v.innerHTML = `<img alt=""><div class="pv-t"></div><button class="btn" id="pv-src">Источник</button>`; document.body.appendChild(v);
    v.onclick = (e) => { if (e.target.id !== "pv-src") v.classList.remove("on"); }; }
  const im = v.querySelector("img"); im.referrerPolicy = "no-referrer";
  im.onerror = () => { if (thumb && im.src !== thumb) im.src = thumb; };      // оригинал с сайта не дался — миниатюра поисковика
  im.src = src; v.querySelector(".pv-t").textContent = title;
  v.querySelector("#pv-src").onclick = () => { if (page) D.openUrl(page); };
  v.classList.add("on");
}
async function webSearch(q) {
  q = String(q || "").trim();
  if (!q) return "Ошибка: пустой запрос — напиши, что искать.";
  let out = [];
  try {
    const r = await http("POST", "https://html.duckduckgo.com/html/", { headers: { "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0 (Linux; Android 14) Dewiar" },
      body: "q=" + encodeURIComponent(q) + "&kl=ru-ru", timeout: 15000 });
    if (r.status !== 200) throw new Error("поисковик ответил " + r.status);
    const re = /<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>[\s\S]*?class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = re.exec(r.body)) && out.length < 6) {
      let u = m[1]; const uu = u.match(/uddg=([^&]+)/); if (uu) u = decodeURIComponent(uu[1]);
      out.push(`${stripHtml(m[2])}\n${stripHtml(m[3])}\n${u}`);
    }
    if (!out.length && /anomaly|captcha/i.test(r.body || "")) throw new Error("поисковик просит капчу");
  } catch (e) {
    try { out = ((await dewiarWeb("search", q)).results || []).slice(0, 6).map(x => `${x.title}\n${x.snippet}\n${x.url}`); }
    catch (e2) { return `Ошибка: поиск недоступен (${e.message}; через сервер Dewiar: ${e2.message}).`; }
  }
  return out.length ? out.join("\n\n") + SEARCH_TAIL() : "Поиск ничего не дал.";
}
/* Длинная страница — начало и куски вокруг слов find (или вопроса); пустая — честно «текста нет» (экзамен 14.10: курс
   доллара стоял дальше 7000 знаков — модель его выдумала; пустая страница журнала — выдумала фильм). Как page_excerpt на компьютере. */
const PAGE_MAX = 7000, PAGE_EMPTY = "Страница открылась, но текста на ней нет (скорее всего, он подгружается скриптом). Ничего не пересказывай за неё и не придумывай — открой другой адрес из поиска или честно скажи, что страница не прочиталась.";
const PAGE_STOP = new Set("какой какая какие каков сегодня сейчас завтра вчера скажи покажи найди пожалуйста можно нужно этот этого много очень только было будет есть где когда почему зачем сколько".split(" "));
function pageTerms(t) {
  const out = [];
  for (const w0 of String(t || "").match(/[A-Za-zА-Яа-яЁё0-9]{4,}/g) || []) { const w = w0.toLowerCase(); if (!PAGE_STOP.has(w) && !/^\d+$/.test(w) && !out.includes(w.slice(0, 5))) out.push(w.slice(0, 5)); }
  return out.slice(0, 8);
}
function pageExcerpt(text, find, question) {
  text = String(text || "").trim();
  if (text.replace(/\s+/g, "").length < 80) return PAGE_EMPTY;
  if (text.length <= PAGE_MAX) return text;
  const terms = pageTerms(find).length ? pageTerms(find) : pageTerms(question), low = text.toLowerCase(), spans = [];
  for (const t of terms) { let i = low.indexOf(t, 1500); while (i >= 0 && spans.length <= 40) { spans.push([Math.max(1500, i - 500), Math.min(text.length, i + t.length + 700)]); i = low.indexOf(t, i + t.length); } }
  spans.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [a, b] of spans) { if (merged.length && a <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], b); else merged.push([a, b]); }
  if (!merged.length) return text.slice(0, PAGE_MAX) + `…\n[Страница длиннее: показано ${PAGE_MAX} из ${text.length} знаков. Если нужного здесь нет — вызови read_webpage ещё раз с find (что ищешь, например «Доллар США»); не додумывай.]`;
  const out = [text.slice(0, 1500)]; let left = PAGE_MAX - 1500;
  for (const [a, b] of merged) { if (left <= 200) break; const piece = text.slice(a, Math.min(b, a + left)); out.push(piece); left -= piece.length; }
  return out.join("\n…\n") + `\n[Страница длинная (${text.length} знаков): выше начало и места со словами «${terms.join(", ")}». Чего здесь нет — того на странице не видно; не додумывай.]`;
}
function pageLinks(page, base, limit = 30) {
  let host = ""; try { host = new URL(base).host; } catch (e) { return []; }
  const seen = new Set([base.split("#")[0].replace(/\/$/, "")]), out = [];
  for (const m of page.matchAll(/<a\b[^>]*?href=["']([^"'#][^"']*)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    let u = ""; try { u = new URL(m[1].replace(/&amp;/g, "&"), base).href.split("#")[0]; } catch (e) { continue; }
    const t = stripHtml(m[2]);
    if (!u.startsWith("http") || new URL(u).host !== host || !t || t.length > 90 || /\.(png|jpe?g|gif|svg|pdf|zip|css|js|xml|ico)(\?|$)/i.test(u) || seen.has(u.replace(/\/$/, ""))) continue;
    seen.add(u.replace(/\/$/, "")); out.push([t, u]); if (out.length >= limit) break;
  }
  return out;
}
async function readPage(url, find) {
  if (!/^https?:/.test(url)) url = "https://" + url;
  try {
    const r = await http("GET", url, { headers: { "User-Agent": "Mozilla/5.0 (Linux; Android 14) Dewiar" }, timeout: 20000 });
    if (r.status === 403 || r.status === 451) throw new Error("сайт не пускает (" + r.status + ")");
    // №296 (идеи 17.11): PDF по ссылке (инструкция, договор) — текстом с сервера Dewiar (там его разбирает pdftotext);
    // не вышло — честно, и компьютер, если он подключён (на компьютере Лира читает PDF по ссылке сама)
    if (/^%PDF-/.test(String(r.body || "").slice(0, 8)) || /\.pdf(?:[?#]|$)/i.test(url)) {
      try { return pageExcerpt(String((await dewiarWeb("fetch", url)).text || ""), find, turnQ); }
      catch (e) { return "Это PDF — на телефоне прочитать его не получилось. Скажи честно и не пересказывай по догадке. "
        + (S.sync.on && syncChan() && pcSeen() ? "Компьютер подключён: предложи передать ему (start_task: прочитать PDF по ссылке) — он читает PDF сам." : "На компьютере Лира читает PDF по ссылке сама."); }
    }
    // отчёт №69 (как на компьютере, tools.html_to_text): без меню и боковых панелей; есть <main>/<article> — он;
    // в конце — разделы того же сайта, их можно открыть
    let h = String(r.body || "").replace(/<(nav|header|footer|aside|noscript|svg)\b[\s\S]*?<\/\1>/gi, " ");
    const main = /<(main|article)\b[^>]*>([\s\S]*)<\/\1>/i.exec(h);
    if (main && stripHtml(main[2]).length > 200) h = main[2];
    const out = pageExcerpt(stripHtml(h), find, turnQ), links = pageLinks(String(r.body || ""), url);
    return links.length >= 3 && !/^Страница открылась, но текста/.test(out) ? out + "\n\nРазделы этого сайта (нужное можно открыть read_webpage по адресу):\n" + links.map(([t, u]) => `- ${t} — ${u}`).join("\n") : out;
  } catch (e) {
    try { return pageExcerpt(String((await dewiarWeb("fetch", url)).text || ""), find, turnQ); }
    catch (e2) { return `Ошибка: страница не открылась (${e.message}).`; }
  }
}
const WMO = { 0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 48: "изморозь", 51: "морось", 53: "морось", 55: "сильная морось",
  61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь", 67: "ледяной дождь", 71: "небольшой снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа",
  80: "ливень", 81: "ливни", 82: "сильные ливни", 85: "снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом", 99: "гроза с градом" };
/* Который час в другом городе — по часовому поясу (Intl), а не «в уме» (отчёт №131, 20.10: модель вычла 3 часа вместо
   прибавления). Частые города — таблица (как CITY_TZ в core/tools.py), остальные — геокодер Open-Meteo (поле timezone). */
const CITY_TZ = {"москв": "Europe/Moscow", "петербург": "Europe/Moscow", "питер": "Europe/Moscow", "калининград": "Europe/Kaliningrad", "самар": "Europe/Samara", "екатеринбург": "Asia/Yekaterinburg", "челябинск": "Asia/Yekaterinburg", "уф": "Asia/Yekaterinburg", "тюмен": "Asia/Yekaterinburg", "омск": "Asia/Omsk", "новосибирск": "Asia/Novosibirsk", "томск": "Asia/Tomsk", "барнаул": "Asia/Barnaul", "красноярск": "Asia/Krasnoyarsk", "кемерово": "Asia/Novokuznetsk", "новокузнецк": "Asia/Novokuznetsk", "иркутск": "Asia/Irkutsk", "улан-удэ": "Asia/Irkutsk", "чит": "Asia/Chita", "якутск": "Asia/Yakutsk", "владивосток": "Asia/Vladivostok", "хабаровск": "Asia/Vladivostok", "магадан": "Asia/Magadan", "сахалин": "Asia/Sakhalin", "южно-сахалинск": "Asia/Sakhalin", "камчат": "Asia/Kamchatka", "петропавловск-камчатск": "Asia/Kamchatka", "минск": "Europe/Minsk", "киев": "Europe/Kyiv", "алмат": "Asia/Almaty", "астан": "Asia/Almaty", "ташкент": "Asia/Tashkent", "бишкек": "Asia/Bishkek", "ереван": "Asia/Yerevan", "тбилиси": "Asia/Tbilisi", "баку": "Asia/Baku", "лондон": "Europe/London", "париж": "Europe/Paris", "берлин": "Europe/Berlin", "рим": "Europe/Rome", "мадрид": "Europe/Madrid", "стамбул": "Europe/Istanbul", "дуба": "Asia/Dubai", "пекин": "Asia/Shanghai", "токио": "Asia/Tokyo", "сеул": "Asia/Seoul", "бангкок": "Asia/Bangkok", "дели": "Asia/Kolkata", "нью-йорк": "America/New_York", "чикаго": "America/Chicago", "лос-анджелес": "America/Los_Angeles", "сан-франциско": "America/Los_Angeles", "торонто": "America/Toronto", "сидне": "Australia/Sydney", "иерусалим": "Asia/Jerusalem", "тель-авив": "Asia/Jerusalem"};
async function cityTz(city) {
  const c = String(city || "").toLowerCase().replace(/ё/g, "е").trim();
  for (const [k, tz] of Object.entries(CITY_TZ)) if (c.startsWith(k)) return { name: city, tz };
  try {
    const g = JSON.parse((await http("GET", "https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name=" + encodeURIComponent(city), { timeout: 10000 })).body || "{}");
    const p = (g.results || [])[0]; return p && p.timezone ? { name: p.name || city, tz: p.timezone } : null;
  } catch (e) { return null; }
}
function tzOffsetMin(tz, d) {                    // смещение пояса от UTC в минутах — через Intl, без библиотек
  const f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const o = Object.fromEntries(f.formatToParts(d).map(x => [x.type, x.value]));
  return Math.round((Date.UTC(+o.year, +o.month - 1, +o.day, +o.hour % 24, +o.minute) - Math.floor(d.getTime() / 6e4) * 6e4) / 6e4);
}
async function worldTime(city, prep, now) {
  const z = await cityTz(city); if (!z) return null;
  now = now || new Date();
  let off; try { off = tzOffsetMin(z.tz, now); } catch (e) { return null; }
  const there = new Date(now.getTime() + (off + now.getTimezoneOffset()) * 6e4), diff = Math.round((off + now.getTimezoneOffset()) / 6) / 10;
  const n = Math.abs(diff), word = n !== Math.floor(n) ? "часа" : n % 10 === 1 && n % 100 !== 11 ? "час" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "часа" : "часов";
  const rel = diff === 0 ? "как у вас" : `на ${String(n).replace(".", ",")} ${word} ${diff > 0 ? "больше" : "меньше"}, чем у вас`;
  const dd = Math.round((new Date(there.getFullYear(), there.getMonth(), there.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  const day = dd > 0 ? ", там уже завтра" : dd < 0 ? ", там ещё вчера" : "";
  const hm = `${there.getHours()}:${String(there.getMinutes()).padStart(2, "0")}`;
  const nm = String(prep ? city : z.name).replace(/(^|[ -])([а-яё])/g, (x, a, b) => a + b.toUpperCase());
  return prep ? `${prep[0].toUpperCase() + prep.slice(1)} ${nm} сейчас ${hm}${day} — ${rel}.` : `${nm}: сейчас ${hm}${day} — ${rel}.`;
}
/* Погода: open-meteo напрямую, а не открылся (№301, №304, пакет 27.10: «сервер долго не отвечает» три раза подряд —
   у провайдера или в слабой сети) — тем же адресом через сервер Dewiar, как поиск. */
async function meteoGet(url) {
  try {
    const r = await http("GET", url, { timeout: 9000 });
    if (r.status === 200) return JSON.parse(r.body || "{}");
    throw new Error("open-meteo ответил " + r.status);
  } catch (e) {
    let d; try { d = await dewiarWeb("fetch", url); } catch (x) { throw e; }
    plog("info", "погода — через сервер Dewiar: " + (e.message || e));
    return JSON.parse(d.text || "{}");
  }
}
async function weather(city, days) {
  // идея №142 (05.11): город не назван — запомненный, из «Утра» с компьютера или из памяти («живу в Балашове», «я из Минска»)
  let mem = "";
  if (!city) { mem = wqHome().replace(/^во?\s+/i, ""); city = mem; }
  if (!city) return "Ошибка: спроси, в каком городе.";
  const g = await meteoGet("https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name=" + encodeURIComponent(city));
  let p = (g.results || [])[0];
  if (!p) { const q = await wqGeocode(city).catch(() => null); if (q) p = { name: q.name, latitude: q.lat, longitude: q.lon }; }   // «Балашове», «Минска» — по основам
  if (!p) return `Город «${city}» не нашёлся.`;
  const u = `https://api.open-meteo.com/v1/forecast?latitude=${p.latitude}&longitude=${p.longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=${Math.min(7, Math.max(1, days))}`;
  const w = await meteoGet(u), c = w.current || {}, d = w.daily || {};
  const lines = [`${p.name}: сейчас ${Math.round(c.temperature_2m)}°, ощущается как ${Math.round(c.apparent_temperature)}°, ${WMO[c.weather_code] || ""}, ветер ${Math.round(c.wind_speed_10m)} км/ч.`];
  const dayName = (t) => { const k = Math.round((new Date(t + "T12:00") - new Date(isoLocal(new Date()).slice(0, 10) + "T12:00")) / 864e5); return k === 0 ? " (сегодня)" : k === 1 ? " (завтра)" : k === 2 ? " (послезавтра)" : ""; };
  (d.time || []).forEach((t, i) => lines.push(`${t}${dayName(t)}: ${Math.round(d.temperature_2m_min[i])}…${Math.round(d.temperature_2m_max[i])}°, ${WMO[d.weather_code[i]] || ""}, осадки ${d.precipitation_probability_max[i] != null ? d.precipitation_probability_max[i] : 0}%.`));
  if (mem) lines.push(`[Город не назван — взят город человека (запомненный или из памяти): ${p.name}. Назови его в ответе; нужен другой — пусть скажет какой.]`);
  return lines.join("\n");
}

/* Погода без модели (0.63; на компьютере — core/weatherq.py, №373: маленькая модель погоду не искала и выдумывала):
   «какая погода?», «погода в Минске завтра», «сколько градусов на улице?» — сразу числа Open-Meteo. Город: названный →
   запомненный здесь (S.weatherCity) → «Утро» с компьютера (morning.json) → память («живу в …», «мой город — …»); нет нигде —
   спросить. Названный, если своего нет, запоминаем. «Погода в доме» — не город: отвечает модель. JS без \w для кириллицы. */
const WQ_ASK = /^(?:какая|какой|что|как|скажи|подскажи|узнай|глянь|посмотри|покажи)?\s*(?:там\s+|у\s+нас\s+|у\s+меня\s+)?(?:сейчас\s+|сегодня\s+|завтра\s+|послезавтра\s+)?(?:с\s+|про\s+)?погод[аеуыой]+/i;
const WQ_TEMP = /^(?:а\s+)?(?:сколько\s+(?:сейчас\s+)?градусов|какая\s+(?:сейчас\s+)?температура|температура)(?:\s+(?:сейчас|сегодня))?(?:\s+(?:на\s+улице|за\s+окном|снаружи))(?:\s+(?:сейчас|сегодня))?$|^(?:а\s+)?(?:холодно|тепло|жарко)\s+(?:ли\s+)?(?:сейчас\s+)?(?:на\s+улице|за\s+окном)$/i;
const WQ_NOT = /включи|поставь|песн|музык|трек|напомн|кажд[а-яё]+\s+(?:утро|день|час)|по\s+утрам|пришли|телеграм|(?:^|[^a-z])max(?![a-z])|недел|выходн|месяц|вчера|прошл|прогноз\s+на\s+\d|почему|зачем|влияет|климат|запиши|заметк|календар/i;
const WQ_TIME = new Set("сейчас сегодня завтра послезавтра на будет там у нас меня за окном улице днём днем утром вечером какая какой какие какая-то пожалуйста подскажи скажи".split(" "));
const WQ_PLACE = "([А-ЯЁA-Z][А-Яа-яЁёA-Za-z-]+(?:,?\\s+[А-ЯЁа-яё-]+(?:ой|ей|ого)\\s+(?:области|края)|[\\s-][А-ЯЁA-Z][А-Яа-яЁёA-Za-z-]+)?)";
const WQ_MEM = new RegExp("(?:[Жж]иву|[Жж]ив[её]т|[Пп]роживаю|[Пп]роживает|[Нн]ахожусь|[Нн]аходится)\\s+(?:[Вв]о?)\\s+(?:[Гг]ороде\\s+)?" + WQ_PLACE
  + "|(?:[Мм]ой\\s+город|[Гг]ород\\s+проживания|[Рр]одной\\s+город|[Гг]ород)\\s*(?:—|-|:|это)?\\s*" + WQ_PLACE);
// идея №142 (05.11): «я из Минска», «родом из Балашова» — если «живу в …» в памяти нет
const WQ_FROM = new RegExp("(?:^|[\\s,.;])(?:[Яя]\\s+(?:сам[а-яё]*\\s+)?(?:родом\\s+)?из|[Рр]одом\\s+из|[Пп]риехал[а-яё]*\\s+из)\\s+(?:города\\s+)?" + WQ_PLACE);
const WQ_HELLO = /^(?:(?:привет|приветик|приветствую|здравствуй(?:те)?|добрый\s+(?:день|вечер)|доброе\s+утро|хай|салют)(?:\s*,?\s*(?:лира|патрик))?\s*[!,.]*\s+)/;
function wqParse(text) {
  const t = String(text || "").replace(/\s+/g, " ").trim().replace(/^[\s.!?…]+|[\s.!?…]+$/g, "");
  let low = t.toLowerCase().replace(/ё/g, "е");
  low = low.replace(WQ_HELLO, "");                    // экзамен 0.9.18: «Привет! Какая сейчас погода в Минске?» — модель «Давай гляну» без погоды
  low = low.replace(/^(?:(?:а|и|ну|так|слушай|лира|скажи|подскажи)[, ]+)+/, "");
  low = low.replace(/^(?:найди|поищи|посмотри|узнай)(?:\s+(?:в\s+интернете|в\s+сети))?\s+(?:информацию\s+|данные\s+)?(?:о|про|по)\s+погод[а-я]*/, "погода");
  low = low.replace(/\s*(?:у\s+(?:меня|нас)\s+)?(?:в\s+(?:моем|нашем|своем)\s+городе|в\s+городе|у\s+(?:меня|нас))(?=\s|$)/, "").trim();
  if (low.length > 80 || WQ_NOT.test(low)) return null;
  const day = low.includes("послезавтра") ? 2 : low.includes("завтра") ? 1 : 0;
  if (WQ_TEMP.test(low)) return { city: "", day, pre: false };
  const m = low.match(WQ_ASK);
  if (!m || !/погод/.test(low)) return null;
  let rest = low.slice(m[0].length).replace(/^[ ,]+|[ ,]+$/g, "");
  rest = rest.replace(/^(?:сейчас|сегодня|завтра|послезавтра|на\s+завтра|на\s+сегодня|будет|там|за\s+окном|на\s+улице)(?![а-я])\s*/, "").replace(/^[ ,]+|[ ,]+$/g, "");
  let city = "", pre = false;
  const mc = rest.match(/^(?:в|во)\s+(.+)$/);
  const cut = (ws) => { while (ws.length && WQ_TIME.has(ws[ws.length - 1].replace(/,/g, ""))) ws.pop(); return ws.join(" ").replace(/^[ ,]+|[ ,]+$/g, ""); };
  if (mc) { city = cut(mc[1].split(/\s+/).filter(Boolean)); if (!city || city.length > 60) return null; pre = true; }
  else if (rest && !rest.replace(/,/g, " ").split(/\s+/).filter(Boolean).every(w => WQ_TIME.has(w))) {
    if (rest.split(/\s+/).length > 4 || /[^а-яa-z\s,-]/.test(rest)) return null;
    city = cut(rest.split(/\s+/).filter(Boolean));
  }
  if (city) {                                         // как сказали — с заглавной: «в минске» → «Минске»
    const first = city.split(" ")[0], i = t.toLowerCase().replace(/ё/g, "е").indexOf(first);
    if (i >= 0) city = t.slice(i).split(/\s+/).slice(0, city.split(" ").length).join(" ").replace(/^[ ,]+|[ ,]+$/g, "");
    city = city.split(" ").map(w => /^(?:области|края|района|республики)$/i.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  }
  return { city, day, pre: pre && !!city };
}
function wqStems(word) {
  const w = word.trim(), low = w.toLowerCase(), out = [w];
  for (const [end, rep] of [["ском", "ск"], ["ске", "ск"], ["ем", "ий"], ["ом", ""], ["е", "а"], ["е", ""], ["и", "ь"], ["и", "а"], ["ы", "а"], ["у", "а"], ["ой", "ая"], ["ей", "ь"]])
    if (low.endsWith(end) && low.length - end.length >= 3) out.push(w.slice(0, w.length - end.length) + rep);
  if (w.length > 4) out.push(w.slice(0, -1));
  const seen = new Set(); return out.filter(x => !seen.has(x.toLowerCase()) && seen.add(x.toLowerCase()));
}
async function wqGeocode(phrase) {
  const m = phrase.trim().match(/^(.*?)[\s,]+([А-ЯЁа-яё-]+?)(?:ой|ей|ая|ий|ый|ом|ем)?\s+(?:област[ьи]|кра[йя]|республик[аи]|район[ае]?)$/i);
  const name = m ? m[1].replace(/^[ ,]+|[ ,]+$/g, "") : phrase.trim(), region = m ? m[2].toLowerCase().slice(0, 5) : "";
  const words = name.split(/\s+/);
  const tries = words.length === 1 ? wqStems(words[0])
    : wqStems(words[0]).slice(0, 3).flatMap(f => wqStems(words[words.length - 1]).slice(0, 3).map(l => [f, ...words.slice(1, -1), l].join(" "))).slice(0, 6).concat([name]);
  const lo = (x) => String(x || "").toLowerCase().replace(/ё/g, "е");
  for (const q of tries) {
    const g = await meteoGet("https://geocoding-api.open-meteo.com/v1/search?count=10&language=ru&name=" + encodeURIComponent(q));
    let res = g.results || [];
    if (region) res = res.filter(r => lo(r.admin1).includes(region));
    if (!res.length) continue;
    const ql = lo(q);
    res.sort((a, b) => (lo(a.name) !== ql) - (lo(b.name) !== ql) || (!lo(a.name).startsWith(ql.slice(0, 4))) - (!lo(b.name).startsWith(ql.slice(0, 4))) || (b.population || 0) - (a.population || 0));
    const r = res[0];
    if (!lo(r.name).startsWith(ql.slice(0, 3))) continue;
    return { name: r.name, lat: r.latitude, lon: r.longitude, admin1: r.admin1 || "" };
  }
  return null;
}
const wqStored = (p) => p.name + (p.admin1 && p.admin1 !== p.name ? ", " + p.admin1 : "");
const wqDeg = (t) => { t = Math.round(t); return t < 0 ? `минус ${-t}` : t > 0 ? `плюс ${t}` : "ноль"; };
function wqSay(where, f, day) {
  const pre = /^во?\s/i.test(where);
  if (day && f.days.length > day) {
    const x = f.days[day], word = day === 1 ? "Завтра" : "Послезавтра";
    return `${pre ? `${word} ${where}` : `${where}, ${word.toLowerCase()}:`} от ${wqDeg(x.min)} до ${wqDeg(x.max)}°, ${x.sky}` + (x.rain != null ? `, вероятность осадков ${x.rain}%` : "") + ".";
  }
  let out = `${pre ? `Сейчас ${where}` : `${where}, сейчас`} ${wqDeg(f.now)}°, ${f.sky}` + (Math.abs(f.feels - f.now) >= 3 ? `, ощущается как ${wqDeg(f.feels)}` : "") + `, ветер ${f.wind} км/ч.`;
  if (f.days.length) { const x = f.days[0]; out += ` Днём от ${wqDeg(x.min)} до ${wqDeg(x.max)}°, ${x.sky}` + (x.rain != null && x.rain >= 20 ? `, осадки ${x.rain}%` : "") + "."; }
  return out;
}
function wqHome() {
  if (S.weatherCity) return S.weatherCity;
  try { const m = JSON.parse(fileGet("morning.json") || "null"); if (m && m.city) return m.city; } catch (e) { }
  for (const f of S.memory || []) { const m = String(f || "").match(WQ_MEM); if (m) return (m[1] ? "в " + m[1] : m[2] || "").trim(); }   // «живу в Минске» — «в Минске»
  for (const f of S.memory || []) { const m = String(f || "").match(WQ_FROM); if (m) return m[1].trim(); }                          // «я из Минска»
  return "";
}
/* «Лира заметила» (0.97, владелец 14.11: «иногда активировалась и находила полезное — предупредила о дожде… а не так,
   что каждое утро будет злить»). Сам поиск повода — в фоне, Notice.java (раз в ~3 часа: погода на остаток дня,
   день рождения близкого сегодня или завтра; есть повод — одно уведомление, не чаще раза в день, не до 8 и не после 21;
   нет — тишина). Здесь — что ему смотреть: координаты города (запомненного — wqHome) и дни рождения из памяти. */
const NT_MON = ["январ", "феврал", "март", "апрел", "ма[йя]", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"];
function noticeDays(now = new Date()) {
  const out = [], seen = new Set(), facts = [...(S.memory || []).map(String)];
  try { for (const [who, fs] of Object.entries((S.pmem && S.pmem.facts) || {})) (fs || []).forEach(f => facts.push(`${who}: ${f}`)); } catch (e) { }
  for (const f of facts) {
    if (!/д(ень|\.)\s*р(ождени|\.)|др\b/i.test(f)) continue;
    const m = f.match(new RegExp(`(\\d{1,2})\\s+(${NT_MON.join("|")})`, "i")); if (!m) continue;
    const mon = NT_MON.findIndex(x => new RegExp("^" + x, "i").test(m[2])); if (mon < 0) continue;
    const who = (f.match(/(?:^|\s)у\s+([А-ЯЁа-яё-]+)/i) || f.match(/^([^:]+):/) || [])[1] || "";
    for (const add of [0, 1]) {
      const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + add);
      if (d.getMonth() === mon && d.getDate() === +m[1]) {
        const key = d.toDateString() + who; if (seen.has(key)) continue; seen.add(key);
        out.push({ date: isoLocal(d).slice(0, 10), text: who ? `день рождения у ${who.trim()} — не забудьте поздравить` : "чей-то день рождения из вашей памяти" });
      }
    }
  }
  return out.slice(0, 4);
}
async function noticeSync() {
  if (!D.notice) return;
  const n = S.notice || {};
  let j = "";
  if (n.on) {
    const city = wqHome().replace(/^во?\s+/i, "");
    if (city && (!S.noticeGeo || S.noticeGeo.city !== city)) {
      try { const q = await wqGeocode(city); if (q) { S.noticeGeo = { city, lat: q.lat, lon: q.lon }; prefSet("settings", JSON.stringify(S)); } } catch (e) { }
    }
    const g = S.noticeGeo && S.noticeGeo.city === city ? S.noticeGeo : null;
    // «Интересное в мире»: исключительная новость (оценка с учётом вкуса ≥ 9) — тоже повод, не чаще 2 раз в неделю (Notice.java)
    const wt = worldTaste(), world = wt.on && !kidsOn() ? { base: annBase(), w: worldWeights(), seen: wt.seen.slice(-40) } : null;
    j = JSON.stringify(Object.assign({ on: true, lang: appEn() ? "en" : "ru", who: trL((persona() || {}).name || "Лира"), days: noticeDays().map(d => Object.assign(d, { text: trL(d.text) })) },
      g ? { lat: g.lat, lon: g.lon, place: g.city } : {}, world ? { world } : {}));
  }
  if (j !== noticeSync.last) { noticeSync.last = j; try { D.notice(j); } catch (e) { } }
}
function noticeSet(on) {
  S.notice = Object.assign({}, S.notice || {}, { on: !!on, asked: true }); saveS();
  hUse(on ? "sh:notice_on" : "sh:notice_off");
  noticeSync();
}
/* предложить один раз — после первого настоящего ответа, на следующий день после установки или позже */
function noticeOffer() {
  if (!D.notice || D.mock || (S.notice && S.notice.asked) || $("#nt-offer")) return;
  const first = +S.firstRun || 0; if (!first) { S.firstRun = Date.now(); saveS(); return; }
  if (Date.now() - first < 20 * 3600e3) return;
  const el = document.createElement("div"); el.id = "nt-offer"; el.className = "nt-offer";
  el.innerHTML = `<p><b>Подсказывать, если замечу важное?</b><span>Дождь или снег сегодня, день рождения близкого — одно уведомление, не чаще раза в день. Нечего сказать — молчу.</span></p>
    <div><button class="btn" id="nt-yes">Да</button><button class="btn ghost" id="nt-no">Не надо</button></div>`;
  const st = $("#stage"); if (!st) return; st.appendChild(el);
  $("#nt-yes").onclick = async () => {
    el.remove(); await needPerm("android.permission.POST_NOTIFICATIONS").catch(() => {});
    noticeSet(true);
    if (!wqHome()) { const c = (prompt("В каком вы городе? Чтобы предупреждать о погоде.") || "").trim(); if (c) { S.weatherCity = "в " + c.replace(/^во?\s+/i, ""); saveS(); noticeSync(); } }
    toast("Хорошо — скажу, только когда замечу важное");
  };
  $("#nt-no").onclick = () => { el.remove(); noticeSet(false); toast("Не буду. Включить — «Настройки» → «Звук»"); };
}
async function weatherQuick(text) {
  const c = wqParse(text); if (!c) return null;
  let phrase = c.city, pre = c.pre;
  if (!phrase) { const h = wqHome(); pre = /^в\s/.test(h); phrase = h.replace(/^в\s+/, ""); }
  if (!phrase) return { say: "В каком вы городе? Скажите, например: «погода в Минске» — я запомню и дальше буду говорить сразу." };
  let place, f;
  try {
    place = await wqGeocode(phrase);
    if (!place) return c.city ? null : { say: `Не нашла город «${phrase}». Скажите: «погода в …» — с названием города.` };
    const w = await meteoGet(`https://api.open-meteo.com/v1/forecast?latitude=${place.lat}&longitude=${place.lon}&timezone=auto&forecast_days=3&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max`);
    const cu = w.current || {}, d = w.daily || {};
    f = { now: Math.round(cu.temperature_2m || 0), feels: Math.round(cu.apparent_temperature || 0), sky: WMO[cu.weather_code] || "", wind: Math.round(cu.wind_speed_10m || 0),
      days: (d.time || []).map((_, i) => ({ min: Math.round(d.temperature_2m_min[i]), max: Math.round(d.temperature_2m_max[i]), sky: WMO[d.weather_code[i]] || "", rain: (d.precipitation_probability_max || [])[i] })) };
  } catch (e) { plog("info", "🌦 погода: " + (e.message || e)); return { say: "Прогноз сейчас не получить — сервис погоды не отвечает. Попробуйте через минуту." }; }
  if (c.city && !S.weatherCity) { S.weatherCity = wqStored(place); saveS(); plog("info", "🌦 город для погоды: " + S.weatherCity); }
  const where = /^во?\s/i.test(phrase) ? phrase : pre ? "в " + phrase : place.name;
  plog("info", `🌦 погода без модели: ${wqStored(place)}`);
  const hello = WQ_HELLO.exec(String(text || "").toLowerCase().replace(/ё/g, "е").trim());
  const say = (hello ? (/здравств|добр|приветств/.test(hello[0]) ? "Здравствуйте! " : "Привет! ") : "") + wqSay(where, f, c.day);
  // экзамен 0.9.18: прогноз без модели судья принял за выдумку («вызовов нет») — в песочнице экзамена видно, откуда числа
  if (SANDBOX) SANDBOX.dev.push({ name: "weather", args: `${wqStored(place)}${c.day ? ", через " + c.day + " дн." : ""}`, result: "прогноз Open-Meteo получен приложением, без модели: " + say, t: Date.now() });
  return { say };
}

