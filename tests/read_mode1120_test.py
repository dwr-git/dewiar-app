"""Владелец 20.11: «если большие сложные ответы — чтобы Лира, видя объём, сказала, что это лучше прочитать… само чтение
бледное, текст единообразный — сделать живее, как в текстовом редакторе». Набранный вопрос с разбором, анализом, планом
(или с большим текстом/вложением) — ответ «для чтения»: модель оформляет (подзаголовки, жирное, списки), вслух — только
суть, потом «Подробно — на экране» и виджет открывает «Ответ целиком» в цветах блокнота."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from engine_base import read_mode, READ_HINT, READ_VOICE  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

ok(read_mode("Проанализируй этот текст на слабости и противоречия", True), "набрали «проанализируй…» — для чтения")
ok(read_mode("Составь план переезда", True) and read_mode("Сравни iPhone и Pixel", True), "план, сравнение — для чтения")
ok(read_mode("Что в файле?\n\nВложения:\n[договор.pdf]\nтекст", True), "к вопросу вложение — для чтения")
ok(read_mode("x" * 2000 + "\n\nЧто думаешь?", True), "большой вставленный текст — для чтения")
ok(not read_mode("Проанализируй этот текст", False), "спросили голосом — как всегда, голосом")
ok(not read_mode("Какая погода завтра?", True) and not read_mode("Привет, как дела?", True), "простой набранный вопрос — как всегда")
ok("## " in READ_HINT and "**жирным**" in READ_HINT and "первым абзацем" in READ_HINT and 300 <= READ_VOICE <= 600,
   "подсказка модели: суть первым абзацем, подзаголовки, жирное, списки; вслух — около полминуты")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("turn.read = read_mode(text, getattr(turn, \"typed\", False))" in ea and "ctx.append(READ_HINT)" in ea, "ход: признак и подсказка — в справку к вопросу (подсказка системы не меняется)")
ok("voice_cap = READ_VOICE" in ea and "Подробно — на экране, так удобнее читать." in ea and 'self.emit("read_open")' in ea, "вслух — суть, дальше «на экране», окно чтения открывается")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('.on("read_open"' in hud and "openReader()" in hud, "виджет: «Ответ целиком» открывается сам")
ok("#rd-body .md .h { font-size" in hud and "body.light #rd-body .md b { color" in hud and "<i>$2</i>" in hud, "чтение — цветные подзаголовки, жирное, пункты, курсив")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
