"""Жалобы 26.11 (день):
- №1117, №1118 (своя модель Qwen3.5-4B): «Проверь почту» — «Проверка почты завершена» и три письма без read_emails: письма
  пришли из прошлого разговора, поднятого к вопросу. Теперь: просили проверить почту, а действия с почтой нет — модель
  переспрашивают; кусок прошлого разговора в подсказке помечен «прошлый разговор, не свежие данные»; в «Рентгене» без
  поправок — «Без поправок», а не «Всё чисто» (будто ответ проверен);
- №1122 (gemma4:e2b): «Вызываю инструмент read_emails», а действий нет — проверить почту и прочитать последнее письмо
  программа делает сама до модели, действие видно в ходе; почта не ответила — честно и с причиной;
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
ok("mail_fresh_missing(text, step_text, self._mail_on(), set(called) | set(getattr(turn, \"mail_fetched\", ()) or ()))" in eng, "проверка стоит в ходе")

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

# ---------- №1122 (Ollama gemma4:e2b): «Вызываю инструмент read_emails» — а действий нет; программа проверяет почту сама ----------
import types  # noqa: E402
import engine_answer as EA  # noqa: E402
import exam  # noqa: E402


class TB:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def run(self, name, a):
        self.calls.append((name, dict(a)))
        if self.fail:
            raise RuntimeError(self.fail)
        if name == "read_emails":
            return "[77] ● 26.11 18:00 · Андрей <a@list.ru> · «Счёт» — оплатите до пятницы\n\nЦеликом письмо — read_email…"
        return "От: Андрей\nТема: Счёт\n\nОплатите до пятницы, пожалуйста."


class ME:
    _mail_prefetch = EA.AnswerMixin._mail_prefetch

    def __init__(self, on=True, fail=None):
        self.toolbox, self.on, self.events = TB(fail), on, []

    def _mail_on(self):
        return self.on

    def emit(self, type_, **kw):
        self.events.append(dict(kw, type=type_))


e = ME()
tn = types.SimpleNamespace()
ctx = e._mail_prefetch("Проверь почту List.ru", tn)
ok(e.toolbox.calls == [("read_emails", {"limit": 8, "box": "List.ru"})] and "свежие данные" in ctx and "«Счёт»" in ctx,
   f"«Проверь почту List.ru» — программа сама вызвала read_emails (ящик назван): {e.toolbox.calls}")
t = exam.tools_of(e.events)
ok(t and t[0]["name"] == "read_emails" and t[0].get("ok", True) and "Счёт" in str(t[0].get("result")), f"действие видно в ходе (и экзамену): {t[:1]}")
ok(tn.mail_fetched == {"read_emails"}, "проверка «просили почту — а действия нет» знает, что действие было")
e = ME()
tn = types.SimpleNamespace()
ctx = e._mail_prefetch("Прочитай последнее письмо на лист.ру.", tn)
ok([c[0] for c in e.toolbox.calls] == ["read_emails", "read_email"] and e.toolbox.calls[1][1] == {"uid": "77"} and "Оплатите до пятницы" in ctx,
   f"«Прочитай последнее письмо» — нашла последнее, взяла номер, прочитала целиком: {e.toolbox.calls}")
e = ME()
ok(e._mail_prefetch("Есть новые письма?", types.SimpleNamespace()) and e.toolbox.calls[0][1].get("unread_only") is True, "«новые письма» — только непрочитанные")
e = ME(fail="IMAP: неверный пароль приложения")
ctx = e._mail_prefetch("Проверь почту", types.SimpleNamespace())
ok("проверить не смогла" in ctx and "неверный пароль" in ctx and any(x.get("status") == "error" for x in e.events),
   "почта не ответила — «проверка не выполнена» и причина, в ходе — ошибка, а не «сделано»")
for q in ("Ответь Андрею на письмо", "Проверь почту и удали спам", "Отправь письмо маме", "Сделай таблицу Excel по почте"):
    e = ME()
    ok(e._mail_prefetch(q, types.SimpleNamespace()) == "" and not e.toolbox.calls, f"«{q}» — не проверка: решает модель (и с подтверждением)")
e = ME(on=False)
ok(e._mail_prefetch("Проверь почту", types.SimpleNamespace()) == "" and not e.toolbox.calls, "почта не подключена — сами не лезем")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
