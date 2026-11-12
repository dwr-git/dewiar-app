/* Студия → «Главная» (24.10, владелец: «вот я внутри программы, как бы в её настройках… часть разделов — настройки, раз
   настроил и больше не идёшь, а часть — которыми пользуешься; сделать первичную красивую страничку с иконками, как на
   айфоне… главное — здесь же включить нужное и убрать ненужное»).
   Сверху — приветствие и «Сегодня» (ближайшее дело, письмо близкого, задача ждёт ответа, сделано сегодня); ниже —
   «Приложения» (значки; «Настроить главную» — показать или скрыть, перетащить), «Продолжить» (последний разговор и
   блокнот), «Настройка» (то, что настраивают один раз). Выбор значков — ui.home_apps (порядок и состав). */
/* рисунки — маленькие сцены из тонких линий на сетке 48×48 (24.10, владелец: «прекрасен»): ln — главный штрих, th — тонкие
   детали, sf — мягкая заливка, dt — точки, bg — подложка цвета плитки (чтобы детали не просвечивали), tx — цифра даты */
const HM_SVG = (g, d) => `<svg viewBox="0 0 48 48" class="hmx" style="--hg:url(#hg${g})">${d}</svg>`;
const HM_APPS = [
  { id: "chat", name: "Чат", sub: "с персонажами", g: 1, d: '<path class="sf" d="M6 12a6 6 0 0 1 6-6h16a6 6 0 0 1 6 6v9a6 6 0 0 1-6 6H17l-7 5.5V26.6A6 6 0 0 1 6 21z"/><path class="ln" d="M6 12a6 6 0 0 1 6-6h16a6 6 0 0 1 6 6v9a6 6 0 0 1-6 6H17l-7 5.5V26.6A6 6 0 0 1 6 21z"/><path class="ln" d="M23 30.5v.5a5 5 0 0 0 5 5h7l5.5 4.5V35.6A5 5 0 0 0 43 31v-6a5 5 0 0 0-5-5h-1.5"/><circle class="dt" cx="14" cy="16.5" r="1.7"/><circle class="dt" cx="20" cy="16.5" r="1.7"/><circle class="dt" cx="26" cy="16.5" r="1.7"/><path class="th" d="M29 31h7M29 34.5h4"/>' },
  { id: "close", name: "Близкие", sub: "переписка и звонки", g: 2, d: '<path class="sf" d="M17 40S5 32.6 5 23.5A6.5 6.5 0 0 1 17 20a6.5 6.5 0 0 1 12 3.5C29 32.6 17 40 17 40z"/><path class="ln" d="M17 40S5 32.6 5 23.5A6.5 6.5 0 0 1 17 20a6.5 6.5 0 0 1 12 3.5C29 32.6 17 40 17 40z"/><path class="sf2" d="M33 24s-8-4.8-8-10.4A4.4 4.4 0 0 1 33 11a4.4 4.4 0 0 1 8 2.6C41 19.2 33 24 33 24z"/><path class="ln" d="M33 24s-8-4.8-8-10.4A4.4 4.4 0 0 1 33 11a4.4 4.4 0 0 1 8 2.6C41 19.2 33 24 33 24z"/><path class="th" d="M10.5 24a3 3 0 0 1 3-2.5M40 32c1.6 1 2.6 2.6 2.8 4.5M37.5 35.5c.8.6 1.3 1.4 1.4 2.4"/><circle class="dt" cx="8" cy="12" r="1.4"/>' },
  { id: "calendar", name: "Календарь", sub: "события и дни", g: 3, d: `<rect class="sf" x="7" y="10" width="34" height="31" rx="7"/><rect class="ln" x="7" y="10" width="34" height="31" rx="7"/><path class="ln" d="M7 19h34M16 6v8M32 6v8"/><text class="tx" x="24" y="35.5" text-anchor="middle">${new Date().getDate()}</text><path class="th" d="M12 24h3M33 24h3"/>` },
  { id: "reminders", name: "Дела", sub: "и напоминания", g: 4, d: '<path class="sf" d="M13 32V22a11 11 0 0 1 22 0v10l3 4H10z"/><path class="ln" d="M13 32V22a11 11 0 0 1 22 0v10l3 4H10z"/><path class="ln" d="M20 40a4.2 4.2 0 0 0 8 0M24 8v3"/><path class="th" d="M6 18a17 17 0 0 1 5-8M42 18a17 17 0 0 0-5-8M3.5 21a21 21 0 0 1 3-10M44.5 21a21 21 0 0 0-3-10"/><circle class="bg" cx="36" cy="33.5" r="6.5"/><circle class="ln" cx="36" cy="33.5" r="6.5"/><path class="ln" d="M33.2 33.6l2 2 3.6-3.8"/>' },
  { id: "notes", name: "Заметки", sub: "поиск, фото, файлы", g: 5, d: '<rect class="sf" x="11" y="7" width="27" height="35" rx="4"/><rect class="ln" x="11" y="7" width="27" height="35" rx="4"/><path class="ln" d="M8 12h6M8 19h6M8 26h6M8 33h6"/><path class="th" d="M19 15h13M19 20h13M19 25h9"/><path class="bg" d="M27.5 37.5l13-13 3 3-13 13-4 1z"/><path class="ln" d="M27.5 37.5l13-13 3 3-13 13-4 1z"/><path class="th" d="M38 27l3 3"/>' },
  { id: "ideas", name: "Идеи Лиры", sub: "что делать дальше", g: 4, d: '<path class="sf" d="M24 6a12 12 0 0 0-7.2 21.6c1.4 1 2.2 2.6 2.2 4.4V33h10v-1c0-1.8.8-3.4 2.2-4.4A12 12 0 0 0 24 6z"/><path class="ln" d="M24 6a12 12 0 0 0-7.2 21.6c1.4 1 2.2 2.6 2.2 4.4V33h10v-1c0-1.8.8-3.4 2.2-4.4A12 12 0 0 0 24 6z"/><path class="ln" d="M19 38h10M20.5 42.5h7"/><path class="th" d="M20.5 20.5 24 24l3.5-3.5M24 24v9"/><circle class="dt" cx="38" cy="10" r="1.6"/><circle class="dt" cx="9" cy="13" r="1.3"/>' },
  { id: "council", name: "Совет ИИ", sub: "спорят и советуют", g: 8, d: '<circle class="sf" cx="24" cy="30" r="12"/><circle class="ln" cx="24" cy="30" r="12"/><circle class="bg" cx="24" cy="11" r="5.5"/><circle class="ln" cx="24" cy="11" r="5.5"/><circle class="bg" cx="9" cy="21" r="5"/><circle class="ln" cx="9" cy="21" r="5"/><circle class="bg" cx="39" cy="21" r="5"/><circle class="ln" cx="39" cy="21" r="5"/><path class="th" d="M18 28.5h12M18 33h8"/>' },
  { id: "podcast", name: "Подкасты", sub: "двое обсудят вслух", g: 9, d: '<rect class="sf" x="17" y="5" width="14" height="23" rx="7"/><rect class="ln" x="17" y="5" width="14" height="23" rx="7"/><path class="th" d="M21 12h6M21 17h6"/><path class="ln" d="M10 22a14 14 0 0 0 28 0M24 36v6M17 42h14"/><path class="th" d="M5 18v6M43 18v6"/>' },
  { id: "watch", name: "Дозор", sub: "скажу, когда готово", g: 3, d: '<path class="sf" d="M3 24S11 11 24 11s21 13 21 13-8 13-21 13S3 24 3 24z"/><path class="ln" d="M3 24S11 11 24 11s21 13 21 13-8 13-21 13S3 24 3 24z"/><circle class="bg" cx="24" cy="24" r="7.5"/><circle class="ln" cx="24" cy="24" r="7.5"/><circle class="dt" cx="24" cy="24" r="3.2"/><path class="th" d="M24 3.5v4M12 6.5l2.2 3.4M36 6.5l-2.2 3.4"/>' },
  { id: "docs", name: "Документы", sub: "ответы по вашим папкам", g: 9, d: '<rect class="th" x="15" y="5" width="24" height="30" rx="4"/><rect class="bg" x="8" y="10" width="24" height="31" rx="4"/><rect class="sf" x="8" y="10" width="24" height="31" rx="4"/><rect class="ln" x="8" y="10" width="24" height="31" rx="4"/><path class="th" d="M14 18h12M14 23h12M14 28h7"/><circle class="bg" cx="33" cy="33" r="7.5"/><circle class="ln" cx="33" cy="33" r="7.5"/><path class="ln" d="M38.5 38.5 43 43"/><circle class="dt" cx="33" cy="33" r="2"/>' },
  { id: "pay", name: "Платежи", sub: "счета и сроки", g: 7, d: '<path class="sf" d="M10 7.5A2.5 2.5 0 0 1 12.5 5h19A2.5 2.5 0 0 1 34 7.5V41l-3.6-2.6-3.6 2.6-3.6-2.6-3.6 2.6-3.6-2.6L10 41z"/><path class="ln" d="M10 7.5A2.5 2.5 0 0 1 12.5 5h19A2.5 2.5 0 0 1 34 7.5V41l-3.6-2.6-3.6 2.6-3.6-2.6-3.6 2.6-3.6-2.6L10 41z"/><path class="th" d="M15 12.5h14M15 17.5h9M15 22.5h11"/><path class="ln" d="M15 29h6"/><circle class="bg" cx="35.5" cy="31.5" r="7.5"/><circle class="ln" cx="35.5" cy="31.5" r="7.5"/><path class="ln" d="M32.2 31.6l2.3 2.3 4.2-4.4"/>' },
  { id: "family", name: "Семья", sub: "общий бюджет", g: 3, d: '<path class="sf" d="M7 40V30.5A6.5 6.5 0 0 1 13.5 24h5A6.5 6.5 0 0 1 25 30.5V40z"/><path class="ln" d="M7 40V30.5A6.5 6.5 0 0 1 13.5 24h5A6.5 6.5 0 0 1 25 30.5V40"/><circle class="bg" cx="16" cy="15" r="5.5"/><circle class="ln" cx="16" cy="15" r="5.5"/><path class="sf2" d="M24 40v-7a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v7z"/><path class="ln" d="M24 40v-7a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v7"/><circle class="bg" cx="31" cy="20.5" r="4.5"/><circle class="ln" cx="31" cy="20.5" r="4.5"/><circle class="bg" cx="38.5" cy="11.5" r="5.5"/><circle class="ln" cx="38.5" cy="11.5" r="5.5"/><path class="th" d="M38.5 8.8v5.4M36.6 10.2h2.9a1.3 1.3 0 0 1 0 2.6h-2a1.3 1.3 0 0 0 0 2.6h3"/><path class="th" d="M4 40h40"/>' },
  { id: "vault", name: "Сейф", sub: "пароли и коды", g: 4, d: '<rect class="sf" x="9" y="20" width="30" height="22" rx="7"/><rect class="ln" x="9" y="20" width="30" height="22" rx="7"/><path class="ln" d="M16 20v-5.5a8 8 0 0 1 16 0V20"/><circle class="bg" cx="24" cy="30" r="3.4"/><circle class="ln" cx="24" cy="30" r="3.4"/><path class="ln" d="M24 33.4v3.6"/><path class="th" d="M14 26h3M31 26h3"/>' },
  { id: "music", name: "Музыка", sub: "своя папка и радио", g: 8, d: '<circle class="sf" cx="15" cy="35" r="7"/><circle class="ln" cx="15" cy="35" r="7"/><circle class="sf2" cx="34" cy="31" r="7"/><circle class="ln" cx="34" cy="31" r="7"/><path class="ln" d="M22 35V12l19-5v24"/><path class="ln" d="M22 18l19-5"/><path class="th" d="M6 14a7 7 0 0 1 4-5M4 18a11 11 0 0 1 3-11"/><circle class="dt" cx="15" cy="35" r="1.8"/><circle class="dt" cx="34" cy="31" r="1.8"/>' },
  // «Режимы» вместо «Дети» (28.10, владелец: «удобнее, чтобы режимы удобно переключались… иконка с совой на главной не нужна?»):
  // нажали — «Для кого эта Лира?» (studio/modes.js); подпись — какой режим сейчас
  { id: "modes", name: "Режимы", sub: "для кого Лира", g: 2, d: '<rect class="sf" x="3" y="12" width="42" height="24" rx="12"/><rect class="ln" x="3" y="12" width="42" height="24" rx="12"/><circle class="dt" cx="27" cy="24" r="2.4"/><circle class="dt" cx="37" cy="24" r="2.4"/><circle class="bg" cx="15" cy="24" r="8.5"/><circle class="ln" cx="15" cy="24" r="8.5"/><circle class="sf2" cx="15" cy="24" r="4.2"/><path class="th" d="M11 6.5l2 2.6M19 6.5l-2 2.6M15 4.5v3.4"/>' },
  { id: "qa", name: "Вопрос — ответ", sub: "всё о Лире", g: 1, d: '<circle class="sf" cx="22" cy="22" r="15"/><circle class="ln" cx="22" cy="22" r="15"/><path class="ln" d="M17.5 18a4.6 4.6 0 0 1 9 1.4c0 3-4.5 3.4-4.5 6.4"/><circle class="dt" cx="22" cy="30.5" r="1.9"/><circle class="bg" cx="36" cy="36" r="7"/><circle class="ln" cx="35" cy="35" r="5.2"/><path class="ln" d="M39 39l4.5 4.5"/>' },
  { id: "tasks", name: "Задачи", sub: "большая работа", g: 6, d: '<rect class="sf" x="9" y="9" width="30" height="33" rx="5"/><rect class="ln" x="9" y="9" width="30" height="33" rx="5"/><path class="bg" d="M18 6.5h12a2 2 0 0 1 2 2V12H16V8.5a2 2 0 0 1 2-2z"/><path class="ln" d="M18 6.5h12a2 2 0 0 1 2 2V12H16V8.5a2 2 0 0 1 2-2z"/><path class="ln" d="M14.5 20l2 2 3.6-3.8M14.5 29l2 2 3.6-3.8"/><path class="th" d="M24 20.5h9M24 29.5h9"/><path class="ln" d="M15 37h18" opacity=".35"/><path class="ln" d="M15 37h11"/>' },
  { id: "sites", name: "Сайты", sub: "делает Лира", g: 3, d: '<rect class="sf" x="5" y="7" width="38" height="34" rx="6"/><rect class="ln" x="5" y="7" width="38" height="34" rx="6"/><path class="ln" d="M5 15h38"/><circle class="dt" cx="10.5" cy="11" r="1.4"/><circle class="dt" cx="15" cy="11" r="1.4"/><rect class="bg" x="10" y="20" width="14" height="15" rx="2.5"/><rect class="ln" x="10" y="20" width="14" height="15" rx="2.5"/><path class="th" d="M29 21h9M29 26h9M29 31h6"/><path class="ln" d="M36.5 34.5l3 3"/><path class="dt" d="M41 3.5l1.1 2.6 2.6 1.1-2.6 1.1L41 10.9l-1.1-2.6-2.6-1.1 2.6-1.1z"/>' },
  { id: "clients", name: "Клиенты", sub: "договорённости", g: 6, d: '<circle class="bg" cx="19" cy="17" r="7"/><circle class="ln" cx="19" cy="17" r="7"/><path class="ln" d="M7 40a12 12 0 0 1 24 0"/><path class="th" d="M30 10.5a6.5 6.5 0 0 1 0 13M34 28a11 11 0 0 1 7 12"/>' },
  { id: "pbot", name: "Бот в Telegram", sub: "отвечает людям", g: 1, d: '<path class="sf" d="M42 7 5 21.5l11 4.2L35 13 20.5 28.5 31 40z"/><path class="ln" d="M42 7 5 21.5l11 4.2M42 7l-11 33-10.5-11.5M42 7 16 25.7V36l4.5-7.5"/><circle class="bg" cx="12" cy="38" r="6"/><circle class="dt" cx="12" cy="38" r="2.4"/><path class="th" d="M4 31a9 9 0 0 1 4-4M20 31a9 9 0 0 0-4-4"/>' },
  { id: "team", name: "Поручения", sub: "сотрудникам", g: 6, d: '<rect class="sf" x="6" y="15" width="36" height="26" rx="6"/><rect class="ln" x="6" y="15" width="36" height="26" rx="6"/><path class="ln" d="M18 15v-3.5A3.5 3.5 0 0 1 21.5 8h5A3.5 3.5 0 0 1 30 11.5V15"/><path class="th" d="M6 25h36"/><circle class="bg" cx="24" cy="31" r="6.5"/><path class="ln" d="M20.8 31l2.2 2.2 4.4-4.6"/>' },
  { id: "play", name: "Досуг", sub: "игры на пару минут", g: 7, d: '<path class="sf" d="M15 15h18a10 10 0 0 1 9.6 12.8l-2.2 7.5a5 5 0 0 1-8.6 1.9L28 33h-8l-3.8 4.2a5 5 0 0 1-8.6-1.9l-2.2-7.5A10 10 0 0 1 15 15z"/><path class="ln" d="M15 15h18a10 10 0 0 1 9.6 12.8l-2.2 7.5a5 5 0 0 1-8.6 1.9L28 33h-8l-3.8 4.2a5 5 0 0 1-8.6-1.9l-2.2-7.5A10 10 0 0 1 15 15z"/><path class="ln" d="M15.5 21v7M12 24.5h7"/><circle class="dt" cx="31" cy="22.5" r="2"/><circle class="dt" cx="35" cy="26.5" r="2"/><path class="th" d="M24 6v4M18 8l2 3M30 8l-2 3"/>' },
  { id: "prompter", name: "Суфлёр", sub: "подсказки на встречах", g: 8, d: '<rect class="sf" x="5" y="8" width="38" height="24" rx="5"/><rect class="ln" x="5" y="8" width="38" height="24" rx="5"/><path class="th" d="M11 15h17M11 20h22M11 25h12"/><path class="ln" d="M35 13.5v4M33 15.5h4"/><path class="ln" d="M24 32v8M16 41h16"/><path class="th" d="M38 40a5 5 0 0 0 4-4.5"/>' },
  { id: "memory", name: "Память", sub: "что Лира знает", g: 1, d: '<circle class="sf" cx="24" cy="24" r="17"/><circle class="ln" cx="24" cy="24" r="17"/><ellipse class="th" cx="24" cy="24" rx="17" ry="7"/><ellipse class="th" cx="24" cy="24" rx="7" ry="17"/><path class="ln" d="M14 18l9 5 9-9M23 23l2 11 9-5M14 18l-1 12 12 4"/><circle class="dt" cx="14" cy="18" r="2.2"/><circle class="dt" cx="23" cy="23" r="2.6"/><circle class="dt" cx="32" cy="14" r="2"/><circle class="dt" cx="25" cy="34" r="2"/><circle class="dt" cx="34" cy="29" r="1.6"/><circle class="dt" cx="13" cy="30" r="1.6"/>' },
  // «Нода Лиры» (0.87): компьютер помогает Лире отвечать другим людям и зарабатывает талеры (studio/node.js)
  { id: "node", name: "Нода Лиры", sub: "талеры за помощь", g: 5, d: '<circle class="sf" cx="24" cy="24" r="8"/><circle class="ln" cx="24" cy="24" r="8"/><circle class="th" cx="24" cy="24" r="15"/><circle class="th" cx="24" cy="24" r="21"/><circle class="dt" cx="24" cy="9" r="2.4"/><circle class="dt" cx="37" cy="31.5" r="2.4"/><circle class="dt" cx="11" cy="31.5" r="2.4"/><circle class="dt" cx="41" cy="12" r="1.6"/><circle class="dt" cx="6" cy="18" r="1.6"/>' },
  // «Радар» (0.91): Лира читает источники темы, ищет тренды и шлёт срочное (studio/insight.js); подписи — из словаря
  { id: "insight", get name() { return window.t("nav.insight"); }, get sub() { return window.t("insight.home.sub"); }, g: 8, d: '<circle class="sf" cx="24" cy="25" r="18"/><path class="sf2" d="M24 25V7a18 18 0 0 1 14.6 7.5z"/><circle class="ln" cx="24" cy="25" r="18"/><circle class="th" cx="24" cy="25" r="11.5"/><circle class="th" cx="24" cy="25" r="5"/><path class="ln" d="M24 25l14.6-10.5"/><circle class="dt" cx="31" cy="18.5" r="2.3"/><circle class="dt" cx="14.5" cy="31" r="1.7"/><circle class="dt" cx="33.5" cy="33" r="1.4"/><path class="th" d="M41 6.5l1.2 2.6 2.6 1.2-2.6 1.2L41 14l-1.2-2.5-2.6-1.2 2.6-1.2z"/>' },
  { id: "ref", name: "Рефералы", sub: "приглашённые", g: 2, d: '<circle class="sf" cx="24" cy="24" r="8"/><circle class="ln" cx="24" cy="21.5" r="3.2"/><path class="ln" d="M18.5 30a5.5 5.5 0 0 1 11 0"/><path class="th" d="M17 18L11 12M31 18l6-6M17 31l-6 5M31 31l6 5"/><circle class="ln" cx="9" cy="10" r="3"/><circle class="ln" cx="39" cy="10" r="3"/><circle class="ln" cx="9" cy="38" r="3"/><circle class="ln" cx="39" cy="38" r="3"/><path class="dt" d="M39 18.5l.8 1.7 1.8.3-1.3 1.3.3 1.8-1.6-.9-1.6.9.3-1.8-1.3-1.3 1.8-.3z"/>' }];
// по умолчанию видно всё (у тех, кто ещё не настраивал, ничего не пропадает); скрытое с главной — скрыто и в меню слева
// (24.10, владелец: «если с главной отключаю „Рефералы“ — то и слева должно исчезать… иначе не решили нахлобученность»)
const HM_DEFAULT = ["chat", "close", "family", "calendar", "reminders", "notes", "council", "podcast", "watch", "docs", "pay", "vault", "music", "modes", "qa", "ideas", "tasks", "sites", "team", "clients", "pbot", "play", "prompter", "insight", "memory", "ref", "node"];
/* Новые приложения после выпуска (25.10: «Платежи», «Сейф») у тех, кто уже настраивал главную, — появляются сами, в конце:
   ui.home_known — какие значки человек уже видел, когда настраивал; кого там нет — новый. */
const HM_OLD = ["chat", "close", "calendar", "reminders", "notes", "tasks", "play", "pad", "prompter", "memory", "folder", "ref"];
const HM_NAV = { council: ["council"], podcast: ["podcast"], pbot: ["pbot"], ideas: ["ideas"], chat: ["chat"], docs: ["docs"], watch: ["watch"], close: ["close"], calendar: ["calendar"], reminders: ["reminders"], notes: ["notes"], tasks: ["tasks"],
  prompter: ["prompter"], memory: ["memory"], ref: ["ref"], pay: ["pay"], vault: ["vault"], family: ["family"], music: ["music"], modes: ["kids", "senior"], qa: ["qa"], team: ["team"], clients: ["clients"], sites: ["sites"], node: ["node"], insight: ["insight"] };
/* Два разных переключателя (24.10, владелец: «включить или нет вообще — или показать или скрыть, это разное»):
   — здесь, на «Главной», — только ПОКАЗАТЬ / СКРЫТЬ: значок и раздел в меню; сама функция работает (Лира помнит,
     письма близких приходят, напоминания звенят);
   — «Возможности» — ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ совсем (игры, суфлёр…): выключенное пропадает отовсюду само. */
const HM_FEAT = { play: "games", prompter: "prompter", family: "family", team: "team", clients: "clients", sites: "sites" };
const HM_OPTIN = { family: 1, team: 1, clients: 1 };                                  // по желанию: видно, только когда включили (27.10)
const hmFeat = (id) => { if (!HM_FEAT[id]) return true; const v = ((S && S.features) || {})[HM_FEAT[id]]; return HM_OPTIN[id] ? v === true : v !== false; };
/* №558 (05.11): «чтобы в левой колонке был именно тот порядок, который я настроил под себя». Значки на «Главной»
   переставляют перетаскиванием (ui.home_apps); теперь в том же порядке и разделы меню — внутри своих групп («Для себя»,
   «Работа»…): группы и их заголовки на месте, двигаются только разделы со значком на «Главной», остальные — где были.
   Плагины в группе «Плагины» — тоже по главной (plugpage.js plpNav). Пока главную не настраивали — порядок меню свой. */
function hmOrder() {
  const a = ((S && S.ui) || {}).home_apps;
  if (!Array.isArray(a) || !a.length) return null;
  const r = {}; a.forEach((id, i) => { const k = id === "kids" ? "modes" : id; if (!(k in r)) r[k] = i; });
  return r;
}
window.hmOrder = hmOrder;
function hmNavSort() {
  const rank = hmOrder(), nav = $("nav"); if (!rank || !nav) return;
  const app = {}; for (const [id, ps] of Object.entries(HM_NAV)) for (const p of ps) app[p] = id;
  const rk = (el) => el.tagName === "BUTTON" && !el.classList.contains("sub") && el.dataset.p && app[el.dataset.p] in rank ? rank[app[el.dataset.p]] : null;
  let grp = [];
  const flush = (ref) => {
    // раздел едет вместе со своей строкой «+ Поручения» (.nopt) сразу за ним
    const units = [], slot = new Set();
    grp.forEach((el, i) => { if (rk(el) == null) return; const u = [el]; let j = i + 1;
      while (grp[j] && grp[j].classList.contains("nopt")) u.push(grp[j++]);
      units.push({ r: rk(el), i, u }); slot.add(i); });
    if (units.length < 2) return;
    const sorted = units.slice().sort((a, b) => a.r - b.r || a.i - b.i);
    if (sorted.every((x, n) => x === units[n])) return;                     // уже по порядку — DOM не трогаем
    const moved = new Set(units.flatMap(x => x.u.slice(1))), seq = []; let n = 0;
    grp.forEach((el, i) => { if (slot.has(i)) seq.push(...sorted[n++].u); else if (!moved.has(el)) seq.push(el); });
    seq.forEach(el => nav.insertBefore(el, ref));
  };
  for (const el of [...nav.children]) {
    if (el.classList.contains("ng") || el.classList.contains("grow")) { flush(el); grp = []; } else grp.push(el);
  }
  flush(null);
  if (typeof plpNav === "function" && typeof PLP !== "undefined" && PLP.cat && PLP.cat.length) plpNav();
}
/** Меню слева — по главной: скрытый значок прячет свой раздел; открыт спрятанный раздел — на «Главную». */
function hmNav() {
  if (!S) return;
  const shown = hmApps();
  try { hmNavSort(); } catch (e) { console.error(e); }
  for (const [id, ps] of Object.entries(HM_NAV)) {
    const off = !shown.includes(id) || !hmFeat(id);
    for (const p of ps) { const b = $(`nav button[data-p="${p}"]`); if (b) b.hidden = off; }
  }
  /* 28.10, владелец: «не вижу слева „Семья“, в „Работе“ — поручений». Разделы «по желанию» выключены, пока их не включат
     в «Возможностях», — и о них никто не знал. Теперь на их месте в меню — тихая строка «+ Поручения»: нажали — включено
     и открыто (выключить — в «Возможностях»). На «Главной» спрятали значок сами — строки нет. */
  for (const [id, feat] of Object.entries(HM_FEAT)) {
    if (!HM_OPTIN[id]) continue;
    const b = $(`nav button[data-p="${(HM_NAV[id] || [id])[0]}"]`); if (!b) continue;
    const name = [...b.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join("").trim();
    let o = b.nextElementSibling && b.nextElementSibling.classList.contains("nopt") ? b.nextElementSibling : null;
    const want = ((S && S.features) || {})[feat] !== true && shown.includes(id);
    if (want && !o) {
      o = document.createElement("button"); o.className = "nopt"; o.dataset.feat = feat;
      o.title = `Включить «${name}» — выключить можно в «Возможностях»`;
      o.innerHTML = `<i aria-hidden="true">+</i>${name}`;
      o.onclick = async () => { await save({ features: { [feat]: true } }, true); toast(`«${name}»: включено — выключить можно в «Возможностях»`); b.hidden = false; b.click(); };
      b.after(o);
    }
    if (o) o.hidden = !want;
  }
  if (typeof shNav === "function") shNav();                     // «Оформление» → «Что показывать» (show.js): класс .nh
  const cur = $("nav button.cur");
  if (cur && (cur.hidden || cur.classList.contains("nh"))) { const h = $('nav button[data-p="home"]'); if (h) h.click(); }
  $$("nav .ng").forEach(g => {                                   // заголовок группы, под которым всё скрыто, — тоже прочь
    let n = g.nextElementSibling, any = false;
    while (n && !n.classList.contains("ng")) {
      if (!n.hidden && !n.classList.contains("nh") && (n.tagName === "BUTTON" || (n.classList.contains("nav-groups") && n.querySelector("button")))) any = true;
      n = n.nextElementSibling;
    }
    g.hidden = !any;
  });
  if (typeof featuresRender === "function") featuresRender();   // «Возможности» показывают то же положение (0.74)
}
window.hmNav = hmNav;

/* Группы меню сворачиваются (24.10, владелец: «„Настройка“, „Знания“ — сворачиваемыми, с запоминанием»): щелчок по
   заголовку; что свёрнуто — ui.nav_fold (в настройках, переживает перезапуск). Открытый раздел в свёрнутой группе
   остаётся виден — чтобы было понятно, где вы. */
const ngKey = (g) => g.dataset.foldK || g.dataset.k || (g.dataset.k = g.textContent.trim());   // data-fold-k — прежнее русское имя: свёрнутость не теряется при смене языка (0.88)
function ngApply() {
  const f = new Set(((S && S.ui) || {}).nav_fold || []);
  $$("nav .ng").forEach(g => {
    const on = f.has(ngKey(g));
    g.classList.toggle("fold", on); g.setAttribute("aria-expanded", String(!on));
    let n = g.nextElementSibling;
    while (n && !n.classList.contains("ng")) {
      // владелец 11.11: «включённые плагины не сворачиваются… сжирают много места» — пункты плагинов и групп «Близких»
      // лежат в своих блоках (.nav-groups): сворачиваются вместе с заголовком; открытый сейчас — виден
      const btns = n.tagName === "BUTTON" ? [n] : n.classList.contains("nav-groups") ? [...n.querySelectorAll("button")] : [];
      btns.forEach(x => x.classList.toggle("folded", on && !x.classList.contains("cur")));
      n = n.nextElementSibling;
    }
  });
}
function ngToggle(g) {
  const f = new Set(((S && S.ui) || {}).nav_fold || []), k = ngKey(g);
  f.has(k) ? f.delete(k) : f.add(k);
  const list = [...f];
  if (S) S.ui = Object.assign({}, S.ui, { nav_fold: list });
  ngApply();
  core.call("settings_save", { patch: { ui: { nav_fold: list } } }).catch(() => { });
}
$$("nav .ng").forEach(g => {
  g.setAttribute("role", "button"); g.tabIndex = 0; g.title = t("nav.fold");
  g.onclick = () => ngToggle(g);
  g.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ngToggle(g); } };
});
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("nav button[data-p]")) setTimeout(ngApply, 0); });
window.ngApply = ngApply;
const HM_SET = [["personas", "Персонажи"], ["brain", "Мозг"], ["ears", "Слух"], ["voice", "Голос"], ["look", "Оформление"], ["sound", "Звук и поведение"],
  ["hands", "Руки"], ["connect", "Подключение"], ["features", "Возможности"], ["dw", "Dewiar.pro"], ["safety", "Безопасность"], ["about", "О программе"]];
const HM = { edit: false, data: {} };
const hmEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
/* Плагины на «Главной» (25.10, владелец: «может быть плагины также иметь возможность показывать на главной»): каждый
   установленный плагин — свой значок (его эмодзи и цвет); нажать — «Плагины», открыта его карточка (что сказать,
   настройки). Как и остальные значки, скрывается в «Настроить главную»; новый установленный — появляется сам. */
const hmAll = () => HM_APPS.concat((HM.plg || []).map(p => ({ id: "plg:" + p.id, name: p.name, sub: p.tagline || "плагин", plg: p })));
function hmApps() {
  const u = (S && S.ui) || {}, a = u.home_apps, all = hmAll(), plg = all.filter(x => x.plg).map(x => x.id);
  if (!Array.isArray(a) || !a.length) return HM_DEFAULT.filter(id => all.some(x => x.id === id)).concat(plg);
  const known = (Array.isArray(u.home_known) && u.home_known.length ? u.home_known : HM_OLD).map(id => id === "kids" ? "modes" : id);
  return a.map(id => id === "kids" ? "modes" : id).filter(id => all.some(x => x.id === id)).concat(all.map(x => x.id).filter(id => !known.includes(id) && !a.includes(id)));
}
// personas — «let» из core.js, на window её нет: раньше здесь всегда выходила «Лира», даже у Патрика (отчёт 256).
const hmWho = (id) => {
  const all = (typeof personas !== "undefined" && Array.isArray(personas)) ? personas : [];
  const p = all.find(x => x.id === id) || (!id && all.find(x => x.id === (typeof active !== "undefined" ? active : ""))) || null;
  return (p && p.name) || (id ? id.charAt(0).toUpperCase() + id.slice(1) : "Ассистент");
};
function hmGreet() {
  const h = new Date().getHours(), name = String(((S && S.user_name) || "")).trim().split(/\s+/)[0];
  const w = t(h < 5 ? "home.greet.night" : h < 12 ? "home.greet.morning" : h < 18 ? "home.greet.day" : "home.greet.evening");
  return name ? `${w}, ${name}` : w;
}
function hmDate() { const d = new Date(); const s = d.toLocaleDateString(dwLocale(), { weekday: "long", day: "numeric", month: "long" }); return s[0].toUpperCase() + s.slice(1); }
async function loadHome() {
  hmRender();
  if (window.snLoad) snLoad();                          // «Слепок знаний» справа от приветствия (studio/snapshot.js)
  if (typeof moLoad === "function") moLoad();           // «Мой месяц с Лирой» (studio/month.js): первые 7 дней месяца — о прошлом
  if (typeof mnLoad === "function") mnLoad();           // «Утро с Лирой» (studio/morning.js): погода и почта — не ждём их
  hmMailLoad();                                         // «Почта»: последние письма — не ждём их
  const now = new Date(), get = (c, a) => core.call(c, a).catch(() => null);
  // скрытое в «Что показывать» (show.js) не грузится и не напоминает о себе карточкой «Сегодня» (03.11)
  const off = (...ps) => typeof shHiddenBy === "function" && ps.every(p => shHiddenBy(p)), skip = Promise.resolve(null);
  // уроки — с сайта, не ждём их (сеть бывает медленной): пришли — карточка «Новый видеоурок» дорисуется
  // «Радар» (12.11): бриф дня и самый сильный сигнал — не ждём, пришёл — карточка дорисуется; раздел скрыт — не грузим
  if (!off("insight")) get("insight_pulse").then(p => { HM.rd = p && p.stats ? p : null; if (HM.data) hmRender(); });
  if (!(HM.ac && Date.now() - HM.ac.at < 6 * 3600e3)) get("academy_list").then(ac => { if (ac && Array.isArray(ac.items)) { HM.ac = { at: Date.now(), d: ac }; if (HM.data) hmRender(); } });
  const [cal, cl, tk, dn, ch, pad, py, pl, cs] = await Promise.all([off("calendar", "reminders") ? skip : get("calendar_month", { year: now.getFullYear(), month: now.getMonth() + 1 }),
    off("close") ? skip : get("close_state"), off("tasks") ? skip : get("tasks_list"), get("done"), get("chat_list", { limit: 6 }), get("pad_tabs"),
    off("pay") ? skip : get("pay_overview"), get("plugins"), off("course") ? skip : get("course_get")]);
  const wt = off("watch") ? null : await get("watch_get");             // «Дозор»: сколько идёт — числом на значке
  HM.all = (pl && pl.plugins) || [];
  HM.plg = HM.all.filter(p => p.installed);
  let padText = null;
  if (pad && pad.active) { const r = await get("pad_read", { name: pad.active }); padText = r ? { name: pad.active, text: r.text || "" } : null; }
  HM.data = { cal, cl, tk: Array.isArray(tk) ? tk : [], dn: dn && typeof dn === "object" ? dn : null, ch, pad: padText,
              py: py && Array.isArray(py.bills) ? py : null, cs: cs && cs.days ? cs : null, wt: wt && Array.isArray(wt.items) ? wt : null };   // старое ядро или заглушка — не массив
  hmRender();
}
function hmToday() {
  const { cal, cl, dn } = HM.data, tk = HM.data.tk || [], out = [], now = new Date(), key = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;   // местная дата, не UTC (после полуночи по Москве)
  const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const today = ((cal && cal.days && cal.days[key]) || []).filter(x => (x.type === "event" || x.type === "reminder") && !x.done && (x.time || "99") >= hm)
    .sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  if (today[0]) out.push({ cls: "next", lab: "Дальше сегодня", b: `${today[0].time ? today[0].time + " — " : ""}${today[0].title}`, s: today.length > 1 ? `и ещё ${today.length - 1} сегодня` : "больше на сегодня ничего", go: today[0].type === "event" ? "calendar" : "reminders" });
  else out.push({ cls: "next", lab: "Сегодня", b: "Дел больше нет", s: "Скажите: «напомни через час…» — и я напомню", go: "reminders" });
  const un = ((cl && cl.people) || []).filter(p => p.unread);
  if (un.length) { const p = un[0], l = p.last && !p.last.out ? (p.last.t || "📎 файл") : "новое сообщение";
    out.push({ cls: "msg", lab: "Близкие", b: `💌 ${p.name}`, s: `«${String(l).slice(0, 60)}»${un.length > 1 ? ` · и ещё от ${un.length - 1}` : ""}`, go: "close" }); }
  const pyb = ((HM.data.py && HM.data.py.bills) || []).filter(b => !b.archived && ["overdue", "soon", "unpaid"].includes(b.now && b.now.s))
    .sort((a, b) => (a.now.s === "overdue" ? 0 : 1) - (b.now.s === "overdue" ? 0 : 1));
  if (pyb.length) { const b = pyb[0], late = b.now.s !== "soon";
    out.push({ cls: late ? "pay late" : "pay", lab: late ? "Не оплачено" : "Скоро срок оплаты", b: `${b.icon || "🧾"} ${b.name}`, s: (late ? "срок был " : "до ") + new Date(b.now.due + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) + (pyb.length > 1 ? ` · и ещё ${pyb.length - 1}` : ""), go: "pay" }); }
  const rd = hmRadar(); if (rd) out.push(rd);
  const cs = HM.data.cs, L = cs && cs.lesson;          // курс «Неделя с Лирой»: урок дня ещё не пройден
  if (L && L.open && cs.offer !== false && !L.steps.every(s => s.done))
    out.push({ cls: "course", lab: `Урок дня · ${L.day} из ${cs.total}`, b: `🎓 ${L.title}`, s: `5 минут: ${(L.steps.find(s => !s.done) || L.steps[0]).say}`, go: "course" });
  const nl = hmLesson();                                // новый видеоурок — одной карточкой, пока не посмотрели (3 дня, потом молча)
  if (nl) out.push({ cls: "lesson", lab: `Новый видеоурок · ${nl.sec ? nl.sec + " с" : "минута"}`, b: `🎬 ${nl.title}`, s: nl.about || "мультфильм о том, как это работает", go: "lesson:" + nl.id });
  const w = tk.find(t => t.status === "waiting");
  if (w) out.push({ cls: "task", lab: "Задача ждёт ответа", b: `⏳ ${w.title}`, s: w.question || "откройте и ответьте", go: "tasks" });
  if (dn) out.push({ cls: "done", lab: "Сделано сегодня", b: `${dn.today || 0} ${(dn.today || 0) % 10 === 1 && (dn.today || 0) % 100 !== 11 ? "дело" : [2, 3, 4].includes((dn.today || 0) % 10) && ![12, 13, 14].includes((dn.today || 0) % 100) ? "дела" : "дел"}`,
    s: dn.streak >= 2 ? `🔥 серия ${dn.streak} дн. подряд` : "отметьте сделанное — голосом или в «Делах»", go: "reminders" });
  return out.slice(0, 4);
}
/* «Радар» на «Главной» (владелец 12.11: «на главной показывало находки — лучшее из найденного и проанализированного»):
   свежий бриф дня (не старше полутора суток) — его заголовок и самый сильный сигнал за сутки; брифа нет — сам сигнал,
   если он заметный (от 7). Источников нет или тихо — карточки нет: «Главная» не реклама раздела. */
function hmRadar() {
  const rd = HM.rd, tt = (k, v) => window.t ? window.t("insight.home." + k, v) : k;
  if (!rd || !rd.stats || !rd.stats.sources) return null;
  const top = (rd.field || []).filter(p => p.x >= 6).sort((a, b) => b.s - a.s)[0];
  const sig = top && top.s >= 6 ? `⚡ ${Number(top.s).toLocaleString(dwLocale(), { maximumFractionDigits: 1 })} · ${top.title}` : "";
  const b = rd.brief && rd.brief.headline && (rd.brief.at || 0) * 1000 > Date.now() - 36 * 3600e3 ? rd.brief : null;
  if (b) return { cls: "radar", lab: tt("brief"), b: b.headline, s: sig || (b.points || [])[0] || tt("open"), go: "insight" };
  if (top && top.s >= 7) return { cls: "radar", lab: tt("signal"), b: top.title, s: tt("day", { n: rd.stats.day || 1 }), go: "insight" };
  return null;
}
function hmBadge(id) {
  const { cl } = HM.data, tk = HM.data.tk || [];
  if (id === "close") return ((cl && cl.people) || []).reduce((a, p) => a + (p.unread || 0), 0);
  if (id === "tasks") return tk.filter(t => t.status === "waiting").length;
  if (id === "watch") return ((HM.data.wt && HM.data.wt.items) || []).filter(x => x.status === "active").length;
  if (id === "pay") return ((HM.data.py && HM.data.py.bills) || []).filter(b => !b.archived && ["overdue", "soon", "unpaid"].includes(b.now && b.now.s)).length;
  return 0;
}
/* Начало листа блокнота на «Главной» — как в самом блокноте, а не сырой Markdown (25.10, владелец: «там сырой маркдаун
   с решётками»): заголовок, жирное, курсив, код, пункты, задачи, цитаты; схемы и картинки — короткой пометкой. */
function hmPadLines(text, max = 5) {
  const inl = (s) => hmEsc(s.length > 110 ? s.slice(0, 108).replace(/\s+\S*$/, "") + "…" : s)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*\*([^*]+)$/, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<em>$2</em>").replace(/==([^=]+)==/g, "<mark>$1</mark>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const out = []; let fence = null;
  for (const raw of String(text || "").split("\n")) {
    if (out.length >= max) break;
    const l = raw.trim(); let m;
    if (/^```/.test(l)) { if (fence === null) { fence = l.slice(3).trim(); if (fence === "mermaid") out.push('<p class="pv-x">◇ схема</p>'); } else fence = null; continue; }
    if (fence !== null || !l || /^(-{3,}|\*{3,})$/.test(l) || /^\|?\s*:?-{2,}/.test(l)) continue;
    if (/^!\[[^\]]*\]\([^)]*\)$/.test(l)) { out.push('<p class="pv-x">▣ картинка</p>'); continue; }
    if ((m = l.match(/^(#{1,6})\s+(.*)$/))) out.push(`<p class="pv-h${m[1].length > 1 ? " h2" : ""}">${inl(m[2])}</p>`);
    else if ((m = l.match(/^[-*+]\s+\[([ xX])\]\s*(.*)$/))) out.push(`<p class="pv-li pv-t${m[1] !== " " ? " done" : ""}"><i></i>${inl(m[2])}</p>`);
    else if ((m = l.match(/^(?:[-*+•]|\d+[.)])\s+(.*)$/))) out.push(`<p class="pv-li"><i></i>${inl(m[1])}</p>`);
    else if ((m = l.match(/^>\s?(.*)$/))) { if (m[1].trim()) out.push(`<p class="pv-q">${inl(m[1])}</p>`); }
    else if (/^\|.*\|$/.test(l)) out.push(`<p class="pv-x">${inl(l.replace(/^\||\|$/g, "").split("|").map(c => c.trim()).filter(Boolean).join(" · "))}</p>`);
    else out.push(`<p>${inl(l)}</p>`);
  }
  return out;
}
function hmRender() {
  const box = $("#hm-body"); if (!box) return;
  const all = hmAll(), shown = hmApps().filter(hmFeat), list = HM.edit ? shown.map(id => all.find(x => x.id === id)).concat(all.filter(x => !shown.includes(x.id) && hmFeat(x.id))) : shown.map(id => all.find(x => x.id === id));
  $("#hm-greet").textContent = hmGreet(); $("#hm-date").textContent = hmDate();
  const t = hmToday();
  // «Совет ИИ» (0.67, владелец: «и это же — в красивую кнопку на главной»): лица персонажей за столом
  if ($("#hmc-faces")) {
    const ps = (typeof personas !== "undefined" && Array.isArray(personas) ? personas : []).filter(p => !p.kids).slice(0, 4);
    $("#hmc-faces").innerHTML = ps.map((p, i) => `<i style="--c:${hmEsc(p.color || "#8b7cff")};z-index:${9 - i}${p.avatar_url ? `;background-image:url('${String(p.avatar_url).replace(/'/g, "%27")}')` : ""}" class="${p.avatar_url ? "pic" : ""}">${p.avatar_url ? "" : hmEsc((p.name || "?")[0])}</i>`).join("");
    $("#hm-council").hidden = !shown.includes("council");
  }
  $("#hm-today").innerHTML = t.map(c => `<button class="hm-card ${c.cls}" data-go="${c.go}"${String(c.b).length > 70 ? ` title="${hmEsc(c.b)}"` : ""}><small>${hmEsc(c.lab)}</small><b>${hmEsc(c.b)}</b><span>${hmEsc(c.s)}</span></button>`).join("");
  // Приложения и плагины — раздельно (11.11, люди: «путаются, что есть что»): встроенное — «Приложения», поставленные
  // дополнения — «Плагины» со своей кнопкой «Все плагины». Порядок и «показать/скрыть» — общие (hmApps), как прежде.
  const tile = a => { const on = shown.includes(a.id), n = hmBadge(a.id);
    const md = a.id === "modes" && typeof MD !== "undefined" && MD.st && MD.st.mode && MD.st.mode !== "me" ? MD.st.mode : "";
    if (md) a = Object.assign({}, a, { sub: "сейчас: " + MD_NAME[md] });
    return `<div class="hm-app${on ? "" : " off"}" data-app="${hmEsc(a.id)}" ${HM.edit ? 'draggable="true"' : ""}><button class="hm-ic${a.plg ? " hm-isplg" : ""}" data-open="${hmEsc(a.id)}" title="${hmEsc(a.name)} — ${hmEsc(a.sub)}"${a.plg ? ` style="--pc:${hmEsc(a.plg.color || "#7c8cff")}"` : ""}>${a.plg ? `<i class="hm-plg" aria-hidden="true">${hmEsc(a.plg.icon || "🧩")}</i>` : HM_SVG(a.g, a.d)}${n && !HM.edit ? `<em>${n}</em>` : ""}</button>`
      + `<b>${hmEsc(a.name)}</b><small>${hmEsc(a.sub)}</small>${HM.edit ? `<label class="tg hm-tg" title="${on ? "Скрыть с главной и из меню (сама функция продолжит работать)" : "Показать на главной и в меню"}"><input type="checkbox" data-tg="${hmEsc(a.id)}" ${on ? "checked" : ""}><i></i></label>` : ""}</div>`; };
  const items = list.filter(Boolean), apps = items.filter(a => !a.plg), plgs = items.filter(a => a.plg);
  $$("#hm-apps, #hm-plgs").forEach(g => g.classList.toggle("edit", HM.edit));
  $("#hm-apps").innerHTML = apps.map(tile).join("");
  const offPlg = typeof S !== "undefined" && S && S.ui && Array.isArray(S.ui.nav_hidden) && S.ui.nav_hidden.includes("plugins");
  $("#hm-plgs").innerHTML = plgs.map(tile).join("") + (HM.edit ? "" : `<div class="hm-app hm-add"><button class="hm-ic" data-plgall="1" title="Каталог плагинов — поставить одним нажатием" aria-label="Все плагины"><i class="hm-plg" aria-hidden="true">＋</i></button><b>Ещё плагины</b><small>каталог Dewiar</small></div>`);
  $("#hm-plg-h").hidden = $("#hm-plgs").hidden = !!offPlg;
  $("#hm-edit").textContent = HM.edit ? "Готово" : "Настроить главную";
  $("#hm-edit-hint").hidden = !HM.edit;
  const ch = (HM.data.ch && HM.data.ch.items) || [], lastU = [...ch].reverse().find(x => x.role === "user"), lastA = [...ch].reverse().find(x => x.role === "assistant");
  $("#hm-chat").innerHTML = ch.length ? `<small>Последний разговор · ${new Date((lastA || lastU).ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</small>`
    + (lastU ? `<p class="u">Вы: ${hmEsc(lastU.text.slice(0, 120))}</p>` : "") + (lastA ? `<p>${hmEsc(hmWho(lastA.who) + ": " + lastA.text.slice(0, 220))}${lastA.text.length > 220 ? "…" : ""}</p>` : "")
    + `<button class="hm-more" data-go="chat">Продолжить в чате</button>` : `<small>Чат</small><p>Здесь появится последний разговор. Можно писать и голосом, и текстом.</p><button class="hm-more" data-go="chat">Открыть чат</button>`;
  const pd = HM.data.pad, lines = pd ? hmPadLines(pd.text) : [];
  $("#hm-pad").innerHTML = `<small>Блокнот${pd ? " · «" + hmEsc(pd.name) + "»" : ""}</small>` + (lines.length ? `<div class="hm-pv">${lines.join("")}</div>` : `<p>Блокнот у виджета — для мыслей на лету. Пишется само.</p>`)
    + `<button class="hm-more" data-pad="1">Открыть блокнот у виджета</button>`;
  hmMail();
  hmTry();
  $("#hm-set").innerHTML = HM_SET.map(([p, n]) => `<button class="hm-pill" data-go="${p}">${hmEsc(n)}</button>`).join("");
  hmWire();
}
/* «Почта» на главной (30.10, владелец: «добавил почту — и не могу понять, как увидеть последние письма… может, показывать
   здесь последние письма красиво, если почта подключена»). Пять последних писем: от кого, тема, начало текста, когда;
   новые — жирно с точкой. Нажали — письмо целиком (mail_read), «Ответить с Лирой» — в «Чат». Почты нет — карточки нет
   (позвать подключить — дело «Утра»). Письма — раз в 5 минут, не мешая остальной «Главной». */
const HMM_TTL = 5 * 60e3;
async function hmMailLoad(force) {
  if (HM.mailBusy) return;
  if (!force && HM.mail && Date.now() - HM.mail.at < HMM_TTL) { hmMail(); return; }
  HM.mailBusy = true; if (force) hmMail();
  let r;
  try { r = await core.call("mail_inbox", { limit: 14 }); }   // с запасом: убранные с главной и заглушённые не в счёт
  catch (e) { r = /Детский режим/.test(e.message) ? { on: false, items: [] } : { on: true, items: (HM.mail && HM.mail.items) || [], err: e.message }; }
  HM.mailBusy = false;
  HM.mail = Object.assign({ at: Date.now() }, r || { on: false, items: [] });
  hmMail();
}
const hmmWho = (f) => { const s = String(f || ""), m = s.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>/); return (m ? (m[1].trim() || m[2]) : s.trim()) || "без имени"; };
const hmmAddr = (f) => { const m = String(f || "").match(/<([^>]+)>/); return m ? m[1] : String(f || "").trim(); };
function hmmWhen(d) {
  const t = new Date(d); if (isNaN(t)) return "";
  const now = new Date(), day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime(), diff = Math.round((day(now) - day(t)) / 864e5);
  if (diff === 0) return t.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  if (diff === 1) return "вчера";
  return t.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }).replace(".", "");
}
/* Владелец 11.11 (Ubuntu): «почта занимает много места и всё время мозолит глаз — сворачивать красиво, с возможностью
   развернуть, или убирать неинтересные письма». Свернуть — шапкой (одна строка: сколько новых и последнее письмо), выбор
   запоминается. У письма — «Убрать с главной» (×): письмо уходит только отсюда, в ящике остаётся; тут же можно не показывать
   этого отправителя вовсе («Не показывать …»), вернуть — «Показать скрытые». Всё — в этом окне (localStorage). */
/* Свёрнута ли почта, убранные письма и отправители — в настройках программы (ui.mail_fold, mail_hide, mail_mute), как
   свёрнутые группы меню. Владелец 11.11 (Ubuntu): «сворачивание писем — ничего не происходит», «удаление — крестик ни к
   чему не приводит»: в окне студии WebKitGTK хранилище страницы (localStorage) не работает, запись молча пропадала.
   Прежние значения из хранилища страницы (Windows) читаются, пока в настройках ничего нет. */
const HMM_K = { fold: "mail_fold", hide: "mail_hide", mute: "mail_mute" };
const hmmMem = {};
function hmmGet(k, d) {
  const u = (typeof S !== "undefined" && S && S.ui) || {};
  if (u[k] != null) return u[k];
  if (k in hmmMem) return hmmMem[k];
  try { const v = JSON.parse(localStorage.getItem("dw_" + k)); return v == null ? d : v; } catch (e) { return d; }
}
function hmmSet(k, v) {
  hmmMem[k] = v;
  if (typeof S !== "undefined" && S) S.ui = Object.assign({}, S.ui, { [k]: v });
  if (typeof core !== "undefined") core.call("settings_save", { patch: { ui: { [k]: v } } }).catch(() => { });
  try { localStorage.setItem("dw_" + k, JSON.stringify(v)); } catch (e) { }
}
const hmmKey = (x) => `${x.box || ""}|${x.uid || ""}|${x.date || ""}`;
const hmmFrom = (x) => hmmAddr(x.from).toLowerCase();
function hmmShown(items) {
  const hide = new Set(hmmGet(HMM_K.hide, [])), mute = new Set(hmmGet(HMM_K.mute, []));
  return (items || []).filter(x => !hide.has(hmmKey(x)) && !mute.has(hmmFrom(x)));
}
function hmmHide(x) {
  const hide = hmmGet(HMM_K.hide, []); hide.push(hmmKey(x)); hmmSet(HMM_K.hide, hide.slice(-300));
  HM.mailUndo = x; hmMail();
}
function hmMail() {
  const box = $("#hm-mail"); if (!box) return;
  const m = HM.mail;
  if (!m || !m.on) { box.hidden = true; box.innerHTML = ""; return; }
  box.hidden = false;
  const all = m.items || [], it = hmmShown(all).slice(0, 5), un = it.filter(x => x.unread).length;
  const fold = !!hmmGet(HMM_K.fold, false), hidden = all.length - hmmShown(all).length;
  box.classList.toggle("fold", fold);
  const rows = it.map((x, i) => { const who = hmmWho(x.from), sub = x.subject || "(без темы)", sn = String(x.snippet || "").trim();
    return `<li><button type="button" class="hmm-row${x.unread ? " new" : ""}" data-i="${i}" title="${hmEsc(hmmAddr(x.from))}">
      <i class="hmm-av" style="--c:${typeof vlCol === "function" ? vlCol(who) : "#5b8def"}" aria-hidden="true">${hmEsc((who.replace(/^[^\p{L}\d]+/u, "")[0] || "?").toUpperCase())}</i>
      <span class="hmm-t"><span class="hmm-l1"><b>${hmEsc(who)}</b>${x.files && x.files.length ? '<em class="hmm-clip" title="С вложением">📎</em>' : ""}<time>${hmEsc(hmmWhen(x.date))}</time></span>
        <span class="hmm-l2"><span class="hmm-sub">${hmEsc(sub)}</span>${sn ? `<span class="hmm-sn"> — ${hmEsc(sn.slice(0, 140))}</span>` : ""}</span></span></button>
      <button type="button" class="hmm-rx" data-x="${i}" title="Убрать с главной (в ящике письмо останется)" aria-label="Убрать письмо от ${hmEsc(who)} с главной"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></li>`; }).join("");
  const last = it[0], u = HM.mailUndo, uw = u ? hmmWho(u.from) : "";
  const peek = last ? `<span class="hmm-peek"><b>${hmEsc(hmmWho(last.from))}</b> — ${hmEsc(last.subject || "(без темы)")}</span>` : "";
  box.innerHTML = `<div class="hmm-head"><h2 class="hmm-h2"><button type="button" class="hmm-fold" id="hmm-fold" aria-expanded="${!fold}" aria-controls="hmm-wrap" title="${fold ? "Показать письма" : "Свернуть почту"}">
        <span class="hmm-h">Почта</span>${un ? `<span class="hmm-n">${un} ${un % 10 === 1 && un % 100 !== 11 ? "новое" : "новых"}</span>` : ""}${fold ? peek : ""}
        <svg class="hmm-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button></h2>${fold ? "" : '<span class="hmm-sp"></span>'}
      <button type="button" class="hmm-re${HM.mailBusy ? " busy" : ""}" id="hmm-re" title="Проверить почту" aria-label="Проверить почту"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5A8 8 0 1 0 17.7 17"/><path d="M20.5 5.5v6h-6"/></svg></button></div>`
    + `<div class="hmm-wrap" id="hmm-wrap"${fold ? " hidden" : ""}>`
    + (u ? `<p class="hmm-undo" role="status">Письмо убрано с главной. <button type="button" id="hmm-mute">Не показывать письма от ${hmEsc(uw)}</button><button type="button" id="hmm-back">Вернуть</button></p>` : "")
    + (m.err && !it.length ? `<p class="hmm-err">Почта не ответила: ${hmEsc(m.err)} <a href="#" id="hmm-fix">Проверить подключение</a></p>`
      : !it.length ? `<p class="hmm-empty">${HM.mailBusy ? "Смотрю почту…" : hidden ? "Новых писем для главной нет." : "Во входящих пусто."}</p>` : `<ul class="hmm-list">${rows}</ul>`)
    + `<p class="hmm-foot">Голосом: «что нового в почте?», «прочитай письмо от…», «ответь ему, что…»`
    + (hmmGet(HMM_K.hide, []).length || hmmGet(HMM_K.mute, []).length ? ` · <button type="button" class="hmm-all" id="hmm-all">Показать скрытые</button>` : "") + `</p></div>`;
  $("#hmm-re").onclick = () => hmMailLoad(true);
  $("#hmm-fold").onclick = () => { hmmSet(HMM_K.fold, !fold); HM.mailUndo = null; hmMail(); };
  $$("#hm-mail .hmm-rx").forEach(b => b.onclick = (e) => { e.stopPropagation(); hmmHide(it[+b.dataset.x]); });
  if ($("#hmm-back")) $("#hmm-back").onclick = () => { hmmSet(HMM_K.hide, hmmGet(HMM_K.hide, []).filter(k => k !== hmmKey(u))); HM.mailUndo = null; hmMail(); };
  if ($("#hmm-mute")) $("#hmm-mute").onclick = () => { const mu = hmmGet(HMM_K.mute, []); mu.push(hmmFrom(u)); hmmSet(HMM_K.mute, [...new Set(mu)].slice(-100)); HM.mailUndo = null; hmMail(); };
  if ($("#hmm-all")) $("#hmm-all").onclick = () => { hmmSet(HMM_K.hide, []); hmmSet(HMM_K.mute, []); HM.mailUndo = null; hmMail(); };
  if ($("#hmm-fix")) $("#hmm-fix").onclick = (e) => { e.preventDefault(); hmGo("connect"); setTimeout(() => { const b = $("#mail-box"); if (b) b.scrollIntoView({ block: "center", behavior: "smooth" }); }, 250); };
  $$("#hm-mail .hmm-row").forEach(b => b.onclick = () => hmmOpen(it[+b.dataset.i]));
}
/* Письмо целиком (№562, 05.11, Serge: «удобно: просмотр письма в HTML-виде; минимальное управление: Удалить, В спам,
   Переслать»). «Как в письме» — HTML письма в рамке <iframe sandbox="" srcdoc>: без скриптов, без своего источника, CSP
   default-src 'none' (core/mailhtml.py уже вычистил скрипты, формы и on…). Картинки из интернета — только по «Показать
   картинки» (до того отправитель не узнает, что письмо открыли). Ссылки внутри рамки не нажимаются — переход внутри неё
   ушёл бы на чужой сайт мимо всех запретов, — они списком под письмом, с настоящим адресом, и открываются в браузере.
   Есть у письма своя текстовая часть — по умолчанию «Текстом»; выбор человека запоминается. */
const HMM = { x: null, r: null, view: "", pics: false, busy: false };
function hmmView() { return String(hmmGet("mail_view", "") || ""); }
function hmmDoc(r, pics) {
  const csp = `default-src 'none'; img-src data:${pics ? " https:" : ""}; style-src 'unsafe-inline'; font-src data:`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${csp}">`
    + `<meta name="referrer" content="no-referrer"><style>html{background:#fff}body{margin:0;padding:18px 20px;color:#1d2330;background:#fff;`
    + `font:14.5px/1.55 -apple-system,"Segoe UI","Manrope",Ubuntu,"Noto Sans",sans-serif;overflow-wrap:anywhere}img{max-width:100%;height:auto}`
    + `table{max-width:100%}:where(a[data-href]){color:#1a5fd0;text-decoration:underline}a[data-href]{cursor:default}pre{white-space:pre-wrap}</style></head><body>`
    + (r.html || "") + `</body></html>`;
}
function hmmShow() {
  const r = HMM.r, body = $("#hmm-body"); if (!r) return;
  const html = !!r.html && HMM.view === "html", txt = String(r.text || "").trim();
  $$("#hmm-bar .hmm-seg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === (html ? "html" : "text"))));
  $("#hmm-bar").hidden = !r.html;
  $("#hmm-pics").hidden = !html || HMM.pics || !(r.html_remote > 0);
  if (!$("#hmm-pics").hidden) $("#hmm-pics span").textContent = `Показать картинки · ${r.html_remote}`;
  const head = `<p class="hmm-to">${hmEsc(hmmAddr(r.from || HMM.x.from))}${r.to ? ` → ${hmEsc(r.to)}` : ""}</p>`;
  const files = (r.files || []).length ? `<p class="hmm-files">📎 ${r.files.map(hmEsc).join(" · ")}</p>` : "";
  if (!html) { body.innerHTML = head + `<div class="hmm-text">${txt ? hmEsc(txt) : "<i>В письме нет текста.</i>"}</div>` + files; return; }
  const links = (r.html_links || []).filter(l => /^(https?:|mailto:)/i.test(l.url));
  body.innerHTML = head + `<div class="hmm-paper"><iframe class="hmm-frame" sandbox="" referrerpolicy="no-referrer" title="Письмо: ${hmEsc(r.subject || "")}"></iframe></div>` + files
    + (links.length ? `<details class="hmm-links"><summary>Ссылки в письме · ${links.length}</summary><ul>${links.map((l, i) => {
        let host = l.url, rest = ""; try { const u = new URL(l.url); host = u.protocol === "mailto:" ? u.pathname : u.host; rest = u.protocol === "mailto:" ? "" : (u.pathname + u.search).replace(/^\/$/, ""); } catch (e) { }
        return `<li><button type="button" data-l="${i}" title="${hmEsc(l.url)}"><span class="hmm-lt">${hmEsc(l.text || host)}</span><span class="hmm-lu"><b>${hmEsc(host)}</b>${hmEsc(rest.slice(0, 80))}</span></button></li>`; }).join("")}</ul>`
      + `<small>Ссылки открываются в браузере. Смотрите на адрес: письмо может выдавать себя за банк или магазин.</small></details>` : "");
  $(".hmm-frame", body).srcdoc = hmmDoc(r, HMM.pics);
  $$(".hmm-links button", body).forEach(b => b.onclick = () => { const l = links[+b.dataset.l]; if (l) openExt(l.url); });
}
function hmmFwd(on) { $("#hmm-fwd").hidden = !on; $("#hmm-fwdb").setAttribute("aria-expanded", String(!!on)); }
function hmmStatus(t, bad) { const el = $("#hmm-st"); el.hidden = !t; el.textContent = t || ""; el.classList.toggle("bad", !!bad); }
function hmmBusy(on) { HMM.busy = on; ["#hmm-del", "#hmm-spam", "#hmm-fwdb", "#hmm-fgo"].forEach(id => { const b = $(id); if (b) b.disabled = on; }); }
function hmmGone(x) {                                    // письмо убрали — и из списка на «Главной»
  if (HM.mail && HM.mail.items) HM.mail.items = HM.mail.items.filter(it => it !== x && it.uid !== x.uid);
  hmMail(); setTimeout(() => hmMailLoad(true), 1500);
}
async function hmmAct(action) {
  const x = HMM.x, r = HMM.r || {}; if (!x || HMM.busy) return;
  const what = `«${r.subject || x.subject || "без темы"}» от ${hmmWho(r.from || x.from)}`;
  if (action === "trash" && !await ask(`Удалить письмо ${what}?\nОно уйдёт в «Корзину» почты — оттуда его можно вернуть.`, { ok: "Удалить" })) return;
  if (action === "junk" && !await ask(`Отправить письмо ${what} в «Спам»?\nПочта будет узнавать такие письма.`, { ok: "В спам", danger: true })) return;
  let to = "", note = "";
  if (action === "forward") {
    to = $("#hmm-fto").value.trim(); note = $("#hmm-fnote").value.trim();
    const bad = to.split(/[,;\s]+/).filter(Boolean).find(a => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(a));
    if (!to || bad) { hmmStatus(to ? `Проверьте адрес: ${bad}` : "Впишите, кому переслать", true); $("#hmm-fto").focus(); return; }
    if (!await ask(`Переслать письмо ${what} → ${to}?`, { ok: "Переслать" })) return;
  }
  hmmBusy(true); hmmStatus(action === "forward" ? "Пересылаю…" : action === "junk" ? "Убираю в «Спам»…" : "Удаляю…");
  try {
    const res = await core.call("mail_act", { uid: x.uid, action, to, note });
    if (action === "forward") {
      hmmStatus(`Переслала: ${(res.to || [to]).join(", ")}`); hmmFwd(false); $("#hmm-fnote").value = "";
    } else {
      $("#hmm-dlg").close(); hmmGone(x);
      toast(action === "junk" ? `Письмо в «${res.folder || "Спам"}»` : res.permanent ? "Письмо удалено — корзины в этой почте нет" : `Письмо в «${res.folder || "Корзине"}»`, 3200);
    }
  } catch (e) { hmmStatus("Не вышло: " + e.message, true); }
  hmmBusy(false);
}
async function hmmOpen(x) {
  if (!x) return;
  const d = $("#hmm-dlg"), body = $("#hmm-body");
  HMM.x = x; HMM.r = null; HMM.pics = false; HMM.busy = false; hmmBusy(false); hmmStatus("");
  hmmFwd(false); $("#hmm-bar").hidden = true;
  $("#hmm-dfrom").textContent = `${hmmWho(x.from)} · ${hmmWhen(x.date)}`; $("#hmm-dt").textContent = x.subject || "(без темы)";
  body.innerHTML = `<p class="hmm-load">Открываю письмо…</p>`;
  if (!d.open) d.showModal();
  $("#hmm-reply").onclick = () => { d.close(); const t = `Помоги ответить на письмо от ${hmmWho(x.from)} (${hmmAddr(x.from)}) с темой «${x.subject || "без темы"}»`;
    if (typeof qaAsk === "function") qaAsk(t); else core.call("say", { text: t }).catch(() => {}); };
  try {
    const r = await core.call("mail_read", { uid: x.uid, html: true });
    if (HMM.x !== x) return;                             // пока грузилось, открыли другое
    // своего текста у письма нет — «текстом» лишь выжимка из HTML: сразу «как в письме»; есть — как выбрал человек (сначала текстом)
    HMM.r = r; HMM.view = r.html && (!r.plain || hmmView() === "html") ? "html" : "text";
    hmmShow();
    if (x.unread) { x.unread = false; hmMail(); }        // открыли — прочитано и здесь, и на самой почте (mail_read отметил)
  } catch (e) { body.innerHTML = `<p class="hmm-err">Не открылось: ${hmEsc(e.message)}</p>`; }
}
if ($("#hmm-dlg")) {
  $("#hmm-x").onclick = () => $("#hmm-dlg").close();
  $("#hmm-dlg").addEventListener("click", (e) => { if (e.target === $("#hmm-dlg")) $("#hmm-dlg").close(); });
  $$("#hmm-bar .hmm-seg button").forEach(b => b.onclick = () => { HMM.view = b.dataset.v; hmmSet("mail_view", HMM.view); hmmShow(); });
  $("#hmm-pics").onclick = () => { HMM.pics = true; hmmShow(); };
  $("#hmm-del").onclick = () => hmmAct("trash");
  $("#hmm-spam").onclick = () => hmmAct("junk");
  $("#hmm-fwdb").onclick = () => { const f = $("#hmm-fwd"); hmmFwd(f.hidden); hmmStatus(""); if (!f.hidden) { $("#hmm-fto").focus(); f.scrollIntoView({ block: "nearest" }); } };
  $("#hmm-fcancel").onclick = () => { hmmFwd(false); hmmStatus(""); };
  $("#hmm-fwd").onsubmit = (e) => { e.preventDefault(); hmmAct("forward"); };
}
function hmGo(p) {
  if (p.includes("#")) {                               // «раздел#элемент» — открыть и показать место (look#show-box)
    const [q, id] = p.split("#"); hmGo(q);
    setTimeout(() => { const el = document.getElementById(id); if (el) el.scrollIntoView({ block: "start", behavior: "smooth" }); }, 200);
    return;
  }
  if (p.startsWith("lesson:")) {                       // карточка «Новый видеоурок» — сразу смотреть
    const l = ((HM.ac && HM.ac.d.items) || []).find(x => x.id === p.slice(7)); hmGo("lessons");
    if (l && typeof lsPlay === "function") setTimeout(() => lsPlay(l), 150);
    return;
  }
  const b = $(`nav button[data-p="${p}"]`); if (b) b.click();
}
/* «Чтобы люди узнали про уроки — ненавязчиво» (29.10, владелец): на «Главной» среди карточек «Сегодня» — самый ранний
   урок, который ещё не смотрели. Посмотрели (lessons.js lsSeen) — следующий; карточка висит не дольше 3 дней, потом урок
   считается показанным и больше не напоминает. Отметки — S.ui.lessons_seen {id: время}. */
function hmLesson() {
  const items = ((HM.ac && HM.ac.d.items) || []).slice().sort((a, b) => a.n - b.n), ui = (S && S.ui) || {};
  const seen = ui.lessons_seen || {}, now = Date.now();
  const l = items.find(x => !seen[x.id] || (seen[x.id] < 0 && now + seen[x.id] < 3 * 864e5));
  if (!l) return null;
  if (!seen[l.id] && S) { const m = Object.assign({}, seen, { [l.id]: -now }); S.ui = Object.assign({}, ui, { lessons_seen: m }); save({ ui: { lessons_seen: m } }, true); }
  return l;
}
function hmOpen(id) {
  const a = window.pywebview && window.pywebview.api;
  if (id === "play") { if (a && a.play_open) a.play_open(""); else toast("Игры открываются у виджета: «Лира, давай поиграем»"); return; }
  if (id === "pad") { if (a && a.pad_toggle) a.pad_toggle("notes"); return; }
  if (id === "modes") { if (window.mdOpen) mdOpen(false); return; }          // «Режимы» — выбор «Для кого эта Лира?»
  if (id.startsWith("plg:") && window.plpOpen && ((HM.plg || []).some(p => p.id === id.slice(4) && p.installed !== false))) return plpOpen(id.slice(4));   // установлен — его страница
  if (id.startsWith("plg:")) { plgOpen = id.slice(4); hmGo("skills"); if (PLG.length) plgDrawer(plgOpen); return; }   // карточка плагина — в «Плагинах»
  hmGo(id);
}
function hmSave(list) {
  const known = hmAll().map(x => x.id);
  core.call("settings_save", { patch: { ui: { home_apps: list, home_known: known } } }).then(() => { S.ui = Object.assign({}, S.ui, { home_apps: list, home_known: known }); hmNav(); }).catch(e => toast(e.message));
  S.ui = Object.assign({}, S.ui, { home_apps: list, home_known: known }); hmNav();
}
/* «Попробуйте плагин» (31.10, владелец: «на главной показывать плагины, чтобы человек видел, мог включить и сразу
   посмотреть, как работает; в будущем — видео к каждому»). Один ещё не включённый плагин за раз, каждый день — другой
   (стрелка — следующий): значок, что умеет, фраза. «Включить» — сразу, без похода в «Плагины»; плагину нужны настройки
   (поле required: «Что искать» у «Тендеров») — открывается его панель. Включили — карточка говорит, что сказать, и
   «Спросить Лиру» задаёт эту фразу в чате: результат виден сразу. Ролик — свой (поле video плагина: урок Академии или
   адрес), иначе общий урок «Плагины». Скрыть — на две недели (S.ui.try_hide_until). */
const TRY_LESSON = "15-plugins";
function hmTryList() {
  return (HM.all || []).filter(p => !p.installed && p.builtin !== false).sort((a, b) => a.id < b.id ? -1 : 1);
}
function hmTry() {
  const box = $("#hm-try"); if (!box) return;
  const ui = (S && S.ui) || {}, list = hmTryList(), done = HM.tryDone && (HM.all || []).find(p => p.id === HM.tryDone);
  if (HM.edit || !hmFeat("skills") || (!done && (!list.length || (ui.try_hide_until || 0) > Date.now()))) { box.hidden = true; return; }
  if (HM.tryI == null) HM.tryI = Math.floor(Date.now() / 864e5);          // по дню: сегодня — один, завтра — другой
  const p = done || list[((HM.tryI % list.length) + list.length) % list.length];
  const les = ((HM.ac && HM.ac.d.items) || []).find(l => l.id === (p.video || TRY_LESSON));
  const vid = p.video ? (les || /^https:/.test(p.video) ? "Смотреть ролик" : "") : (les ? "Как работают плагины" : "");
  const say = p.try || (p.phrases || [])[0] || "";
  box.style.setProperty("--pc", p.color || "#7c8cff");
  box.hidden = false;
  box.classList.toggle("done", !!done);
  box.innerHTML = `<i class="ht-ic" aria-hidden="true">${hmEsc(p.icon || "🧩")}</i>
    <div class="ht-t"><small>${done ? "Плагин включён" : "Попробуйте плагин"} · ${hmEsc(p.category || "")}</small>
      <b>${hmEsc(p.name)}</b><span>${hmEsc(done ? "Скажите Лире — или нажмите, и она ответит в чате:" : p.tagline || "")}</span>
      ${say ? `<q>${hmEsc(say)}</q>` : ""}
      <div class="ht-acts">${done
        ? `<button class="btn primary small" type="button" id="ht-ask">Спросить Лиру</button><button class="btn ghost small" type="button" id="ht-more">Настройки плагина</button>`
        : `<button class="btn primary small" type="button" id="ht-on">${(p.settings || []).some(x => x.required && !String((p.values || {})[x.key] ?? "").trim()) ? "Настроить и включить" : "Включить"}</button>`
          + (vid ? `<button class="btn ghost small" type="button" id="ht-vid">▶ ${vid}</button>` : "")
          + `<button class="btn ghost small" type="button" id="ht-more">Подробнее</button>`}</div></div>
    <div class="ht-nav">${!done && list.length > 1 ? `<button type="button" class="ht-b" id="ht-next" aria-label="Другой плагин" title="Другой плагин">›</button>` : ""}
      <button type="button" class="ht-b" id="ht-x" aria-label="Скрыть" title="${done ? "Закрыть" : "Скрыть на две недели"}">×</button></div>`;
  $("#ht-more").onclick = () => hmOpen("plg:" + p.id);
  if ($("#ht-next")) $("#ht-next").onclick = () => { HM.tryI++; hmTry(); };
  if ($("#ht-vid")) $("#ht-vid").onclick = () => {
    const l = les || { id: "plg-" + p.id, n: "", title: p.name, video: p.video, poster: "" };
    if (typeof lsPlay === "function") lsPlay(l); };
  if ($("#ht-ask")) $("#ht-ask").onclick = () => { HM.tryDone = ""; if (typeof qaAsk === "function") qaAsk(say); else core.call("say", { text: say }).catch(() => {}); hmTry(); };
  $("#ht-x").onclick = () => {
    if (done) { HM.tryDone = ""; hmTry(); return; }
    const until = Date.now() + 14 * 864e5;
    S.ui = Object.assign({}, S.ui, { try_hide_until: until });
    core.call("settings_save", { patch: { ui: { try_hide_until: until } } }).catch(() => {});
    hmTry(); toast("Скрыла на две недели. Все плагины — в разделе «Плагины»");
  };
  if ($("#ht-on")) $("#ht-on").onclick = async () => {
    if ((p.settings || []).some(x => x.required && !String((p.values || {})[x.key] ?? "").trim())) {
      hmOpen("plg:" + p.id); toast("Заполните настройки — и «Установить»"); return; }
    $("#ht-on").disabled = true;
    try {
      const r = await core.call("plugin_install", { id: p.id, values: {} });
      HM.all = (r && r.plugins) || HM.all; HM.plg = HM.all.filter(x => x.installed); HM.tryDone = p.id;
      if (typeof plgSet === "function" && r) plgSet(r);
      hmRender(); hmNav();
    } catch (e) { toast(e.message); if ($("#ht-on")) $("#ht-on").disabled = false; }
  };
}
function hmWire() {
  $$("#hm-body [data-go]").forEach(b => b.onclick = () => hmGo(b.dataset.go));
  $$("#hm-body [data-pad]").forEach(b => b.onclick = () => hmOpen("pad"));
  $$("#hm-apps [data-open], #hm-plgs [data-open]").forEach(b => b.onclick = () => { if (!HM.edit) hmOpen(b.dataset.open); });
  $$("#hm-plgs [data-plgall], #hm-plg-all").forEach(b => b.onclick = () => { const na = $("#nav-plg-all"); if (na) na.click(); });
  $$("#hm-apps [data-tg], #hm-plgs [data-tg]").forEach(i => i.onchange = () => {
    const cur = hmApps(), id = i.dataset.tg, next = i.checked ? cur.concat(cur.includes(id) ? [] : [id]) : cur.filter(x => x !== id);
    if (!next.length) { i.checked = true; toast("Хотя бы один значок оставьте"); return; }
    hmSave(next); hmRender(); });
  if (!HM.edit) return;
  let drag = null;
  $$("#hm-apps .hm-app, #hm-plgs .hm-app").forEach(el => {
    el.ondragstart = (e) => { drag = el.dataset.app; el.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; };
    el.ondragend = () => { el.classList.remove("drag"); drag = null; };
    el.ondragover = (e) => { if (drag && drag !== el.dataset.app) { e.preventDefault(); el.classList.add("over"); } };
    el.ondragleave = () => el.classList.remove("over");
    el.ondrop = (e) => { e.preventDefault(); el.classList.remove("over"); const cur = hmApps(); if (!drag || !cur.includes(drag)) return;
      const to = el.dataset.app, list = cur.filter(x => x !== drag), i = list.indexOf(to);
      if (i < 0) return; list.splice(i, 0, drag); hmSave(list); hmRender(); };
  });
}
$("#hm-edit").onclick = () => { HM.edit = !HM.edit; hmRender(); };
const hmCur = () => $("#p-home").classList.contains("cur");
let hmT = 0; const hmSoon = () => { clearTimeout(hmT); hmT = setTimeout(() => { if (hmCur()) loadHome(); }, 400); };
core.on("hello", () => setTimeout(() => { hmNav(); ngApply(); }, 0)).on("settings", () => setTimeout(() => { hmNav(); ngApply(); }, 0)).on("hello", hmSoon).on("close", hmSoon).on("tasks", hmSoon).on("done", hmSoon);
setInterval(() => { if (hmCur() && !document.hidden) hmRender(); }, 60000);    // «Дальше сегодня» и приветствие — по часам
