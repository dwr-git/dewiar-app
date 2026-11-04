"""Кто делает плагин (04.11, пользователь: «у Лиры модель не особо мощная, а у Патрика получше; не смог сделать, чтобы
изменением плагина занялся Патрик — менять настройки Лиры не хочется»): плагин пишет модель персонажа — того, кто
отвечает, или названного («пусть Патрик сделает», by), и выбранного в студии («Кто делает»); общий «Мозг» — только если у
персонажа своей модели нет."""
import os, sys, tempfile
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


import plugin_maker as PM  # noqa: E402
import tools as T  # noqa: E402

asked = []


class S:
    def __init__(self):
        self.d = {"persona": "lira"}

    def get(self, *k):
        return self.d.get(k[0])

    def active_llm(self):
        return {"base_url": "http://general", "model": "general"}


class Host:
    def __init__(self):
        self.s = S()

    def persona_llm(self, pid=None):
        pid = pid or self.s.get("persona")
        asked.append(pid)
        return {"lira": {"base_url": "http://weak", "model": "weak"}, "patrik": {"base_url": "http://strong", "model": "strong"}}[pid]

    def find_persona(self, name):
        return {"патрик": "patrik", "патрика": "patrik", "лира": "lira"}.get(name.lower())

    class personas:
        @staticmethod
        def get(pid):
            return {"lira": {"name": "Лира"}, "patrik": {"name": "Патрик"}}.get(pid)


H = Host()
M = PM.Maker(None, H)
used = []
import llm as L  # noqa: E402
L.stream_chat = lambda prof, system, msgs: (used.append(prof["model"]), iter(["ok"]))[1]
PM.stream_chat = L.stream_chat

M.llm("s", "u")
ok(used[-1] == "weak", f"по умолчанию — модель того, кто отвечает (Лира): {used[-1]}")
with M.using("patrik"):
    M.llm("s", "u")
    ok(M.who() == "Патрик", "кто делает — Патрик")
ok(used[-1] == "strong", f"«Кто делает: Патрик» — модель Патрика: {used[-1]}")
M.llm("s", "u")
ok(used[-1] == "weak" and M.by is None, "после — снова тот, кто отвечает")
ok(T._maker_by(M, {"by": "Патрика"}) == "patrik" and T._maker_by(M, {}) is None, "by: имя персонажа -> его id; пусто — тот, кто отвечает")
try:
    T._maker_by(M, {"by": "Вася"}); ok(False, "неизвестный персонаж — ошибка")
except T.ToolError as e:
    ok("Персонажа «Вася» нет" in str(e), "неизвестный персонаж — понятная ошибка")
# 04.11: «by» сначала встал в описание отдельным элементом — у plugin_create/plugin_change сдвинулись поля, окно не получало
# каталог действий (title — функция, «not JSON serializable») — проверяем сам каталог, а не текст файла
import json as _json
for _n in ("plugin_create", "plugin_change"):
    _v = T.TOOLS[_n]
    ok(len(_v) == 5 and isinstance(_v[0], str) and isinstance(_v[1], dict) and isinstance(_v[2], str) and callable(_v[3]) and isinstance(_v[4], str)
       and "by" in _v[1]["properties"] and "by —" in _v[0], f"{_n}: описание, схема с by, исполнитель — на своих местах")
ok(all(isinstance(v[4], str) for v in T.TOOLS.values()), "у всех действий подпись — текст (каталог для окна сериализуется)")
_json.dumps({n: [v[0], v[1], v[2], v[4]] for n, v in T.TOOLS.items()})
src = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok('"by": {"type": "string"}' in src and "пусть Патрик сделает" in src, "у plugin_create и plugin_change — поле by")
js = (ROOT / "ui/studio/plugmake.js").read_text(encoding="utf-8") + (ROOT / "ui/studio/plugpage.js").read_text(encoding="utf-8")
ok('pmkWho("pmk-who")' in js and 'by: pmkWhoVal("pmk-who")' in js and 'pmkWho("plp-ed-who")' in js, "студия: «Кто делает» при создании и правке плагина")
eng = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok(eng.count('M.using(str(a.get("by") or "") or None)') == 2, "ядро: plugin_make и plugin_change берут by из студии")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
