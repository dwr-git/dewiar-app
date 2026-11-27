"""Письмо 25.11 и №985/№982: «Бот персонажа» и «Проверить ответ» «не видят» базы сайта, а виджет видит.
1) «Мои папки» на сайте — kind "folder" с id, без пути: уходили в поиск по компьютеру, падали (нет path) и роняли все
   знания бота, включая «Библию» из библиотеки. Теперь папка с путём — компьютер, без пути — сайт.
2) «Что ты знаешь?» в базе не находится — персонаж отвечал «в моей базе ничего не нашлось», будто баз нет. Теперь он
   знает, какие базы у него есть, а «Проверить ответ» пишет под ответом, что нашлось."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_brain as EB  # noqa: E402

asked = []


def retrieve(q, b, hist=None):
    asked.append((b.get("kind"), b.get("label"), q))
    hit = b.get("label") == "Библия" and "Моисей" in q
    return {"context": "Исход 3:14 — Я есмь Сущий." if hit else "", "sources": ["Исход"] if hit else [], "found": hit, "images": []}


host = types.SimpleNamespace(account=types.SimpleNamespace(logged_in=lambda: True, retrieve=retrieve), knowledge=None,
                             history=[], emit=lambda *a, **k: None)
host._persona_local_knowledge = lambda *a, **k: EB.BrainMixin._persona_local_knowledge(host, *a, **k)
p = {"id": "t", "name": "Тестовый", "knowledge": [{"kind": "folder", "id": "7", "label": "База СУПЕРАДМИНА"},
                                                  {"kind": "library_folder", "id": "12", "lib": "1", "label": "Библия"}]}
info = {}
out = EB.BrainMixin._persona_knowledge(host, "Что ты знаешь?", None, p=p, quiet=True, hist=[], info=info)
ok({k for k, _, _ in asked} == {"folder", "library_folder"}, f"папка сайта и раздел библиотеки — обе в поиск сайта: {asked}")
ok("ТВОИ ЗНАНИЯ" in out and "«Библия»" in out and "что ты знаешь" in out.lower(), f"ничего не нашлось — персонаж знает свои базы: {out[:200]}")
ok(sorted(info.get("empty", [])) == ["«База СУПЕРАДМИНА»", "«Библия»"] and not info.get("found"), f"что нашлось — для строки под ответом: {info}")
asked.clear(); info = {}
out = EB.BrainMixin._persona_knowledge(host, "Кто такой Моисей?", None, p=p, quiet=True, hist=[], info=info)
ok("Я есмь Сущий" in out and info.get("found") == ["«Библия»"], f"нашлось — в подсказке и в строке: {info}")

# бот: знания — в его подсказке, test() отдаёт, что нашлось
import pbot as PB  # noqa: E402
import llm  # noqa: E402
host.s = types.SimpleNamespace(get=lambda *k: "t", active_llm=lambda: {})
host.personas = types.SimpleNamespace(get=lambda pid: p)
host.persona_llm = lambda pid: {"kind": "openai"}
host._persona_knowledge = lambda *a, **k: EB.BrainMixin._persona_knowledge(host, *a, **k)
seen = {}
llm.stream_chat = lambda prof, system, msgs, **k: (seen.update(system=system) or iter(["Я знаю Библию — спросите о книге или стихе."]))
import tempfile  # noqa: E402
bot = PB.PersonaBot(host, path=Path(tempfile.mkdtemp()) / "pb.json")
r = bot.test("Что ты знаешь?")
ok(r["answer"].startswith("Я знаю Библию") and "ТВОИ ЗНАНИЯ" in seen.get("system", ""), "«Проверить ответ»: базы — в подсказке бота")
ok(r["kb"].get("empty") and "«Библия»" in r["kb"]["empty"], f"«Проверить ответ» отдаёт, что нашлось: {r['kb']}")

src = srctext.text(ROOT, "core/commands_services.py")
ok("r = pb.test(q)" in src, "команда pbot_try отдаёт и знания")
js = (ROOT / "ui/studio/pbot.js").read_text(encoding="utf-8")
ok("pbKbNote(a, r.kb)" in js and "ничего не нашлось" in js and "Знания не ответили" in js, "строка под ответом: нашлось / ничего / не ответили")
pj = (ROOT / "ui/studio/personas.js").read_text(encoding="utf-8")
ok('b.kind === "folder" && b.path ? `folder:${b.path}`' in pj, "редактор персонажа: у каждой папки сайта свой ключ")
ok('b.kind === "folder" && b.path)' in (ROOT / "ui/studio/sitechat.js").read_text(encoding="utf-8"), "чат для сайта: папки сайта — не папки компьютера")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
