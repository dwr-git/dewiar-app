"""Экзамен компьютера 0.81.1 (04.11, «DWR Chat Qwen 3.8», 67 из 92): «сказала, но не сделала» и ответы без инструментов.
Как на телефоне (коммит 7cfe573, экзамен 0.9.18), но в ядре компьютера:
- «Открой сайт википедии» — web_search и «Готово, открыта» без open_url → переспрос (open_claim); на экзамене (ядро --server
  с EXAM_LAUNCH) open_url, show_page и council теперь есть — запуск там записывается; на сервере без окна show_page честно
  отдаёт файл;
- ссылка в вопросе без read_webpage (url_unread), погода и курс числами без инструмента (invented_numbers; утро без города —
  «погоды нет», не выдумывать), «сколько я написал» без writing_today, «собери совет» — call_persona не выполняется, council;
- вопрос о самом приложении — руководство прикладывается к вопросу (guide.attach, событие app_help), «такого нет» без
  руководства — переспрос с выдержкой (feature_deny); в data/guide.json — «Видеоуроки», «сын/дочь» → детский режим,
  «задания сотрудникам через Телеграм» → «Поручения»;
- «что по плану» — время дела, которого нет в делах, → переспрос (agenda_invented); четверостишие — 4 строки и рифма;
- «Запиши потраченную 2.000 руб» — две тысячи в «Деньгах», не заметка; «Кафе» от модели — та же категория, что «Кафе и
  рестораны» (890 + 1250 = 2140); «остановимся на 65 тысячах» — remember, а не money_add;
- быстрый ответ («17% от 2350 — 399,5») — в разговоре сразу, «объясни, как посчитал» видит его;
- set_reminder: when «завтра в 9» главнее «послезавтра» в тексте;
- переспрос заменяет неверный ответ: придержанный шаг не звучит и не остаётся в тексте;
- экзамен: «Больше ничего не запланировано» — не провал проверки «нет: ничего не запланировано»; журнал сработавших
  напоминаний чистится между испытаниями; в отчёт — строка исключения, а не одно «Traceback».
Обычный разговор («как дела?», «сколько градусов в прямом угле?», совет фильма) — без переспросов."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "ust"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "ucfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- проверки по отдельности ----------
import quality as Q  # noqa: E402
ok(Q.open_claim("Открой, пожалуйста, сайт википедии.", "Готово, Википедия открыта в браузере.", {"web_search"}) != "",
   "«открыта» после одного web_search — переспрос open_url")
ok(Q.open_claim("Открой сайт википедии", "Открыла Википедию.", {"open_url"}) == "" and Q.open_claim("Открой сайт", "Какой сайт открыть?") == ""
   and Q.open_claim("Что такое Википедия?", "Энциклопедия, открытая для всех.") == "", "открыла по-настоящему, вопрос, не просьба — без переспроса")
ok(Q.url_unread("Посмотри сайт https://www.python.org/ и коротко напиши, что там есть", "Я посмотрела сайт: About, Downloads.") != ""
   and Q.url_unread("Посмотри сайт https://www.python.org/", "Там About.", {"read_webpage"}) == "", "ссылка без read_webpage — переспрос")
ok(Q.ask_url("глянь, что на example.com") == "example.com" and Q.ask_url("пиши на ivan@mail.ru") == "", "ссылка в вопросе, почта — не ссылка")
ok(Q.invented_numbers("Еду в Дубай с 3 по 10 ноября. Что взять с собой?", "Днём жарко, около 30-33 градусов.") != "",
   "поездка: градусы без weather — переспрос")
ok(Q.invented_numbers("[Утро с Лирой] сводка", "В Минске около +4.", known="Погода: данных нет") != ""
   and Q.invented_numbers("[Утро с Лирой] сводка", "В Минске +4.", known="Погода (уже узнана): Минск: сейчас +4°") == "",
   "утро: градусы, которых нет в данных, — переспрос; из данных — нет")
ok(Q.invented_numbers("Сколько градусов в прямом угле?", "90 градусов.") == "" and Q.invented_numbers("Какая погода?", "+4", {"weather"}) == ""
   and Q.invented_numbers("При какой температуре кипит вода?", "При 100 градусах.") == "", "градусы не о погоде и погода из weather — без переспроса")
ok(Q.writing_missing("Сколько я написал сегодня?", "4 812 слов.") != "" and Q.writing_missing("Сколько я написал сегодня?", "…", {"writing_today"}) == "",
   "«сколько написал» без writing_today — переспрос")
ok(Q.council_missing("Собери совет: учить Python или английский?", "Передаю слово Лире.", {"call_persona"}) != ""
   and Q.council_missing("Дай совет, что подарить маме", "Цветы.") == "", "«собери совет» без council — переспрос; «дай совет» — нет")
ok(Q.feature_deny("А есть у тебя видеоуроки?", "Я голос, роликов со мной нет.") != "" and Q.feature_deny("У тебя есть брат?", "У меня нет брата.") == "",
   "«такого нет» о приложении — переспрос с руководством; о себе — нет")
ok("08:05" in Q.agenda_invented("Сработало в 8:05, а в 9:01 полить цветы.", "04.11 (сегодня) 09:01 напоминание: полить цветы",
                                datetime(2026, 11, 4, 8, 31)), "время дела, которого нет в планах, — переспрос")
ok(Q.agenda_invented("В 9:01 полить цветы, сейчас 8:31.", "04.11 (сегодня) 09:01 напоминание: полить цветы", datetime(2026, 11, 4, 8, 31)) == "",
   "время из планов и «сейчас» — без переспроса")
BAD = "Дым над речью, осень, тишина,\nГолый клён стоит в сирой траве.\nСлышишь, где-то капает вода\nИ кружат листья в воздухе, как пчёлы в мае."
GOOD = "Осень бродит по садам,\nРыжий лист кружит у ног,\nТихо шепчет: я отдам\nВам последний свой цветок."
ok("нет рифмы" in Q.poem_check("Напиши четверостишие про осень с настоящей рифмой.", BAD), "четверостишие без рифмы — переспрос")
ok("4 строки, а в стихе 5" in Q.poem_check("Напиши четверостишие", GOOD + "\nИ уходит за порог."), "пять строк вместо четырёх — переспрос")
ok(Q.poem_check("Напиши четверостишие", "Вот:\n\n" + GOOD + "\n\nНравится?") == "" and Q.poem_check("Расскажи про осень", BAD) == "",
   "хороший стих с вступлением и вопросом, просьба не о стихах — без переспроса")
ok(Q.money_claim("Ладно, остановимся на 65 тысячах.", "Записала: 65 тысяч.") == "" and Q.saved_claim("Ладно, остановимся на 65 тысячах.", "Записала: 65 тысяч.") != ""
   and Q.money_claim("Бюджет на мебель — 50 тысяч.", "Записала.", {"remember"}) == "", "бюджет — не «Деньги»: remember, а не money_add")
ok(Q.money_claim("Запиши потраченную 2.000 руб.", "Записала.") != "", "трата «записала» без money_add — переспрос, как было")

# ---------- рецензия 0.82: проверки не срабатывают на нормальных ответах ----------
# 1) «нужен совет» — просьба посоветовать, а не совет персонажей
for q_ in ("Мне нужен совет: что подарить маме?", "Нужен твой совет по ремонту", "Позови Патрика, нужен его совет", "Давай совет, что почитать",
           "Дай совет, что подарить маме"):
    ok(not Q.COUNCIL_ASK.search(q_) and Q.council_missing(q_, "Цветы и открытку.") == "", f"«{q_}» — не совет персонажей")
for q_ in ("Собери совет: учить Python или английский?", "Созови совет — переезжать ли мне?", "Устрой совет персонажей", "Проведи совет команды",
           "Что скажет совет ИИ?"):
    ok(bool(Q.COUNCIL_ASK.search(q_)), f"«{q_}» — совет персонажей")
# 2) температура и «жарко» — не всегда погода
for q_, a_ in (("У ребёнка температура сейчас 38,5, что делать?", "При 38,5 градусах дайте жаропонижающее и много питья."),
               ("В квартире жарко, на сколько поставить кондиционер?", "Поставьте 24–25 градусов."),
               ("Что надеть на свадьбу?", "Платье до колена; в зале обычно +22°."),
               ("Холодно в комнате, что делать?", "Проверьте окна: при +18 градусах уже зябко."),
               ("Какая температура у ребёнка нормальная?", "36,6 градуса.")):
    ok(not Q.WEATHER_ASK.search(q_) and Q.invented_numbers(q_, a_) == "", f"«{q_}» — не о погоде, без переспроса")
for q_ in ("Сколько градусов на улице?", "Какая температура в Минске?", "Холодно ли сегодня в Москве?", "Что надеть завтра в Минске?",
           "Какая завтра температура?", "Какая погода?"):
    ok(bool(Q.WEATHER_ASK.search(q_)), f"«{q_}» — о погоде")
# 5) «Открой почту» — read_emails и есть открытие
ok(Q.open_claim("Открой почту, что нового?", "Открыла почту: два новых письма.", {"read_emails"}) == ""
   and Q.open_claim("Открой почту", "Открыла почту.", {"web_search"}) != "", "почта: read_emails — это «открыла»; без него — переспрос")
ok({"read_emails", "send_email", "find_notes", "calendar_list", "read_file"} <= Q.OPEN_TOOLS, "инструменты, которые сами «открывают», — в OPEN_TOOLS")
# 6) стихи: число строк — только когда однозначно; заголовок — не строка
HAI = "Старый тихий пруд.\nПрыгнула в воду лягушка.\nВсплеск в тишине."
GOOD3 = "Осень бродит по садам,\nРыжий лист кружит у ног,\nТихо шепчет: я отдам\nВам последний свой цветок."
ok(Q.poem_check("Напиши стих из трёх четверостиший про осень", "\n\n".join([GOOD3] * 3)) == "", "три четверостишия (12 строк) — без переспроса")
ok(Q.poem_check("Напиши два четверостишия", GOOD3 + "\n\n" + GOOD3) == "" and Q.poem_check("Напиши три хокку", "\n\n".join([HAI] * 3)) == ""
   and Q.poem_check("Стихотворение, где каждое четверостишие — о времени года", GOOD3 + "\n\n" + GOOD3) == "", "несколько строф — не проверяем")
for head in ("**Пруд**\n", "# Пруд\n", "Пруд\n\n", "«Пруд»\n"):
    ok(Q.poem_check("Напиши хокку про пруд", head + HAI) == "", f"заголовок {head.strip()!r} — не строка хокку")
ok(Q.poem_check("Напиши четверостишие", "**Осень**\n" + GOOD3) == "", "четверостишие с заголовком — без переспроса")
ok("3 строки, а в стихе 4" in Q.poem_check("Напиши хокку", HAI + "\nИ ещё одна строка."), "хокку из 4 строк — по-прежнему переспрос")
# 7) планы: свободное время, «до», «напомнить?», предложения — не выдуманные дела
AG = "04.11 (сегодня) 10:00 встреча с Ирой"
for a_ in ("В 10:00 встреча, после 12:00 вы свободны.", "В 10:00 встреча. Напомнить в 9:30?", "В 10:00 встреча, до 18:00 больше ничего.",
           "В 10:00 встреча. Предлагаю перенести звонок на 15:00.", "В 10:00 встреча, а с 14:00 можно отдохнуть.", "В 10:00 встреча; могу напомнить в 9:45."):
    ok(Q.agenda_invented(a_, AG, datetime(2026, 11, 4, 8, 0)) == "", f"«{a_}» — без переспроса")
ok("15:00" in Q.agenda_invented("В 10:00 встреча, в 15:00 звонок Ивану.", AG, datetime(2026, 11, 4, 8, 0)), "выдуманное дело в 15:00 — переспрос")
# 4) «Голос без пауз»: придерживаем только то, на чём проверка сработает, и только пока нужный инструмент не вызван
NM = {"weather", "web_search", "open_url", "read_webpage", "writing_today", "council", "money_add"}
ok(not Q.hold_sentence("Какая погода в Минске?", "Какая погода в Минске?", "В Минске сейчас +4, пасмурно.", {"weather"}, NM),
   "погода после weather — фразы идут сразу")
ok(Q.hold_sentence("Какая погода в Минске?", "Какая погода в Минске?", "В Минске около +4.", set(), NM)
   and not Q.hold_sentence("Какая погода в Минске?", "Какая погода в Минске?", "Сейчас узнаю.", set(), NM), "без weather — придерживаем только фразу с градусами")
ok(not Q.hold_sentence("[Утро с Лирой] сводка", "[Утро с Лирой] сводка", "Доброе утро! Сегодня среда.", set(), NM, known="Погода: данных нет")
   and Q.hold_sentence("[Утро с Лирой] сводка", "[Утро с Лирой] сводка", "В Минске около +4.", set(), NM, known="Погода: данных нет")
   and not Q.hold_sentence("[Утро с Лирой] сводка", "[Утро с Лирой] сводка", "В Минске +4.", set(), NM, known="Погода (уже узнана): Минск: +4°"),
   "утро: придерживаем только выдуманные градусы, обычные фразы — сразу")
ok(not Q.hold_sentence("Напиши четверостишие", "Напиши четверостишие", "Осень бродит по садам,", set(), NM)
   and not Q.hold_step("Напиши четверостишие", set(), NM) and not Q.hold_step("А есть у тебя видеоуроки?", set(), NM),
   "стихи и вопросы о приложении — не придерживаем (проверка после)")
ok(Q.hold_sentence("Открой сайт википедии", "Открой сайт википедии", "Готово, Википедия открыта.", {"web_search"}, NM)
   and not Q.hold_sentence("Открой сайт википедии", "Открой сайт википедии", "Открыла Википедию.", {"open_url"}, NM)
   and not Q.hold_sentence("Открой сайт википедии", "Открой сайт википедии", "Сейчас найду адрес.", set(), NM), "открыть: только «открыта» без open_url")
ok(Q.hold_step("Посмотри сайт https://python.org и скажи, что там", set(), NM)
   and not Q.hold_step("Посмотри сайт https://python.org и скажи, что там", {"read_webpage"}, NM)
   and Q.hold_step("Сколько я написал сегодня?", set(), NM) and not Q.hold_step("Сколько я написал сегодня?", {"writing_today"}, NM)
   and not Q.hold_step("Какой курс доллара?", set(), NM) and not Q.hold_step("Привет! Как дела?", set(), NM),
   "весь шаг — только пока нужный инструмент не вызван (ссылка, «сколько написал»)")
ok(Q.hold_sentence("Ладно", "Запиши потраченную 2.000 руб.", "Записала.", set(), NM)
   and not Q.hold_sentence("Ладно", "Запиши потраченную 2.000 руб.", "Записала.", {"money_add"}, NM), "деньги: «записала» без money_add — придерживаем, после — нет")
ok(Q.hold_sentence("Что по плану?", "Что по плану?", "В 13:17 презентация.", set(), NM, agenda=AG)
   and not Q.hold_sentence("Что по плану?", "Что по плану?", "В 10:00 встреча с Ирой.", set(), NM, agenda=AG), "планы: только дело не из планов")
src_a = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("strict[0] = gate[0] and _hold_step(ask0, called, names0)" in src_a and "_hold_s(ask0, text, s_, called" in src_a
   and "_PL)" not in src_a and "_app\n" not in src_a, "ядро: строгий режим — по hold_step/hold_sentence на каждом шаге, а не весь ход")

import money as M  # noqa: E402
c = M.parse("Запиши потраченную 2.000 руб.", "RUB")
ok(c and c["op"] == "add" and c["amount"] == 2000, f"«потраченную 2.000 руб» — расход 2000: {c}")
ok(M.parse("купил хлеб за 2.50", "RUB")["amount"] == 2.5 and M.parse("потратил 1.250.000 на машину", "RUB")["amount"] == 1250000,
   "2.50 — два с половиной, 1.250.000 — миллион с четвертью")
ok(M.canon_category("Кафе") == "Кафе и рестораны" and M.canon_category("рестораны") == "Кафе и рестораны" and M.canon_category("Мебель") == "Мебель"
   and M.canon_category("продукты") == "Продукты", "категория модели — к своей из списка (другое название той же категории), своя остаётся")
# рецензия 0.82 (коммит 1f1018d обещал): своя категория из одного слова — как написана, а не общая по ключевому слову
for c_ in ("Бензин", "Такси", "Аптека", "Ремонт балкона", "дом"):
    ok(M.canon_category(c_) == c_, f"своя категория «{c_}» остаётся как написана: {M.canon_category(c_)!r}")
names_ = {n for n, _ in M.EXPENSE_CATS}
ok(set(M.CAT_SYNONYMS["expense"]) <= names_ and set(M.CAT_SYNONYMS["income"]) <= {n for n, _ in M.INCOME_CATS},
   "синонимы — только к существующим категориям")
mt = M.Money(tmp / "money_cat.json", currency_fn=lambda: "RUB")
mt.add("expense", 50, "RUB", "Бензин", "бензин")
mt.add("expense", 30, "RUB", "Аптека", "аптека")
ok({x["category"] for x in mt.items} == {"Бензин", "Аптека"}, f"в записях — своя категория: {[x['category'] for x in mt.items]}")
mm = M.Money(tmp / "money.json", currency_fn=lambda: "RUB")
mm.add("expense", 890, "RUB", "Кафе и рестораны", "кафе")
mm.items.append({"id": "old1", "date": datetime.now().date().isoformat(), "kind": "expense", "amount": 1250.0, "currency": "RUB",
                 "category": "Кафе", "note": "Кафе", "said": "", "created": 1})       # запись прежней версии
a = mm.answer(M.parse("Сколько я сегодня потратил на кафе?", "RUB"))
ok("2 140" in a, f"«сколько на кафе» — обе записи: {a}")
import capture  # noqa: E402
ok(capture.parse("Запиши потраченную 2.000 руб.") is None and capture.parse("запиши в заметки, что билет стоит 300 рублей")["op"] == "note",
   "трата не становится заметкой; «в заметки» — заметка")
import tools as T  # noqa: E402
w = T._when({"when": "завтра в 9", "text": "Встреча с Ирой — послезавтра в 12"})
ok(w[0] == datetime.combine(datetime.now().date() + timedelta(days=1), datetime.min.time()).replace(hour=9), f"when «завтра в 9» главнее текста: {w[0]}")
ok(T._when({"when": "каждый день в 8", "text": "таблетки"})[1] == {"kind": "daily", "time": "08:00"}, "повтор из when — как был")
ok("show_page" not in T.SERVER_OFF and "open_url" in T.SERVER_OFF, "show_page на сервере не выключен (сохраняет файл), open_url — выключен")
src_t = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok('not (EXAM_LAUNCH and name in EXAM_ON)' in src_t and T.EXAM_ON == {"open_url", "open_app", "open_path", "council"},
   "экзамен (EXAM_LAUNCH): открыть сайт, программу и собрать совет можно (запуск записывается), звука и экрана нет")
import images  # noqa: E402
its = [{"title": "Heaving line knot ABOK538"}, {"title": "Runestone U 344"}]
ok(images.relevant(its, "runestone knotwork runic inscription") == [its[1]] and images.relevant(its, "церковь") == [], "картинки: подписи по запросу")
import guide  # noqa: E402
for q, want in (("Как сделать, чтобы сын мог разговаривать с тобой безопасно, без лишнего?", "Совёнок Уго"),
                ("А есть у тебя видеоуроки, чтобы посмотреть, что ты умеешь?", "«Обучение» → «Видеоуроки»"),
                ("Как мне добавить маму, чтобы мы могли переписываться через наших помощников?", "Пригласить"),
                ("Я руковожу небольшой фирмой. Как давать задания сотрудникам через Телеграм, чтобы они отмечали, что сделали?", "@BotFather"),
                ("Хочу, чтобы у меня на сайте был консультант, отвечал людям и собирал заявки. Так можно?", "Чат для сайта"),
                ("Хочу вести общий бюджет с женой, чтобы видеть траты друг друга. Как это сделать?", "«Семья»"),
                ("Я поставил Dewiar на второй компьютер. Где взять код, чтобы связать его с моим телефоном?", "Подключить ещё устройство")):
    g = guide.attach(q, "pc")
    ok(want in g, f"руководство к вопросу «{q[:45]}…» — «{want}»")
for q in ("Как дела?", "Как сварить борщ?", "У тебя есть брат?", "Есть у тебя любимая книга?", "Посоветуй, что посмотреть"):
    ok(guide.attach(q, "pc") == "", f"«{q}» — не о приложении, руководство не прикладываем")
import exam as E  # noqa: E402
r = E.check_answer({"none": ["ничего не запланировано"]}, "Завтра в 10:00 позвонить маме. Больше на завтра ничего не запланировано.")
ok(r[0]["ok"] and not E.check_answer({"none": ["ничего не запланировано"]}, "На завтра ничего не запланировано.")[0]["ok"],
   "экзамен: «больше ничего не запланировано» после дела — не провал; просто «ничего» — провал")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("help_kids_have" in sc and sc["open_site_named"]["tool"] == {"open_url": 1}, "сценарии экзамена: «есть для детей?», «открой python.org»")
src_e = (ROOT / "core/exam.py").read_text(encoding="utf-8")
ok('"reminders-log.json"' in src_e and "Traceback: {exc" in src_e, "экзамен: журнал напоминаний чистится, в отчёте — строка исключения")
src_m = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("Погода: данных нет" in src_m and "узнай инструментом weather по" not in src_m, "утро без погоды — «данных нет, не называй»")


# ---------- настоящее ядро с подставной моделью «плохих ответов» ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


REQ = []
UP, PORT = free(), free()
LATE = (datetime.now() + timedelta(hours=5, minutes=17)).strftime("%H:%M")


def txt(m):
    c = m.get("content")
    return c if isinstance(c, str) else " ".join(str(x.get("text") or "") for x in c or [] if isinstance(x, dict))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/search"):
            b = json.dumps({"results": [{"title": "Википедия — свободная энциклопедия", "url": "https://ru.wikipedia.org", "content": "Википедия"}]},
                           ensure_ascii=False).encode()
            ct = "application/json"
        elif self.path.startswith("/page"):
            b = "<html><body><main><h1>Пример</h1><p>Страница-пример: разделы «Новости» и «Скачать».</p></main></body></html>".encode()
            ct = "text/html; charset=utf-8"
        else:
            b = json.dumps({"data": [{"id": "m"}]}).encode(); ct = "application/json"
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        system = txt(msgs[0]) if msgs and msgs[0]["role"] == "system" else ""
        idx = max([i for i, m in enumerate(msgs) if m["role"] == "user" and "(Сообщение пользователя)\n" in txt(m)] or
                  [max([i for i, m in enumerate(msgs) if m["role"] == "user"] or [0])])
        cur = txt(msgs[idx])
        ask, head = cur.split("(Сообщение пользователя)\n")[-1], cur.split("(Сообщение пользователя)\n")[0]
        later = msgs[idx + 1:]
        nud = [i for i, m in enumerate(later) if m["role"] == "user" and txt(m).startswith(("ПРОВЕРКА", "СТОП"))]
        after = later[nud[-1] + 1:] if nud else later
        tres = [str(m.get("content")) for m in after if m["role"] == "tool"]
        REQ.append({"ask": ask, "head": head, "system": system, "nudge": txt(later[nud[-1]]) if nud else "", "tres": tres,
                    "all": json.dumps(msgs, ensure_ascii=False)})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())

        def say(t):
            send({"content": t}); send({}, "stop")

        def call(name, args):
            send({"tool_calls": [{"index": 0, "id": f"c{len(REQ)}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]})
            send({}, "tool_calls")
        n = bool(nud)
        if "википеди" in ask:
            if not n:
                call("web_search", {"query": "Википедия"}) if not tres else say("Готово, Википедия открыта в браузере.")
            else:
                call("open_url", {"url": "https://ru.wikipedia.org"}) if not tres else say("Открыла Википедию.")
        elif "Посмотри сайт" in ask:
            if not n:
                say("Я посмотрела сайт. Там разделы About и Downloads.")
            else:
                call("read_webpage", {"url": f"http://127.0.0.1:{UP}/page"}) if not tres else say("Прочитала: это страница-пример.")
        elif "Дубай" in ask:
            say("Возьми паспорт, крем и очки." if n else "Днём там жарко, около 30-33 градусов. Возьми паспорт и крем.")
        elif "видеоурок" in ask:
            say("Да, есть видеоуроки: студия → «Обучение» → «Видеоуроки»." if "«Обучение» → «Видеоуроки»" in head
                else "Я голос, роликов со мной нет.")
        elif "Собери совет" in ask:
            later_tools = [str(m.get("content")) for m in later if m["role"] == "tool"]
            if not later_tools:
                call("call_persona", {"name": "Лира"})
            elif len(later_tools) == 1:
                call("council", {"question": "учить Python или английский"})
            else:
                say("Собрала совет — обсуждают.")
        elif "написал" in ask:
            if not n:
                say("Сегодня вы написали 4 812 слов.")
            else:
                call("writing_today", {}) if not tres else say("По вашим текстам за сегодня: " + tres[-1][:60])
        elif "четверостиш" in ask:
            say(GOOD if n else BAD)
        elif "[Утро с Лирой]" in ask:
            say("Доброе утро! Сегодня можно не спешить." if n else "Доброе утро! В Минске около +4, пасмурно.")
        elif "по плану" in ask:
            say("Через полчаса — полить цветы." if n else f"В {LATE} подготовить презентацию, и ещё полить цветы.")
        elif "65 тысяч" in ask:
            if not n:
                say("Записала: 65 тысяч.")
            else:
                call("remember", {"fact": "Бюджет на мебель — 65 тысяч"}) if not tres else say("Запомнила: 65 тысяч.")
        elif "Объясни" in ask:
            say("Считала так: 2350 × 0,17 = 399,5.")
        elif "прямом угле" in ask:
            say("В прямом угле 90 градусов.")
        elif "Посоветуй" in ask:
            say("Посмотри «Амели» (2001) — тёплое кино о мелочах.")
        else:
            say("Всё хорошо, спасибо!")
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False}, "tools": {"search_url": f"http://127.0.0.1:{UP}"}, "welcome": {"on": False},
    "llm": {"active": "m", "tools_probe_v": 5, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m", "context": 131072}}}}, ensure_ascii=False), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_DRY_TOOLS=str(tmp / "launched.jsonl"))
R, EV = {}, []
ASKS = [("wiki", "Открой, пожалуйста, сайт википедии."),
        ("url", f"Посмотри сайт http://127.0.0.1:{UP}/page и коротко напиши, что там есть"),
        ("trip", "Еду в Дубай с 3 по 10 ноября. Что взять с собой?"),
        ("video", "А есть у тебя видеоуроки, чтобы посмотреть, что ты умеешь?"),
        ("council", "Собери совет: стоит ли мне в этом году учить Python или лучше английский?"),
        ("writing", "Сколько я написал сегодня?"),
        ("poem", "Напиши четверостишие про осень с настоящей рифмой."),
        ("morning", "Расскажи утро"),
        ("plan", "Что у нас по плану?"),
        ("budget", "Ладно, остановимся на 65 тысячах."),
        ("money", "Запиши потраченную 2.000 руб."),
        ("hi", "Привет! Как дела?"), ("angle", "Сколько градусов в прямом угле?"), ("film", "Посоветуй фильм на вечер")]


async def session():
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (tmp / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
        cnt, replies = [0], {}

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    EV.append(e)
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(1200):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def final(mark, t=40):
            last_n, quiet = -1, 0
            for _ in range(t * 20):
                d = [e for e in EV[mark:] if e["type"] == "answer" and e.get("done")]
                quiet = quiet + 1 if d and len(EV) == last_n else 0
                last_n = len(EV)
                if quiet >= 30:
                    return d[-1].get("text", "")
                await asyncio.sleep(0.05)
            d = [e for e in EV[mark:] if e["type"] == "answer" and e.get("done")]
            return d[-1].get("text", "") if d else ""
        await call("reminder_add", phrase="через 30 минут полить цветы")
        for key, q in ASKS:
            m = len(EV)
            await call("say", text=q)
            R[key] = await final(m)
            R[key + "_ev"] = EV[m:]
        m = len(EV)                                        # «17% от 2350» — без модели; и сразу, не дожидаясь, — «объясни»
        await call("say", text="Сколько будет 17 процентов от 2350?")
        for _ in range(40):
            if any(e["type"] == "answer" and e.get("done") for e in EV[m:]):
                break
            await asyncio.sleep(0.05)
        m2 = len(EV)
        await call("say", text="Объясни, как ты это посчитал.")
        R["explain"] = await final(m2)
        R["money_list"] = ((await call("money_list")) or {}).get("data")
        R["reminders"] = ((await call("reminders")) or {}).get("data")
        rd.cancel(); await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

asyncio.run(session())
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
srv.shutdown()


def reqs(word):
    return [r for r in REQ if word in r["ask"]]


launched = (tmp / "launched.jsonl").read_text(encoding="utf-8") if (tmp / "launched.jsonl").exists() else ""
ok(any("open_url" in r["nudge"] for r in reqs("википеди")) and "wikipedia" in launched, f"«открыта» без open_url — переспрос, сайт открыт: {launched[:120]}")
ok(R["wiki"] == "Открыла Википедию.", f"неверное «Готово, открыта» не осталось в ответе: {R['wiki']!r}")
ok(any("read_webpage" in r["nudge"] for r in reqs("Посмотри сайт")) and "В вопросе ссылка" in reqs("Посмотри сайт")[0]["head"],
   "ссылка: подсказка прочитать и переспрос без read_webpage")
ok(R["url"].startswith("Прочитала") and "About" not in R["url"], f"ответ — по прочитанному: {R['url']!r}")
ok(any("weather" in r["nudge"] for r in reqs("Дубай")) and "33" not in R["trip"] and "сначала узнай погоду" in reqs("Дубай")[0]["head"],
   f"поездка: градусы без weather — переспрос, выдумка не осталась: {R['trip']!r}")
ok("«Обучение» → «Видеоуроки»" in R["video"] and any(e.get("type") == "tool" and e.get("name") == "app_help" and e.get("status") == "done"
                                                   for e in R["video_ev"]), f"видеоуроки: руководство приложено (app_help): {R['video']!r}")
cr = reqs("Собери совет")
ok(cr and "СЕЙЧАС ПРОСЯТ СОБРАТЬ СОВЕТ" in cr[0]["system"], "совет: подсказка вызвать council")
ok(any("Не передано: это просьба собрать совет" in r["all"] for r in cr), "совет: call_persona не выполнен — просим council")
ok("Лира откликнется" not in " ".join(r["all"] for r in cr), "передачи слова Лире не было")
wr = reqs("написал")
ok(wr and "СЕЙЧАС СПРАШИВАЮТ, СКОЛЬКО НАПИСАНО" in wr[0]["system"] and any("writing_today" in r["nudge"] for r in wr) and "4 812" not in R["writing"],
   f"«сколько написал»: подсказка, переспрос, выдуманного числа нет: {R['writing']!r}")
ok(R["poem"] == GOOD, f"четверостишие без рифмы — переписано, плохое не осталось: {R['poem']!r}")
mo = reqs("[Утро с Лирой]")
ok(mo and "Погода: данных нет" in mo[0]["ask"] and "+4" not in R["morning"] and any("погоду" in r["nudge"] for r in mo),
   f"утро: «погоды нет» в данных, выдуманные +4 — переспрос: {R['morning']!r}")
ok(LATE not in R["plan"] and any(LATE in r["nudge"] for r in reqs("по плану")), f"план: выдуманное дело в {LATE} — переспрос: {R['plan']!r}")
bu = reqs("65 тысяч")
ok(any("remember" in r["nudge"] and "Вызови money_add сейчас" not in r["nudge"] for r in bu), "«остановимся на 65 тысячах» — просим remember, а не money_add")
mem = (tmp / "ws" / "Память" / "Обо мне.md").read_text(encoding="utf-8") if (tmp / "ws" / "Память" / "Обо мне.md").exists() else ""
ok("65 тысяч" in mem, f"бюджет 65 тысяч — в памяти: {mem[-200:]!r}")
ml = R.get("money_list") or []
ok(any(abs(float(x.get("amount", 0)) - 2000) < 0.01 for x in ml) and "Потраченную" not in R["money"], f"«потраченную 2.000 руб» — расход 2000: {R['money']!r}")
ok("399,5" in reqs("Объясни")[0]["all"] if reqs("Объясни") else False, "«объясни, как посчитал» — модель видит быстрый расчёт 399,5")
for k in ("hi", "angle", "film"):
    ok(not any(r["nudge"] for r in reqs(dict(ASKS)[k][:12])) and len(reqs(dict(ASKS)[k][:12])) == 1, f"«{dict(ASKS)[k]}» — без переспроса: {R[k]!r}")
ok("Traceback" not in log, "в журнале ядра нет трассировок" + ("" if "Traceback" not in log else ": " + log[log.find("Traceback"):][:600]))
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
