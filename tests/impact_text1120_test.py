"""Владелец 20.11: «выпуски очень долгие, весь день собираем» — из 1027 проверок выбиралось 731: общие файлы шли целиком.
Теперь точнее: ключ словаря-константы (settings.DEFAULTS) — где этот ключ назван; только комментарий в конце строки —
ничего; app.css — по id и классам изменённых правил; файлы сайта — по функциям и словам правки; продолжение многострочного
комментария JS — не код; подписка на событие (N.on(...)) — по её словам, а не «весь файл»."""
import ast, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "tools"))
import test_impact as T  # noqa: E402

bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


ok(T._code_part('        "scene": False,             # проба') == '"scene": False,', "комментарий в конце строки — не код")
ok(T._code_part('x = "a # b"  # c') == 'x = "a # b"', "решётка в кавычках — код")
src = 'DEFAULTS = {\n    "llm": {\n        "scene": False,\n        "scene_on": None,\n    },\n    "cloud": {"gift_seen": ""},\n}\n'
v = ast.parse(src).body[0].value
ok(T._dict_key_at(v, 4) == "scene_on" and T._dict_key_at(v, 6) == "gift_seen", "строка внутри словаря — её ключ")
ok(T._dict_key_at(v, 1) is None, "скобка словаря — по имени константы, как раньше")
js = "/* первая\n   продолжение без звёздочки\n*/\nconst a = 1;\nfoo(); /* хвост */\n"
ok(T._js_block_comment_lines(js) == {1, 2, 3}, f"строки многострочного комментария JS: {sorted(T._js_block_comment_lines(js))}")
s = (ROOT / "tools/test_impact.py").read_text(encoding="utf-8")
ok("CSS_TXT.match(f) or PHP_TXT.match(f)" in s and "def text_pick(" in s, "app.css и файлы сайта — по смыслу правки")
ok('fns.add("__stmt__")' in s and "on_ev and rx and rx.search(src(t))" in s, "подписка на событие — по её словам")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
