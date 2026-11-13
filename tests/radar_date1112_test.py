"""«Радар» знает сегодняшнюю дату (владелец 12.11: «гипотезы он строит в прошедшем времени… возможно модель не знает текущее
время»): модель видела мир только до обучения, а в подсказках Радара даты не было — «к концу января 2026» при ноябре 2026.
Теперь в подсказках разбора, брифа, эволюции и вопроса — «Сегодня ГГГГ-ММ-ДД» и даты материалов; срок гипотезы — от недели
до 60 дней вперёд (в подсказке — числами); гипотеза со сроком в прошлом не принимается; уже выдвинутые «в прошлое» —
убираются при открытии «Разума». Черновики статей — тоже с сегодняшней датой."""
import os, sys, tempfile, time, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import json, insight as I, engine_insight as EI  # noqa: E402
today = datetime.now().date()
x = {"id": "a1", "title": "Qwen выпустили модель", "src_name": "habr", "url": "https://h/1", "text": "Текст", "ts": time.time() - 86400,
     "a": {"signal": 8, "summary": "Суть", "why": "w", "tags": ["llm"], "entities": []}}
for name, (sy, us) in {"разбор": I.analyze_prompt("ИИ", x), "бриф": I.brief_prompt("ИИ", [x], []), "эволюция": I.evolve_prompt("ИИ", {}, [x]),
                       "вопрос": I.question_prompt("что нового?", I.ask_context([x], [], None, None), "ИИ")}.items():
    ok(f"Сегодня {today:%Y-%m-%d}" in us, f"{name}: в подсказке — сегодняшняя дата")
sy, us = I.evolve_prompt("ИИ", {}, [x])
ok(str(today + timedelta(days=7)) in sy and str(today + timedelta(days=60)) in sy and "никогда не о дате раньше сегодняшней" in sy,
   "эволюция: срок прогноза — числами от сегодняшнего дня, прошлое — не прогноз")
ok(str((today - timedelta(days=1)).strftime("%Y-%m-%d")) in us, "материалы — с датами")
ok(I.analyze_prompt("ИИ", x, "en")[1].startswith("Niche") and "Today is" in I.analyze_prompt("ИИ", x, "en")[1], "по-английски — тоже")
raw = json.dumps({"theses": [{"text": "Тезис", "refs": ["a1"]}], "new_hyps": [
    {"text": "К концу января 2026 выйдет Qwen-4", "due": "2026-01-31"},
    {"text": "Через месяц выйдет Qwen-5", "due": str(today + timedelta(days=30))},
    {"text": "Без срока", "due": ""}]})
m = I.apply_evolve({}, raw, [x])
ok([h["text"] for h in m["hyps"]] == ["Через месяц выйдет Qwen-5"], f"гипотеза в прошлое и без срока — не принимаются: {[h['text'] for h in m['hyps']]}")
born = int(time.time())
old = {"hyps": [{"id": "1", "text": "К середине февраля 2026…", "due": "2026-02-15", "state": "open", "at": born},
                {"id": "2", "text": "Через месяц…", "due": str(today + timedelta(days=30)), "state": "open", "at": born},
                {"id": "3", "text": "Старая проверенная", "due": "2026-02-15", "state": "confirmed", "at": born}]}
c, gone = I.clean_hyps(old)
ok(gone == 1 and [h["id"] for h in c["hyps"]] == ["2", "3"], "выдвинутые «в прошлое» — убираются, проверенные и настоящие — остаются")


class S:
    d = {"insight": {}, "ui": {"lang": "ru"}}
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]


r = EI.Radar(types.SimpleNamespace(s=S(), emit=lambda *a, **k: None, push=lambda *a, **k: None), tmp / "r")
r.st.save("mind", old)
v = r.mind_view()
ok([h["id"] for h in v["hyps"]] == ["2", "3"] and [h["id"] for h in r.st.load("mind", {})["hyps"]] == ["2", "3"], "«Разум»: при открытии — уже без них")
import sites_blog as B  # noqa: E402
src = (ROOT / "core/sites_blog.py").read_text()
ok(src.count("Сегодня {datetime.now()") == 2, "план тем и черновик статьи — с сегодняшней датой")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
