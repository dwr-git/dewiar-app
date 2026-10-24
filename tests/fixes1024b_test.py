"""24.10, вечер: №238 («сможешь проанализировать xlsm?» → «Готово.»), №237 («мне выдан аккаунт — где?»), ответы на жалобы
не видны (владелец: «присылал жалобы и ни разу не получил ответ»), установщик Windows с русскими буквами в пути
(совет пользователя: «ставить без кириллического пути… чтоб был выбор диска»)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "ui"))
FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


# --- №238: голое «Готово.» на вопрос (bare_done(вопрос, ответ, вызванные) — как saved_claim) ---
from quality import bare_done  # noqa: E402

ask = "Сможешь проанализировать файл xlsm и написать по нему программу?"
ok(bare_done(ask, "Готово.", ["list_files", "read_file"]), "№238: на вопрос «сможешь?» — «Готово.» → подсказка модели")
ok("read_file" in bare_done(ask, "Готово.", ["read_file"]), "в подсказке — что модель уже посмотрела")
ok(bare_done("проанализируй таблицу и подскажи, как лучше", "Сделано!", []), "«Сделано!» на «проанализируй и подскажи» — тоже")
ok(not bare_done("поставь будильник на 7", "Готово.", ["alarm_set"]), "просьба сделать и «Готово.» — нормально, без подсказки")
ok(not bare_done("Можешь включить свет в зале?", "Готово.", ["smart_home"]), "вежливая просьба с «?» и сделанное действие — «Готово.» без подсказки")
ok(not bare_done("Напомнишь завтра позвонить маме?", "Хорошо.", []), "«Хорошо.» на вопрос — нормальный ответ")
ok(not bare_done("поставь будильник на 7?", "Готово, будильник на 7:00.", ["alarm_set"]), "ответ со смыслом — без подсказки")
ok(not bare_done(ask, "Смогу: в файле три листа с заказами, программа на Python их сведёт.", ["read_file"]), "ответ по существу — без подсказки")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("bare_done(text, step_text, called)" in src and re.search(r"from quality import [^\n]*bare_done", src), "проверка — в цепочке ответа и импортирована")

# --- №237: текст про аккаунт ---
st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok("вам выдали — введите" not in st and "Регистрации на сайте нет" in st and "Подключить бесплатно" in st,
   "№237: студия не говорит «аккаунт вам выдали»; ясно, что регистрации нет и вход обычно не нужен")
ok("Войдите аккаунтом dewiar.pro" not in st, "Dewiar.pro: заголовок не зовёт входить аккаунтом")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("Есть логин на сайте — всё настроится само" not in app and "команда Dewiar выдала вам логин" in app, "телефон: плитка «Аккаунт» — только для выданных логинов")

# --- ответы на жалобы: и в «Чат» ---
h = (ROOT / "core/health.py").read_text(encoding="utf-8")
ok('via="dev"' in h, "ответ на жалобу — ещё и в «Чат» студии")
ok('x.via === "dev" ? "ответ разработчика"' in (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8"), "в «Чате» — пометка «ответ разработчика»")

# --- установщик Windows ---
nsi = (ROOT / "packaging/windows/dewiar.nsi").read_text(encoding="utf-8")
ok("MUI_PAGE_DIRECTORY" in nsi and "латинские буквы" in nsi, "установщик: выбор папки с советом про латиницу")
ok("Function DirLeave" in nsi and "WideCharToMultiByte(i 20127" in nsi, "папка с русскими буквами — предупреждение")
ok('InstallDirRegKey HKCU "${UNKEY}" "InstallLocation"' in nsi, "переустановка — в ту же папку")
ok("GetFullPathName /SHORT" in nsi and 'StrCpy $INSTDIR "C:\\Dewiar"' in nsi, "новая установка с русским именем пользователя — короткий путь или C:\\Dewiar")
import stop_dewiar  # noqa: E402

ok(stop_dewiar._long("/x/y") == "/x/y", "остановка перед обновлением: не Windows — путь как есть")

print("\nИТОГ:", "все проверки прошли" if not FAILS else f"не прошло {len(FAILS)}")
sys.exit(1 if FAILS else 0)
