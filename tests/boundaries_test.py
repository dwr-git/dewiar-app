"""Границы помощника (core/boundaries.py и то же в app.js): грубость В АДРЕС помощника узнаётся («ты тупая», «дура ты»,
«Лира, дура», «заткнись», «сделай, тупица»), ругань о других и о жизни — нет («сосед — дурак», «бля, дождь»), обычная
речь — нет; отказ помощника узнаётся; правила на компьютере и телефоне — одинаковые (телефон — копия выражений)."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import boundaries as B  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


RUDE = ["ты тупая", "Лира, дура!", "дура ты", "заткнись уже", "ну ты и дура", "сделай отчёт, тупица, быстро", "ты совсем идиотка?",
        "отвали", "Иди ты в жопу", "ты бесполезная", "закрой рот"]
FINE = ["ты знаешь, что этот сосед дурак", "бля, опять дождь", "какой овощ полезнее", "ты такая умная", "это тупой вопрос, наверное",
        "мудак сосед опять шумит", "поставь будильник на семь", "Ты дура? Шучу, ты умница" and "ты умница", "сыграй мне что-нибудь бодрое",
        "тупой нож — опасный нож", "идиот из книги Достоевского — кто это?"]
ok(all(B.rude(t) for t in RUDE), "грубость в адрес помощника узнаётся: " + ", ".join(t for t in RUDE if not B.rude(t)))
ok(not any(B.rude(t) for t in FINE), "ругань не в адрес помощника и обычная речь — не грубость: " + ", ".join(t for t in FINE if B.rude(t)))
ok(B.refused("Нет, в этом я не помогу. Могу подсказать другое.") and B.refused("Мне так неприятно. Давай по делу?") and not B.refused("Конечно, сделаю!"),
   "отказ и граница помощника узнаются")
ok("достоинство" in B.RULE and "не повод для отказа" in B.RULE, "правило: достоинство, но обычное — не повод отказывать")

js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
m = re.search(r'const RUDE_RX = (?:new RegExp|LBRX)\((.*), "i"\);', js)
r = re.search(r'const REFUSED_RX = (?:new RegExp|LBRX)\((.*), "i"\);', js)
ok(m and json.loads(m.group(1)) == B.DIRECT_RX.pattern and r and json.loads(r.group(1)) == B.REFUSED_RX.pattern,
   "на телефоне — те же выражения, что на компьютере")
ok(json.dumps(B.RULE, ensure_ascii=False) in js and json.dumps(B.NOTE, ensure_ascii=False) in js, "и тот же текст правила")
node = subprocess.run(["node", "-e", f"const rx=new RegExp({m.group(1)},'i');const t={json.dumps(RUDE + FINE, ensure_ascii=False)};"
                       "console.log(JSON.stringify(t.map(x=>rx.test(x.toLowerCase().replace(/ё/g,'е')))))"], capture_output=True, text=True)
got = json.loads(node.stdout or "[]")
ok(got == [True] * len(RUDE) + [False] * len(FINE), f"телефон решает так же: {got}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
