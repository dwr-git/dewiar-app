"""«Сеть Лиры» (владелец 14.11: «по нодам людей — 3 человека подключились, но за всё время на них ничего не пришло»;
вариант А одобрен): переключатель «Пускать мои общие вопросы в Сеть Лиры» был у всех выключен — вопросов узлам не было.
Теперь у НОВОЙ установки он включён (компьютер и телефон); кто уже пользовался — как было. Честно, один раз, сразу после
подключения мозга: «Общие вопросы без личного иногда отвечают компьютеры других людей — «Сеть Лиры». Выключить: …»."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as S  # noqa: E402
d = Path(tempfile.mkdtemp())
ok(S.Settings(d / "new.json").get("cloud", "net_share") is True, "новая установка — общие вопросы иногда отвечает Сеть Лиры")
(d / "old.json").write_text(json.dumps({"cloud": {"key": "x"}, "ui": {"lang": "ru"}}), encoding="utf-8")
ok(S.Settings(d / "old.json").get("cloud", "net_share") is False, "уже пользовались — как было (выключено)")
(d / "on.json").write_text(json.dumps({"cloud": {"net_share": True}}), encoding="utf-8")
ok(S.Settings(d / "on.json").get("cloud", "net_share") is True, "включали сами — включено")
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("if (!Object.keys(raw).length && S.netShare === undefined) S.netShare = true;" in js, "телефон: новая установка — включено, прежние — как были")
ok("function netNote()" in js and "netNote();" in js and "S.netNoted" in js, "телефон: честная строка один раз после подключения мозга")
ok("иногда отвечают компьютеры других людей" in (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8"), "компьютер: честная строка при подключении")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
