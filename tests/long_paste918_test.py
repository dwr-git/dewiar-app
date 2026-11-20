"""№918 (владелец 20.11): вставил в «Чат» спецификацию на 21 000 знаков и «Проанализируй этот текст на слабости…» — Лира
решила, что это просьба к плагину «Дайджест по интересам» (по словам из вставленного текста), рассказала новости
(«Доброе утро, Миша…»), а потом ответила на разговор в комнате (окно «ваша очередь» после набранного вопроса).
1) навыки, плагины и группы действий подбираются по самой просьбе (ask_core), а не по вставленному тексту;
2) после набранного вопроса фон не слушаем; 3) длинная вставка в виджете и «Чате» — вложением (текст целиком у модели)."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from engine_base import ask_core, LONG_ASK  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

spec = "\n\n".join(["Сервер под 1000 и 1500 одновременных звонков"] + [
    f"{i}. Дайджест новостей коллектора, утренняя сводка нагрузки, интересы сервиса, Kafka, ClickHouse, диски {i} ТБ." for i in range(260)])
ask = "Проанализируй этот текст спецификаций на слабости, противоречия и неточности. Также кратко опиши, как всё работает."
core = ask_core(spec + "\n\n" + ask)
ok(len(spec) > 20000 and ask in core and "Дайджест" not in core and len(core) < 400, f"после вставки — просьба: «{core[-60:]}»")
core2 = ask_core("Переведи на английский:\n\n" + spec)
ok(core2.startswith("Переведи на английский") and len(core2) < 900, "просьба перед вставкой — тоже видна")
core3 = ask_core(spec + "\n\nКоротко опиши, что тут написано.\n\nСпасибо!")
ok("Коротко опиши" in core3, "«…Спасибо!» в конце — берём и абзац перед ним")
ok(ask_core("Какая погода завтра?") == "Какая погода завтра?", "обычный вопрос — как есть")
ok(ask_core("Что в файле?\n\nВложения:\n[договор.pdf]\n" + "x" * 5000) == "Что в файле?", "вложения отрезаны")

ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ap = (ROOT / "core/answer_prompt.py").read_text(encoding="utf-8")
ok("slim_text = ask_core(text)" in ea, "группы действий — по просьбе")
ok("self.skills.hint_for(ask_core(text))" in ap and "ask = ask_core(text)" in ap, "навыки и плагины — по просьбе")
ok('turn.typed = time.monotonic() - getattr(self, "_typed_t", 0.0) < 2' in ea and 'getattr(turn, "typed", False)' in ea,
   "набранный вопрос — после ответа фон не слушаем")
ct = (ROOT / "core/commands_talk.py").read_text(encoding="utf-8")
ok(ct.index('if a.get("typed"):') < ct.index("self._typed_t = time.monotonic()") < ct.index("self.ask(text, images)", ct.index('if cmd == "say"')),
   "«say» отмечает только набранный в поле вопрос (кнопки-подсказки — по-прежнему «ваша очередь»)")
hud0 = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('core.sendLater("say", { text: q, images, files, typed: true })' in hud0 and 'core.sendLater("say", { text: q, files, typed: true })'
   in (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8"), "виджет и «Чат» отправляют набранное с пометкой")

hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("txt.length > PASTE_AS_FILE" in hud and "function addPasted(" in hud and "function unPaste(" in hud, "виджет: длинная вставка — вложением, нажатие возвращает текст")
chat = (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8")
ok("PASTE_AS_FILE" in chat and "chatAddPasted(" in chat, "«Чат» студии: то же")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("PASTE_AS_FILE" in app, "телефон: то же")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
