"""№980, третий раз (владелец 25.11): «активная Лира, напоминание ставил через неё — а в уведомлении на телефоне Патрик».
Напоминание с компьютера приходило на телефон без «кто ставил», и телефон подписывал его «текущим обликом» уведомлений —
он мог остаться от Патрика. Теперь кто ставил записывается на компьютере, идёт через синхронизацию в обе стороны, а без
него телефон берёт главного персонажа сейчас (S.persona)."""
import srctext  # noqa: E402
import os, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("DEWIAR_STATE_DIR", tempfile.mkdtemp())
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools_remind as TR  # noqa: E402
r = TR.Reminders.__new__(TR.Reminders)
import threading  # noqa: E402
r._lock = threading.RLock(); r.items = []; r._save = lambda: None
r.who = lambda: "lira"
it = r.add(datetime.now() + timedelta(hours=1), "Обед не забудь взять карту")
ok(it.get("who") == "lira", f"компьютер: кто ставил — с записью: {it}")
r.upsert({"id": it["id"], "text": "Обед — взять карту", "who": ""})
ok(r.get(it["id"])["who"] == "lira", "правка с устройства без «кто ставил» его не стирает")
r.upsert({"id": "p1", "at": it["at"], "text": "С телефона", "kind": "reminder", "who": "patrik"})
ok(r.get("p1")["who"] == "patrik", "с телефона — кто ставил сохраняется")
ok('self.reminders.who = lambda: getattr(getattr(self, "turn", None), "back_to", None) or self.s.get("persona")' in srctext.text(ROOT, "core/engine.py"),
   "движок: кто ставил — главный персонаж; вопрос, переданный специалисту, — от главного (back_to)")

# №980, четвёртый раз (26.11: «только что опять на телефоне от Патрика пришло»): «напомни обсудить…» уходило Патрику по слову
# «обсуд» — он и ставил напоминание. Напоминание, будильник, таймер — дело главного, специалисту не передаётся
from engine_tools import ToolsMixin  # noqa: E402
from personas import BUILTIN  # noqa: E402


class _P:
    l = [dict(BUILTIN["lira"], id="lira"), dict(BUILTIN["patrik"], id="patrik")]

    def get(self, pid):
        return next(p for p in self.l if p["id"] == pid)

    def all(self):
        return self.l


class _St:
    def get(self, a, b=None):
        return "lira" if b is None else True


class _E(ToolsMixin):
    personas, s = _P(), _St()


_e = _E()
ok(_e._route("Помоги обсудить, стоит ли менять работу") == "patrik", "разговор о решении — по-прежнему Патрику")
for q in ("Напомни в 21:00 обсудить с женой даты отпуска", "напомни завтра определиться, стоит ли ехать",
          "Поставь будильник на семь, надо обсудить план", "засеки 10 минут, потом обсудим"):
    ok(_e._route(q) is None, f"«{q}» — ставит Лира, не Патрик")
snap = srctext.text(ROOT, "core/sync_snap.py")
ok('d["who"] = str(r["who"])[:40]' in snap, "компьютер → облако: who в напоминании")
ok('**({"who": str(d["who"])[:40]} if d.get("who") else {})' in srctext.text(ROOT, "core/sync_apply.py"), "облако → компьютер: who принимается")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("x.who ? { who: x.who } : {}" in app, "телефон → облако: who в напоминании")
ok("const who = [d.who, was && was.who, S.persona].find(w => w && PERSONAS.some(p => p.id === w))" in app,
   "облако → телефон: пришедший, прежний, иначе главный сейчас — не «текущий облик»")
ok("filter(a => a && a.id && !a.who).forEach(a => D.alarmSet(" in app, "уже стоящие без «кто ставил» — один раз подписываются главным")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
