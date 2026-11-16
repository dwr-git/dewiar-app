"""Отчёты людей 15.11 (вторая пачка):
№736 (веб-версия): «TypeError: RP.q[0] is undefined» — стёрли поиск в «Радио», а старый результат ещё на экране.
№738 (телефон, персонаж-юрист): «Какой же это юрист? Глючит на простом вопросе» — «Поясни про главу 39 ГК РФ»: по памяти
     «Ограничение дееспособности», а глава 39 — «Возмездное оказание услуг». Статья или глава закона и кодекс в вопросе —
     отвечать по найденному тексту (web_search → read_webpage); одно правило на компьютере и телефоне; сценарий экзамена."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
wrong = "Глава 39 Гражданского кодекса РФ называется «Ограничение правоспособности и признание гражданина недееспособным». " * 2
ok("web_search" in EA.law_unsourced("Поясни про главу 39 ГК РФ", wrong, []), "компьютер: «глава 39 ГК РФ» без поиска — найди текст")
ok(EA.law_unsourced("Что в статье 80 ТК?", wrong, []) and EA.law_unsourced("Расскажи про статью 15 закона о защите прав потребителей", wrong, []),
   "статья ТК, «закон о защите прав потребителей» — тоже")
ok(not EA.law_unsourced("Поясни про главу 39 ГК РФ", wrong, ["web_search", "read_webpage"]), "нашла и прочитала — хорошо")
ok(not EA.law_unsourced("Прочитай главу 3 книги", wrong, []) and not EA.law_unsourced("Что такое ГК РФ?", wrong, []),
   "глава книги или вопрос без номера — не про это")
ea = srctext.text(ROOT, "core/engine_answer.py")
ok("law_unsourced(ask0, step_text, called)" in ea, "в цепочке проверок ответа")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("law_chapter_sourced" in sc and "дееспособн" in sc["law_chapter_sourced"]["expect"]["none"], "экзамен компьютера: «глава 39 ГК РФ»")
ok('id: "law_chapter_sourced"' in (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8"), "экзамен телефона: тот же сценарий")

www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.DW_SYS_LANG = 'ru';"); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
    r = pg.evaluate("""(() => [lawUnsourced('Поясни про главу 39 ГК РФ', %s, new Set()), lawUnsourced('Поясни про главу 39 ГК РФ', %s, new Set(['web_search'])),
                     lawUnsourced('Прочитай главу 3 книги', %s, new Set())])()""" % (json.dumps(wrong), json.dumps(wrong), json.dumps(wrong)))
    ok("web_search" in r[0] and r[1] == "" and r[2] == "", "телефон: то же правило")
    pg.evaluate("openRadio()"); pg.wait_for_timeout(300)
    pg.evaluate("RP.res = []; RP.q = ''; rpRender()"); pg.wait_for_timeout(200)
    ok(not [e for e in errs if "RP.q" in e or "undefined" in e], f"№736: стёртый поиск при старом результате — без падения: {errs[:2]}")
    b.close()
bj = (ROOT / "android/assets/www/blog.js").read_text(encoding="utf-8")
ok("BLG.list.articles.filter" not in bj and "(BLG.list.articles || [])" in bj, "«Статьи»: ответ сайта без списка — не падаем (экзамен телефона)")
wj = (ROOT / "android/assets/www/work.js").read_text(encoding="utf-8")
ok("Вы руководитель?" in wj and "«Настройки» → «Устройства»" in wj, "планшет (15.11): в «Работе» — руководителю, где его доска и как подключить")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
