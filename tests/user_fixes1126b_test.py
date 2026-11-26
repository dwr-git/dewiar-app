"""Жалобы 26.11 (день):
- №1117, №1118 (своя модель Qwen3.5-4B): «Проверь почту» — «Проверка почты завершена» и три письма без read_emails: письма
  пришли из прошлого разговора, поднятого к вопросу. Теперь: просили проверить почту, а действия с почтой нет — модель
  переспрашивают; кусок прошлого разговора в подсказке помечен «прошлый разговор, не свежие данные»; в «Рентгене» без
  поправок — «Без поправок», а не «Всё чисто» (будто ответ проверен);
- №1116 (macOS): окно правки статьи сайта уходило под боковое меню — левый край текста не читался. Окна «Сайтов» — в body."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- №1117, №1118 ----------
from quality import mail_fresh_missing  # noqa: E402
for q in ("Проверь почту", "Что нового в почте?", "Есть новые письма?", "Прочитай письмо от Ивана"):
    ok(bool(mail_fresh_missing(q, "Проверка почты завершена: три новых письма.", True, ())), f"«{q}» без read_emails — переспросить")
ok(not mail_fresh_missing("Проверь почту", "Три письма: …", True, ("read_emails",)), "read_emails вызван — молчим")
ok(not mail_fresh_missing("Проверь почту", "Почта не подключена.", False, ()), "почта не подключена — это другая проверка (mail_claim)")
ok(not mail_fresh_missing("Напиши письмо Ивану", "Готово.", True, ()), "написать письмо — не проверка почты")
eng = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("mail_fresh_missing(text, step_text, self._mail_on(), called)" in eng, "проверка стоит в ходе")

import recall as R  # noqa: E402
ws = Path(tempfile.mkdtemp())
(ws / "Память" / "Разговоры").mkdir(parents=True)
(ws / "Память" / "Разговоры" / "2026-11-26 1128.md").write_text(
    "# Разговор\n\nЯ проверила пять последних входящих писем в ящике: счёт от провайдера, письмо от Ивана про отчёт.\n", encoding="utf-8")
src = (ROOT / "core/recall.py").read_text(encoding="utf-8")
ok("прошлый разговор" in src and "не свежие данные" in src, "кусок архива разговора — с пометкой «прошлый разговор, не свежие данные»")
import re  # noqa: E402
m = re.search(r'm = re\.match\((r"[^"]+")', src)
rx = eval(m.group(1)) if m else ""
ok(bool(rx) and re.match(rx, "Память/Разговоры/2026-11-26 1128.md") and not re.match(rx, "Заметки/Почта.md"), "архив узнаётся по пути, заметки — нет")
xj = (ROOT / "ui/studio/xray.js").read_text(encoding="utf-8")
ok('"Без поправок"' in xj and '"Всё чисто"' not in xj, "«Рентген»: без поправок — так и написано, без «Всё чисто»")

# ---------- №1116 ----------
sj = (ROOT / "ui/studio/sites.js").read_text(encoding="utf-8")
ok('for (const id of ["st-pubm", "st-histd", "st-addp", "sb-ed"])' in sj and "document.body.appendChild(el)" in sj, "окна «Сайтов» — прямо в body")
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1")
    pg.wait_for_timeout(800)
    r = pg.evaluate("['st-pubm','st-histd','st-addp','sb-ed'].map(id => { const e = document.getElementById(id); return !!e && e.parentElement === document.body; })")
    ok(all(r), f"в студии окна раздела — дети body: {r}")
    b.close()

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
