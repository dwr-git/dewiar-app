"""Владелец 17.11: «Радар не синхронизируется — дома настроил, на работе пришлось настраивать заново» и «из Пульта по
конкретной статье открывается просто Радар, а не статья».
Настройка Радара (источники, вкл/выкл, задача) — запись mind:radar: новее побеждает; собранные материалы у каждого свои.
Радар, настроенный до 1.0.22, — время по самому свежему источнику. Пульт отдаёт id находок и открывает «insight:<id>»."""
import os, sys, tempfile, time, types
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


class S:
    def __init__(self):
        self.d = {"insight": {}, "ui": {"lang": "ru"}}

    def get(self, sec, key=None):
        v = self.d.get(sec)
        return v if key is None else (v or {}).get(key)

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)


import engine_insight as EI  # noqa: E402

emits = []
home = EI.Radar(types.SimpleNamespace(s=S(), emit=lambda t, **kw: emits.append(t)), tmp / "home")
work = EI.Radar(types.SimpleNamespace(s=S(), emit=lambda t, **kw: emits.append(t)), tmp / "work")

home.e.insight, work.e.insight = home, work
ok(home.setup_snap() is None, "пустой Радар — отдавать нечего")
# дома: источники и задача — через команды студии, как человек
EI._bg = lambda fn, *a: None                            # обход источников в фоне здесь не нужен
EI.command(home.e, "insight_add", {"text": "https://habr.com/ru/rss/all/all/\nhttps://t.me/s/ai_news\nhttps://example.by"})
EI.command(home.e, "insight_mission", {"text": "ИИ-модели и их цены"})
snap = home.setup_snap()
ok(snap and len(snap["sources"]) == 3 and snap["mission"] == "ИИ-модели и их цены" and snap["at"] > 0, f"снимок настройки: {snap and snap['at']}")

# на работе — пусто: приходит настройка с дома
ok(work.setup_apply(snap) is True, "работа приняла настройку с дома")
ok(sorted(EI.I.norm_link(s["url"]) for s in work.st.sources()) == sorted(EI.I.norm_link(x["url"]) for x in snap["sources"]),
   "те же источники")
ok(work.conf()["mission"] == "ИИ-модели и их цены", "та же задача Радара")
ok(work.setup_apply(snap) is False, "та же настройка ещё раз — ничего не меняет")
ok("insight" in emits, "студия узнаёт, что источники поменялись")

# на работе выключили один и убрали другой — дом принимает (новее)
time.sleep(0.01)
srcs = work.st.sources()
work.st.update_source(srcs[0]["id"], on=False); work.st.remove_source(srcs[1]["id"]); work.setup_touch()
ws = work.setup_snap()
ok(home.setup_apply(ws) is True, "дом принял правку с работы")
hs = {EI.I.norm_link(s["url"]): s for s in home.st.sources()}
ok(len(hs) == 2 and hs[EI.I.norm_link(srcs[0]["url"])].get("on") is False, "убранный убран, выключенный выключен")
ok(work.setup_apply(home.setup_snap()) is False, "старая настройка не перебивает новую")

# Радар, настроенный до 1.0.22 (setup_at нет) — время по самому свежему источнику
old = EI.Radar(types.SimpleNamespace(s=S(), emit=lambda *a, **k: None), tmp / "old")
old.st.add_sources("https://example.by")
ok(old.setup_snap()["at"] > 0, "настроенный раньше — тоже уходит на другие компьютеры")

# синхронизация: запись mind:radar в снимке и разбор на приёме
snap_src = (ROOT / "core/sync_snap.py").read_text(encoding="utf-8")
apply_src = (ROOT / "core/sync_apply.py").read_text(encoding="utf-8")
ok('out["mind:radar"]' in snap_src and 'iid == "radar"' in apply_src and "setup_apply(d)" in apply_src, "sync: mind:radar туда и обратно")
cmd = (ROOT / "core/engine_insight.py").read_text(encoding="utf-8")
ok(cmd.count("r.setup_touch()") >= 4, "правки в студии (добавить, убрать, вкл/выкл, задача) отмечают время")

# Пульт: id находок → «insight:<id>»
ct = (ROOT / "core/commands_tasks.py").read_text(encoding="utf-8")
ok('"id": x.get("id") or ""' in ct and 'out["radar"]["pick"] = {"id": best.get("id")' in ct, "данные Пульта — с id находок")
pj = (ROOT / "ui/padpult.js").read_text(encoding="utf-8")
ok('"insight:" + x.id' in pj and 'pk.id ? "insight:"' in pj and 'top.id ? "insight:"' in pj, "Пульт открывает саму статью в «читалке»")

print("\n" + ("❌ Ошибок: %d" % len(fails) if fails else "✅ Всё в порядке"))
sys.exit(1 if fails else 0)
