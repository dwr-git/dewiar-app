"""Разбор кода человеком (28.11), мелкое, но важное для честности ответов:
№1147 — «Радар» (insight_ask) резал JSON на 9000 знаков посреди строки — модель получала битые данные;
№1146 — «Интересное в мире»: материал с датой «из будущего» вставал первым в свежие;
№1149 — своя память персонажа: в подсказке назывался файл «Обо мне», а читался его собственный."""
import json, os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


from tools_docs import fit_json  # noqa: E402
o = {"brief": "б" * 500, "items": [{"title": f"Материал {i}", "url": f"https://e.x/{i}", "why": "п" * 700} for i in range(12)]}
s = fit_json(o, 9000)
d = json.loads(s)
ok(len(s) <= 9000 and 0 < len(d["items"]) < 12 and d.get("_cut"), f"длинно — целый JSON, лишние материалы убраны и это отмечено ({len(s)} зн., {len(d['items'])} шт.)")
ok(json.loads(fit_json({"a": 1, "items": [1, 2]}, 9000)) == {"a": 1, "items": [1, 2]}, "коротко — как есть")
ok(len(fit_json({"x": "я" * 20000}, 9000)) <= 9000, "одна огромная строка — укорочена, JSON цел")

import world  # noqa: E402
now = time.time()
feed = [{"url": "https://a.x/1", "title": "Обычная новость", "ts": int(now - 3600)},
        {"url": "https://a.x/2", "title": "Новость из будущего", "ts": int(now + 30 * 86400)},
        {"url": "https://a.x/3", "title": "Без даты", "ts": 0}]
world.I.parse_feed = lambda page, src: feed
out, errs = world.collect(lambda src: "x", ["https://a.x/rss"], now=now, hours=24)
ok(out and out[0]["title"] == "Обычная новость", f"дата «из будущего» — не первой: {[x['title'] for x in out]}")

src = (ROOT / "core/answer_prompt.py").read_text(encoding="utf-8")
ok('rel = str(self.workspace._mem()[0])' in src and 'файл «{rel}»' in src, "в подсказке — файл той памяти, что читается (общая или персонажа)")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
